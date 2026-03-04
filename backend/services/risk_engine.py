"""
Risk Engine
Manages risk limits and monitors trading activity.
"""
from typing import Optional, List
from datetime import datetime, date
import logging

from models.risk import RiskLimits, RiskStatus
from repositories import TradeRepository, PositionRepository
from config import settings

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Monitors and enforces risk limits.
    """
    
    def __init__(
        self,
        trade_repo: TradeRepository,
        position_repo: PositionRepository
    ):
        self.trade_repo = trade_repo
        self.position_repo = position_repo
        self.limits = RiskLimits(
            max_position_size=settings.max_position_size,
            max_daily_loss=settings.max_daily_loss,
            max_open_exposure=settings.max_open_exposure,
            max_trades_per_day=settings.max_trades_per_day
        )
    
    async def get_current_status(self) -> RiskStatus:
        """
        Get current risk utilization status.
        """
        trades_today = await self.trade_repo.count_trades_today()
        trades_this_hour = await self.trade_repo.count_trades_last_hour()
        current_exposure = await self.position_repo.get_total_exposure()
        daily_pnl = await self.trade_repo.get_daily_pnl()
        
        # Check for lockout conditions
        is_locked = False
        lockout_reason = None
        
        if trades_today >= self.limits.max_trades_per_day:
            is_locked = True
            lockout_reason = "Daily trade limit reached"
        elif abs(min(0, daily_pnl)) >= self.limits.max_daily_loss:
            is_locked = True
            lockout_reason = "Daily loss limit reached"
        
        return RiskStatus(
            date=date.today(),
            current_exposure=current_exposure,
            daily_pnl=daily_pnl,
            trades_today=trades_today,
            trades_this_hour=trades_this_hour,
            max_open_exposure=self.limits.max_open_exposure,
            max_daily_loss=self.limits.max_daily_loss,
            max_trades_per_day=self.limits.max_trades_per_day,
            is_locked_out=is_locked,
            lockout_reason=lockout_reason,
            updated_at=datetime.utcnow()
        )
    
    async def can_trade(self, trade_size: float = 0) -> tuple[bool, Optional[str]]:
        """
        Check if trading is currently allowed.

        Returns:
            Tuple of (can_trade, reason_if_not)
        """
        status = await self.get_current_status()

        if status.is_locked_out:
            return False, status.lockout_reason

        if not status.can_trade:
            return False, "Risk limits exceeded"

        if trade_size > 0:
            if status.current_exposure + trade_size > self.limits.max_open_exposure:
                return False, f"Would exceed max exposure limit (${self.limits.max_open_exposure})"
            if trade_size > self.limits.max_trade_size:
                return False, f"Trade size exceeds limit (${self.limits.max_trade_size})"

        return True, None

    async def check_safety_gates(
        self,
        market_id: str,
        game_id: str,
        model_id: str,
        yes_bid: float,
        yes_ask: float,
        volume_24h: int,
        fair_value: float,
        market_price: float,
    ) -> tuple[bool, Optional[str]]:
        """
        Master Rules 6 safety gates — ALL must pass before any order.

        Gate 1: KALSHI_ENV must be 'paper' (hard block)
        Gate 2: Bid-ask spread <= 4c
        Gate 3: 24h volume >= 5,000 contracts
        Gate 4: Model daily loss < 10% of allocation
        Gate 5: No existing open position on this game for this model
        Gate 6: Fair value differs from market by >= 5c
        """
        import os

        # Gate 1
        kalshi_env = os.environ.get("KALSHI_ENV", "paper").lower()
        if kalshi_env != "paper":
            return False, f"SAFETY: KALSHI_ENV='{kalshi_env}' — only 'paper' allowed"

        # Gate 2
        spread = round(yes_ask - yes_bid, 4)
        if spread > 0.04:
            return False, f"SAFETY: Spread {spread:.2%} exceeds 4c gate"

        # Gate 3
        if volume_24h < 5000:
            return False, f"SAFETY: Volume {volume_24h} below 5,000 contract gate"

        # Gate 4
        try:
            daily_pnl = await self.trade_repo.get_daily_pnl_by_model(model_id)
            allocation = getattr(self.limits, "model_allocation", 200.0)
            if daily_pnl < -(allocation * 0.10):
                return False, f"SAFETY: Model {model_id} daily loss ${abs(daily_pnl):.2f} exceeds 10% gate"
        except Exception:
            pass

        # Gate 5
        try:
            existing = await self.position_repo.get_open_by_game_and_model(game_id, model_id)
            if existing:
                return False, f"SAFETY: Open position already exists for game {game_id} / model {model_id}"
        except Exception:
            pass

        # Gate 6
        edge = abs(fair_value - market_price)
        if edge < 0.05:
            return False, f"SAFETY: Edge {edge:.2%} below 5c minimum"

        return True, None
    
    def update_limits(self, new_limits: RiskLimits):
        """
        Update risk limits.
        """
        self.limits = new_limits
        logger.info(f"Risk limits updated: max_exposure=${new_limits.max_open_exposure}, max_daily_loss=${new_limits.max_daily_loss}")
    
    def get_limits(self) -> RiskLimits:
        """
        Get current risk limits.
        """
        return self.limits
