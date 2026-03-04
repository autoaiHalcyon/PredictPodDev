"""
Position Model - Represents a user's position in a market.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Market reference
    game_id: str
    market_id: str
    
    # Position details
    side: str  # "yes" or "no"
    quantity: int = 0  # Number of contracts
    avg_entry_price: float = 0.0  # Average entry price
    
    # PnL tracking
    current_price: float = 0.0  # Current market price
    unrealized_pnl: float = 0.0  # Current unrealized PnL
    realized_pnl: float = 0.0  # Realized PnL from closed positions
    
    # Paper trading flag
    is_paper: bool = True
    
    # Risk metrics
    cost_basis: float = 0.0  # Total $ invested
    max_loss: float = 0.0  # Maximum possible loss
    max_profit: float = 0.0  # Maximum possible profit
    
    # Timestamps
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    @property
    def is_open(self) -> bool:
        return self.quantity > 0 and self.closed_at is None
    
    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl
    
    @property
    def roi_percent(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.total_pnl / self.cost_basis) * 100
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL based on current price"""
        self.current_price = current_price
        if self.side == "yes":
            self.unrealized_pnl = (current_price - self.avg_entry_price) * self.quantity
        else:  # "no" position
            self.unrealized_pnl = (self.avg_entry_price - current_price) * self.quantity
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            **self.dict(),
            'is_open': self.is_open,
            'total_pnl': self.total_pnl,
            'roi_percent': self.roi_percent
        }
