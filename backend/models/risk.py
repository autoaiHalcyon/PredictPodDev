"""
Risk Model - Risk limits and status tracking.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class RiskLimits(BaseModel):
    """User-configurable risk limits"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Position limits
    max_position_size: float = 100.0  # Max $ per single position
    max_trade_size: float = 50.0  # Max $ per single trade
    
    # Exposure limits
    max_open_exposure: float = 1000.0  # Max total exposure across all positions
    max_exposure_per_game: float = 200.0  # Max exposure per game
    
    # Loss limits
    max_daily_loss: float = 500.0  # Max daily loss before lockout
    max_weekly_loss: float = 1500.0  # Max weekly loss
    
    # Trade frequency
    max_trades_per_day: int = 50
    max_trades_per_hour: int = 10
    
    # Signal thresholds for auto-execution
    min_edge_for_trade: float = 0.03  # 3% minimum edge
    min_confidence_for_trade: float = 0.5  # 50% minimum confidence
    
    # Updated
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RiskStatus(BaseModel):
    """Current risk utilization status"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Date tracking
    status_date: str = Field(default_factory=lambda: datetime.utcnow().strftime('%Y-%m-%d'))
    
    # Current utilization
    current_exposure: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    trades_today: int = 0
    trades_this_hour: int = 0
    
    # Limits (from RiskLimits)
    max_open_exposure: float = 1000.0
    max_daily_loss: float = 500.0
    max_trades_per_day: int = 50
    
    # Status flags
    is_locked_out: bool = False
    lockout_reason: Optional[str] = None
    
    # Last update
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def exposure_utilization(self) -> float:
        """Exposure as percentage of limit"""
        if self.max_open_exposure == 0:
            return 0
        return (self.current_exposure / self.max_open_exposure) * 100
    
    @property
    def daily_loss_utilization(self) -> float:
        """Daily loss as percentage of limit"""
        if self.max_daily_loss == 0:
            return 0
        # Only count if we're in a loss
        loss = abs(min(0, self.daily_pnl))
        return (loss / self.max_daily_loss) * 100
    
    @property
    def trades_utilization(self) -> float:
        """Trades as percentage of daily limit"""
        if self.max_trades_per_day == 0:
            return 0
        return (self.trades_today / self.max_trades_per_day) * 100
    
    @property
    def can_trade(self) -> bool:
        """Whether trading is currently allowed"""
        if self.is_locked_out:
            return False
        if self.trades_today >= self.max_trades_per_day:
            return False
        if self.current_exposure >= self.max_open_exposure:
            return False
        if abs(min(0, self.daily_pnl)) >= self.max_daily_loss:
            return False
        return True
    
    def to_dict(self) -> dict:
        return {
            **self.dict(),
            'exposure_utilization': self.exposure_utilization,
            'daily_loss_utilization': self.daily_loss_utilization,
            'trades_utilization': self.trades_utilization,
            'can_trade': self.can_trade
        }
