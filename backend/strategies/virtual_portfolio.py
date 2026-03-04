"""
Virtual Portfolio - Independent capital and PnL tracking per strategy.

Each strategy maintains its own:
- Realized PnL
- Unrealized PnL
- Positions (separate from other strategies)
- Trade history
- Risk metrics
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class VirtualPosition:
    """A virtual position held by a strategy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    market_id: str = ""
    game_id: str = ""
    side: str = "yes"  # "yes" or "no"
    quantity: int = 0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    entry_time: datetime = field(default_factory=datetime.utcnow)
    entry_edge: float = 0.0
    entry_signal_score: float = 0.0
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.quantity == 0:
            return 0.0
        price_diff = self.current_price - self.avg_entry_price
        return price_diff * self.quantity
    
    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.avg_entry_price * self.quantity
    
    @property
    def current_value(self) -> float:
        """Current market value."""
        return self.current_price * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis
    
    @property
    def hold_time_seconds(self) -> float:
        """Time position has been held."""
        return (datetime.utcnow() - self.entry_time).total_seconds()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "game_id": self.game_id,
            "side": self.side,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "entry_time": self.entry_time.isoformat(),
            "entry_edge": self.entry_edge,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "hold_time_seconds": self.hold_time_seconds
        }


@dataclass
class VirtualTrade:
    """A virtual trade executed by a strategy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    market_id: str = ""
    game_id: str = ""
    side: str = "yes"
    direction: str = "buy"  # "buy" or "sell"
    quantity: int = 0
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Signal context
    edge_at_entry: float = 0.0
    signal_score: float = 0.0
    signal_type: str = ""
    
    # Exit context (if closing trade)
    edge_at_exit: float = 0.0
    pnl: float = 0.0
    is_winner: bool = False
    
    # Decision logging
    decision_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "market_id": self.market_id,
            "game_id": self.game_id,
            "side": self.side,
            "direction": self.direction,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "edge_at_entry": self.edge_at_entry,
            "signal_score": self.signal_score,
            "signal_type": self.signal_type,
            "edge_at_exit": self.edge_at_exit,
            "pnl": self.pnl,
            "is_winner": self.is_winner,
            "decision_reason": self.decision_reason
        }


class VirtualPortfolio:
    """
    Virtual portfolio for a single strategy.
    Tracks positions, trades, and PnL independently.
    """
    
    def __init__(self, strategy_id: str, starting_capital: float = 10000.0):
        self.strategy_id = strategy_id
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        
        # Positions by market_id
        self._positions: Dict[str, VirtualPosition] = {}
        
        # Trade history
        self._trades: List[VirtualTrade] = []
        
        # Daily stats
        self._daily_stats: Dict[str, Dict] = {}
        
        # Risk tracking
        self._peak_capital = starting_capital
        self._max_drawdown = 0.0
        self._consecutive_losses = 0
        self._last_trade_time: Optional[datetime] = None
        
        # Circuit breaker state
        self._circuit_breaker_active = False
        self._circuit_breaker_until: Optional[datetime] = None
        
        # Session tracking
        self._session_start = datetime.utcnow()
        self._trades_today = 0
        self._trades_this_hour = 0
        self._last_hour_reset = datetime.utcnow()
        
        logger.info(f"VirtualPortfolio initialized for {strategy_id} with ${starting_capital}")
    
    # ==========================================
    # POSITION MANAGEMENT
    # ==========================================
    
    def open_position(
        self,
        market_id: str,
        game_id: str,
        side: str,
        quantity: int,
        price: float,
        edge: float = 0.0,
        signal_score: float = 0.0,
        reason: str = ""
    ) -> Optional[VirtualTrade]:
        """Open or add to a position."""
        cost = quantity * price
        
        # Check capital
        if cost > self.available_capital:
            logger.warning(f"[{self.strategy_id}] Insufficient capital for trade")
            return None
        
        # Create trade record
        trade = VirtualTrade(
            strategy_id=self.strategy_id,
            market_id=market_id,
            game_id=game_id,
            side=side,
            direction="buy",
            quantity=quantity,
            price=price,
            edge_at_entry=edge,
            signal_score=signal_score,
            decision_reason=reason
        )
        
        # Update or create position
        if market_id in self._positions:
            pos = self._positions[market_id]
            # Average up/down
            total_qty = pos.quantity + quantity
            pos.avg_entry_price = (pos.avg_entry_price * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
        else:
            self._positions[market_id] = VirtualPosition(
                market_id=market_id,
                game_id=game_id,
                side=side,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                entry_edge=edge,
                entry_signal_score=signal_score
            )
        
        # Deduct capital
        self.current_capital -= cost
        
        # Record trade
        self._trades.append(trade)
        self._update_trade_counts()
        self._last_trade_time = datetime.utcnow()
        
        logger.info(f"[{self.strategy_id}] OPEN: {side} {quantity}@{price:.2f} on {market_id} | Reason: {reason}")
        
        return trade
    
    def close_position(
        self,
        market_id: str,
        price: float,
        quantity: Optional[int] = None,
        edge_at_exit: float = 0.0,
        reason: str = ""
    ) -> Optional[VirtualTrade]:
        """Close or reduce a position."""
        if market_id not in self._positions:
            logger.warning(f"[{self.strategy_id}] No position to close for {market_id}")
            return None
        
        pos = self._positions[market_id]
        close_qty = quantity if quantity else pos.quantity
        close_qty = min(close_qty, pos.quantity)
        
        # Calculate PnL
        entry_cost = pos.avg_entry_price * close_qty
        exit_value = price * close_qty
        pnl = exit_value - entry_cost
        
        # Create trade record
        trade = VirtualTrade(
            strategy_id=self.strategy_id,
            market_id=market_id,
            game_id=pos.game_id,
            side=pos.side,
            direction="sell",
            quantity=close_qty,
            price=price,
            edge_at_entry=pos.entry_edge,
            edge_at_exit=edge_at_exit,
            pnl=pnl,
            is_winner=pnl > 0,
            decision_reason=reason
        )
        
        # Update position
        pos.quantity -= close_qty
        if pos.quantity <= 0:
            del self._positions[market_id]
        
        # Add proceeds to capital
        self.current_capital += exit_value
        
        # Update stats
        self._update_after_close(pnl)
        
        # Record trade
        self._trades.append(trade)
        self._update_trade_counts()
        self._last_trade_time = datetime.utcnow()
        
        logger.info(f"[{self.strategy_id}] CLOSE: {close_qty}@{price:.2f} on {market_id} | PnL: ${pnl:.2f} | Reason: {reason}")
        
        return trade
    
    def update_position_price(self, market_id: str, current_price: float):
        """Update current price for unrealized PnL calculation."""
        if market_id in self._positions:
            self._positions[market_id].current_price = current_price
    
    def get_position(self, market_id: str) -> Optional[VirtualPosition]:
        """Get position for a market."""
        return self._positions.get(market_id)
    
    def has_position(self, market_id: str) -> bool:
        """Check if strategy has position in market."""
        return market_id in self._positions
    
    def get_all_positions(self) -> List[VirtualPosition]:
        """Get all open positions."""
        return list(self._positions.values())
    
    # ==========================================
    # PNL & METRICS
    # ==========================================
    
    @property
    def available_capital(self) -> float:
        """Capital available for new trades."""
        return self.current_capital
    
    @property
    def total_exposure(self) -> float:
        """Total capital deployed in positions."""
        return sum(p.cost_basis for p in self._positions.values())
    
    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())
    
    @property
    def realized_pnl(self) -> float:
        """Total realized P&L from closed trades."""
        return sum(t.pnl for t in self._trades if t.direction == "sell")
    
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def total_pnl_pct(self) -> float:
        """Total P&L as percentage of starting capital."""
        return (self.total_pnl / self.starting_capital) * 100
    
    @property
    def portfolio_value(self) -> float:
        """Current total portfolio value."""
        return self.current_capital + sum(p.current_value for p in self._positions.values())
    
    @property
    def win_rate(self) -> float:
        """Win rate of closed trades."""
        closed_trades = [t for t in self._trades if t.direction == "sell"]
        if not closed_trades:
            return 0.0
        winners = sum(1 for t in closed_trades if t.is_winner)
        return (winners / len(closed_trades)) * 100
    
    @property
    def total_trades(self) -> int:
        """Total number of trades."""
        return len(self._trades)
    
    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown from peak."""
        return self._max_drawdown
    
    @property
    def max_drawdown_pct(self) -> float:
        """Maximum drawdown as percentage."""
        if self._peak_capital == 0:
            return 0.0
        return (self._max_drawdown / self._peak_capital) * 100
    
    @property
    def risk_utilization(self) -> float:
        """Percentage of capital deployed."""
        return (self.total_exposure / self.starting_capital) * 100
    
    @property
    def avg_edge_at_entry(self) -> float:
        """Average edge at entry for all trades."""
        entry_trades = [t for t in self._trades if t.direction == "buy"]
        if not entry_trades:
            return 0.0
        return sum(t.edge_at_entry for t in entry_trades) / len(entry_trades)
    
    @property
    def avg_edge_at_exit(self) -> float:
        """Average edge at exit for closed trades."""
        exit_trades = [t for t in self._trades if t.direction == "sell"]
        if not exit_trades:
            return 0.0
        return sum(t.edge_at_exit for t in exit_trades) / len(exit_trades)
    
    @property
    def avg_hold_time(self) -> float:
        """Average hold time for positions (seconds)."""
        if not self._positions:
            return 0.0
        return sum(p.hold_time_seconds for p in self._positions.values()) / len(self._positions)
    
    # ==========================================
    # DAILY STATS
    # ==========================================
    
    def get_daily_stats(self, date_str: Optional[str] = None) -> Dict:
        """Get stats for a specific day."""
        if date_str is None:
            date_str = date.today().isoformat()
        
        day_trades = [
            t for t in self._trades 
            if t.timestamp.date().isoformat() == date_str
        ]
        
        closed = [t for t in day_trades if t.direction == "sell"]
        
        return {
            "date": date_str,
            "trades": len(day_trades),
            "realized_pnl": sum(t.pnl for t in closed),
            "winners": sum(1 for t in closed if t.is_winner),
            "losers": sum(1 for t in closed if not t.is_winner),
            "win_rate": (sum(1 for t in closed if t.is_winner) / len(closed) * 100) if closed else 0,
            "avg_pnl": sum(t.pnl for t in closed) / len(closed) if closed else 0
        }
    
    def get_stats_by_league(self) -> Dict[str, Dict]:
        """Get performance breakdown by league."""
        leagues = {}
        
        for trade in self._trades:
            if trade.direction != "sell":
                continue
            
            # Infer league from game_id pattern
            if "NBA" in trade.game_id.upper():
                league = "NBA"
            elif "NCAAM" in trade.game_id.upper() or "NCAA_M" in trade.game_id.upper():
                league = "NCAA_M"
            elif "NCAAW" in trade.game_id.upper() or "NCAA_W" in trade.game_id.upper():
                league = "NCAA_W"
            else:
                league = "OTHER"
            
            if league not in leagues:
                leagues[league] = {
                    "trades": 0,
                    "pnl": 0.0,
                    "winners": 0
                }
            
            leagues[league]["trades"] += 1
            leagues[league]["pnl"] += trade.pnl
            if trade.is_winner:
                leagues[league]["winners"] += 1
        
        # Calculate win rates
        for league in leagues:
            if leagues[league]["trades"] > 0:
                leagues[league]["win_rate"] = (
                    leagues[league]["winners"] / leagues[league]["trades"] * 100
                )
        
        return leagues
    
    # ==========================================
    # RISK TRACKING
    # ==========================================
    
    def _update_after_close(self, pnl: float):
        """Update metrics after closing a trade."""
        # Update peak and drawdown
        current_value = self.portfolio_value
        if current_value > self._peak_capital:
            self._peak_capital = current_value
        
        drawdown = self._peak_capital - current_value
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown
        
        # Track consecutive losses
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
    
    def _update_trade_counts(self):
        """Update hourly/daily trade counts."""
        now = datetime.utcnow()
        
        # Reset hourly counter if needed
        if (now - self._last_hour_reset).total_seconds() > 3600:
            self._trades_this_hour = 0
            self._last_hour_reset = now
        
        self._trades_this_hour += 1
        self._trades_today += 1
    
    def check_daily_loss_limit(self, max_pct: float) -> bool:
        """Check if daily loss limit is reached."""
        today_stats = self.get_daily_stats()
        daily_loss = -today_stats["realized_pnl"]
        max_loss = self.starting_capital * max_pct
        return daily_loss >= max_loss
    
    def check_drawdown_limit(self, max_pct: float) -> bool:
        """Check if drawdown limit is reached."""
        return self.max_drawdown_pct >= (max_pct * 100)
    
    def activate_circuit_breaker(self, duration_seconds: int):
        """Activate circuit breaker."""
        self._circuit_breaker_active = True
        self._circuit_breaker_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        logger.warning(f"[{self.strategy_id}] Circuit breaker ACTIVATED for {duration_seconds}s")
    
    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker."""
        self._circuit_breaker_active = False
        self._circuit_breaker_until = None
        logger.info(f"[{self.strategy_id}] Circuit breaker DEACTIVATED")
    
    @property
    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is active."""
        if not self._circuit_breaker_active:
            return False
        
        if self._circuit_breaker_until and datetime.utcnow() > self._circuit_breaker_until:
            self.deactivate_circuit_breaker()
            return False
        
        return True
    
    # ==========================================
    # RESET & EXPORT
    # ==========================================
    
    def reset(self, starting_capital: Optional[float] = None):
        """Reset portfolio to initial state."""
        if starting_capital:
            self.starting_capital = starting_capital
        
        self.current_capital = self.starting_capital
        self._positions.clear()
        self._trades.clear()
        self._peak_capital = self.starting_capital
        self._max_drawdown = 0.0
        self._consecutive_losses = 0
        self._circuit_breaker_active = False
        self._circuit_breaker_until = None
        self._trades_today = 0
        self._trades_this_hour = 0
        
        logger.info(f"[{self.strategy_id}] Portfolio RESET to ${self.starting_capital}")
    
    def get_summary(self) -> Dict:
        """Get portfolio summary for dashboard."""
        return {
            "strategy_id": self.strategy_id,
            "starting_capital": self.starting_capital,
            "current_capital": self.current_capital,
            "portfolio_value": self.portfolio_value,
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "win_rate": round(self.win_rate, 1),
            "total_trades": self.total_trades,
            "trades_today": self._trades_today,
            "max_drawdown": round(self._max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "risk_utilization": round(self.risk_utilization, 1),
            "avg_edge_entry": round(self.avg_edge_at_entry * 100, 2),
            "avg_edge_exit": round(self.avg_edge_at_exit * 100, 2),
            "positions_count": len(self._positions),
            "circuit_breaker_active": self.is_circuit_breaker_active,
            "consecutive_losses": self._consecutive_losses
        }
    
    def export_trades_csv(self) -> str:
        """Export trade history to CSV format."""
        if not self._trades:
            return "No trades"
        
        headers = [
            "timestamp", "market_id", "game_id", "side", "direction",
            "quantity", "price", "edge_at_entry", "edge_at_exit",
            "pnl", "is_winner", "decision_reason"
        ]
        
        lines = [",".join(headers)]
        
        for t in self._trades:
            row = [
                t.timestamp.isoformat(),
                t.market_id,
                t.game_id,
                t.side,
                t.direction,
                str(t.quantity),
                f"{t.price:.4f}",
                f"{t.edge_at_entry:.4f}",
                f"{t.edge_at_exit:.4f}",
                f"{t.pnl:.2f}",
                str(t.is_winner),
                t.decision_reason.replace(",", ";")
            ]
            lines.append(",".join(row))
        
        return "\n".join(lines)
    
    def export_trades_json(self) -> str:
        """Export trade history to JSON format."""
        return json.dumps([t.to_dict() for t in self._trades], indent=2)
    
    def get_positions_for_game(self, game_id: str) -> List[VirtualPosition]:
        """Get all positions for a specific game."""
        return [p for p in self._positions.values() if p.game_id == game_id]
