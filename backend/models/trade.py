"""
Trade Model - Represents a trade/order.
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class TradeStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CLOSED = "closed"

class TradeSide(str, Enum):
    YES = "yes"
    NO = "no"

class TradeDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"

class Trade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Market reference
    game_id: str
    market_id: str
    
    # Trade details
    side: TradeSide
    direction: TradeDirection
    quantity: int  # Number of contracts
    price: float  # Execution price (0.00 - 1.00)
    
    # Order details
    order_type: str = "market"  # market, limit
    limit_price: Optional[float] = None
    
    # Status
    status: TradeStatus = TradeStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    
    # Fees (Kalshi charges ~$0.01 per contract)
    fees: float = 0.0
    
    # Paper trading
    is_paper: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    
    # Signal that triggered the trade (for audit)
    signal_type: Optional[str] = None
    edge_at_entry: Optional[float] = None
    
    # Extended fields (for frontend display and analytics)
    type: Optional[str] = None  # 'manual' | 'auto-edge' | 'signal' | 'live'
    strategy: Optional[str] = None
    market_name: Optional[str] = None
    game_title: Optional[str] = None
    league: Optional[str] = None
    current_price: Optional[float] = None
    exit_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    pnl: float = 0.0
    realized_pnl: float = 0.0
    
    class Config:
        extra = 'allow'  # Allow extra fields from MongoDB
    
    @property
    def notional_value(self) -> float:
        """Total $ value of the trade"""
        return self.quantity * self.price
    
    @property
    def max_loss(self) -> float:
        """Maximum possible loss on this trade"""
        if self.direction == TradeDirection.BUY:
            return self.notional_value  # Can lose entire investment
        else:  # SELL
            return self.quantity * (1 - self.price)  # Can lose if settles at 1
    
    @property
    def max_profit(self) -> float:
        """Maximum possible profit on this trade"""
        if self.direction == TradeDirection.BUY:
            return self.quantity * (1 - self.price)  # Profit if settles at 1
        else:  # SELL
            return self.notional_value  # Profit if settles at 0
    
    def to_dict(self) -> dict:
        return {
            **self.dict(),
            'notional_value': self.notional_value,
            'max_loss': self.max_loss,
            'max_profit': self.max_profit
        }
