"""
Trade Engine
Handles trade execution with risk checks and position management.
"""
from typing import Optional, Tuple
from datetime import datetime
import logging

from models.trade import Trade, TradeStatus, TradeSide, TradeDirection
from models.position import Position
from models.signal import Signal, SignalType
from models.risk import RiskStatus, RiskLimits
from adapters.kalshi import KalshiAdapter
from repositories import PositionRepository, TradeRepository
from config import settings

logger = logging.getLogger(__name__)

class TradeEngine:
    """
    Handles trade execution with risk management.
    """
    
    def __init__(
        self,
        kalshi_adapter: KalshiAdapter,
        position_repo: PositionRepository,
        trade_repo: TradeRepository,
        risk_limits: RiskLimits = None
    ):
        self.kalshi = kalshi_adapter
        self.position_repo = position_repo
        self.trade_repo = trade_repo
        self.risk_limits = risk_limits or RiskLimits()
    
    async def execute_trade(
        self,
        game_id: str,
        market_id: str,
        side: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None,
        signal: Optional[Signal] = None
    ) -> Tuple[Optional[Trade], Optional[str]]:
        """
        Execute a trade with risk checks.
        
        Args:
            game_id: Game ID
            market_id: Kalshi market ID
            side: "yes" or "no"
            direction: "buy" or "sell"
            quantity: Number of contracts
            price: Limit price (None for market order)
            signal: Optional signal that triggered this trade
            
        Returns:
            Tuple of (Trade if successful, error message if failed)
        """
        # Pre-trade risk checks
        risk_check, risk_error = await self._check_risk_limits(
            direction=direction,
            quantity=quantity,
            price=price
        )
        
        if not risk_check:
            logger.warning(f"Trade rejected by risk check: {risk_error}")
            return None, risk_error
        
        try:
            # Execute trade via Kalshi adapter
            trade = await self.kalshi.place_order(
                market_id=market_id,
                side=side,
                direction=direction,
                quantity=quantity,
                price=price
            )
            
            # Add signal info if available
            if signal:
                trade.signal_type = signal.signal_type.value
                trade.edge_at_entry = signal.edge
            
            # Store trade in database
            await self.trade_repo.create(trade)
            
            # Update position in database
            await self._sync_position(market_id)
            
            logger.info(f"Trade executed: {trade.id} - {direction} {quantity} {side}")
            
            return trade, None
            
        except ValueError as e:
            logger.error(f"Trade execution error: {e}")
            return None, str(e)
        except Exception as e:
            logger.error(f"Unexpected trade error: {e}")
            return None, f"Unexpected error: {str(e)}"
    
    async def execute_signal(
        self,
        signal: Signal,
        auto_size: bool = True
    ) -> Tuple[Optional[Trade], Optional[str]]:
        """
        Execute a trade based on a signal.
        
        Args:
            signal: Signal to execute
            auto_size: Use signal's recommended size
            
        Returns:
            Tuple of (Trade if successful, error message if failed)
        """
        if not signal.is_actionable:
            return None, "Signal is not actionable"
        
        # Determine trade parameters from signal
        if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            direction = "buy"
            side = "yes"
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            direction = "buy"  # Buy NO contracts
            side = "no"
        elif signal.signal_type == SignalType.SELL_INTO_STRENGTH:
            # Check if we have a position to sell
            position = await self.kalshi.get_position(signal.market_id)
            if position and position.is_open:
                direction = "sell"
                side = position.side
            else:
                return None, "No position to sell"
        else:
            return None, "Unknown signal type"
        
        # Calculate quantity
        if auto_size:
            # Convert $ size to contracts (assuming ~$0.50 per contract)
            estimated_price = 0.50
            quantity = int(signal.recommended_size / estimated_price)
        else:
            quantity = 1  # Default to 1 contract
        
        quantity = max(1, min(quantity, 100))  # 1-100 contracts
        
        return await self.execute_trade(
            game_id=signal.game_id,
            market_id=signal.market_id,
            side=side,
            direction=direction,
            quantity=quantity,
            signal=signal
        )
    
    async def flatten_all_positions(self) -> Tuple[int, int]:
        """
        Panic button - close all open positions.
        
        Returns:
            Tuple of (positions_closed, errors)
        """
        positions = await self.kalshi.get_positions()
        closed = 0
        errors = 0
        
        for position in positions:
            if position.is_open:
                try:
                    trades = await self.kalshi.flatten_position(position.market_id)
                    if trades:
                        closed += 1
                        for trade in trades:
                            await self.trade_repo.create(trade)
                except Exception as e:
                    logger.error(f"Error flattening position {position.id}: {e}")
                    errors += 1
        
        return closed, errors
    
    async def _check_risk_limits(
        self,
        direction: str,
        quantity: int,
        price: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trade passes risk limits.
        """
        # Get current risk status
        trades_today = await self.trade_repo.count_trades_today()
        trades_this_hour = await self.trade_repo.count_trades_last_hour()
        current_exposure = await self.position_repo.get_total_exposure()
        daily_pnl = await self.trade_repo.get_daily_pnl()
        
        # Check trade frequency
        if trades_today >= self.risk_limits.max_trades_per_day:
            return False, f"Daily trade limit reached ({self.risk_limits.max_trades_per_day})"
        
        if trades_this_hour >= self.risk_limits.max_trades_per_hour:
            return False, f"Hourly trade limit reached ({self.risk_limits.max_trades_per_hour})"
        
        # Check exposure for buys
        if direction == "buy":
            estimated_cost = quantity * (price or 0.50)  # Estimate if no price
            new_exposure = current_exposure + estimated_cost
            
            if new_exposure > self.risk_limits.max_open_exposure:
                return False, f"Would exceed max exposure (${self.risk_limits.max_open_exposure})"
            
            if estimated_cost > self.risk_limits.max_trade_size:
                return False, f"Trade size exceeds limit (${self.risk_limits.max_trade_size})"
        
        # Check daily loss limit
        if daily_pnl < 0 and abs(daily_pnl) >= self.risk_limits.max_daily_loss:
            return False, f"Daily loss limit reached (${self.risk_limits.max_daily_loss})"
        
        return True, None
    
    async def _sync_position(self, market_id: str):
        """
        Sync position from Kalshi adapter to database.
        """
        position = await self.kalshi.get_position(market_id)
        if position:
            existing = await self.position_repo.get_by_market_id(market_id)
            if existing:
                await self.position_repo.update(existing.id, position.dict())
            else:
                await self.position_repo.create(position)
    
    async def get_risk_status(self) -> RiskStatus:
        """
        Get current risk utilization status.
        """
        trades_today = await self.trade_repo.count_trades_today()
        trades_this_hour = await self.trade_repo.count_trades_last_hour()
        current_exposure = await self.position_repo.get_total_exposure()
        daily_pnl = await self.trade_repo.get_daily_pnl()
        
        return RiskStatus(
            current_exposure=current_exposure,
            daily_pnl=daily_pnl,
            trades_today=trades_today,
            trades_this_hour=trades_this_hour,
            max_open_exposure=self.risk_limits.max_open_exposure,
            max_daily_loss=self.risk_limits.max_daily_loss,
            max_trades_per_day=self.risk_limits.max_trades_per_day
        )
