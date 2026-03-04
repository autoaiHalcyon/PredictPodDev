"""
Live Trade Audit Log Model
Immutable record of all live trades for compliance.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LiveTradeAuditEntry(BaseModel):
    """
    Immutable audit log entry for live trades.
    Logs every trade with full context for compliance.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Trade identification
    order_id: str
    client_order_id: Optional[str] = None  # Idempotency key
    
    # Market context
    market_id: str
    market_ticker: str
    game_id: Optional[str] = None
    
    # Trade details
    side: str  # "yes" or "no"
    action: str  # "buy" or "sell"
    order_type: str  # "market" or "limit"
    quantity: int
    price_cents: int  # Price in cents (0-100)
    
    # Model context at time of trade
    fair_prob: Optional[float] = None
    market_prob: Optional[float] = None
    edge: Optional[float] = None
    signal_score: Optional[int] = None
    
    # Execution details
    status: str  # "pending", "filled", "partial", "canceled", "rejected"
    fill_price_cents: Optional[int] = None
    filled_quantity: int = 0
    
    # Financial impact
    cost_basis_cents: int = 0
    fees_cents: int = 0
    realized_pnl_cents: Optional[int] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    
    # Risk context
    pre_trade_exposure_cents: int = 0
    post_trade_exposure_cents: int = 0
    daily_pnl_before_cents: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "order_123",
                "market_id": "KXNBA-LAL-BOS",
                "market_ticker": "KXNBA-LAL-BOS",
                "side": "yes",
                "action": "buy",
                "order_type": "limit",
                "quantity": 10,
                "price_cents": 45,
                "fair_prob": 0.52,
                "market_prob": 0.45,
                "edge": 0.07,
                "signal_score": 78,
                "status": "filled",
                "fill_price_cents": 45,
                "filled_quantity": 10
            }
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.dict()
