"""
Order Lifecycle Model
Complete order state machine with 7 states for institutional-grade tracking.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class OrderState(str, Enum):
    """
    7-state order lifecycle.
    Transitions: SUBMITTED -> ACKNOWLEDGED -> PARTIAL/FILLED/REJECTED/CANCELLED/EXPIRED
    """
    SUBMITTED = "submitted"      # Order sent to exchange
    ACKNOWLEDGED = "acknowledged"  # Exchange confirmed receipt
    PARTIAL = "partial"          # Partially filled
    FILLED = "filled"            # Fully filled
    REJECTED = "rejected"        # Exchange rejected order
    CANCELLED = "cancelled"      # User cancelled
    EXPIRED = "expired"          # Time limit expired


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    YES = "yes"
    NO = "no"


class OrderAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStateTransition(BaseModel):
    """Record of state change for audit."""
    from_state: Optional[OrderState] = None
    to_state: OrderState
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderFill(BaseModel):
    """Individual fill event."""
    fill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quantity: int
    price_cents: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_taker: bool = False
    fee_cents: int = 0


class LiveOrder(BaseModel):
    """
    Complete order record with full lifecycle tracking.
    Persisted to MongoDB for crash recovery.
    """
    # Identification
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str  # REQUIRED - prevents duplicates
    client_order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange_order_id: Optional[str] = None  # Set by exchange
    
    # Order details
    market_id: str
    market_ticker: str
    game_id: Optional[str] = None
    side: OrderSide
    action: OrderAction
    order_type: OrderType = OrderType.LIMIT
    
    # Quantities
    quantity: int
    filled_quantity: int = 0
    remaining_quantity: int = 0
    
    # Pricing (in cents, 0-100)
    price_cents: int  # Limit price
    avg_fill_price_cents: int = 0
    expected_fill_price_cents: Optional[int] = None  # For slippage tracking
    
    # State machine
    state: OrderState = OrderState.SUBMITTED
    state_history: List[OrderStateTransition] = Field(default_factory=list)
    
    # Fills
    fills: List[OrderFill] = Field(default_factory=list)
    
    # Risk context at submission
    pre_order_balance_cents: int = 0
    pre_order_exposure_cents: int = 0
    pre_order_daily_pnl_cents: int = 0
    
    # Slippage & liquidity
    orderbook_depth_at_submission: int = 0
    spread_at_submission_cents: int = 0
    liquidity_check_passed: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Trading mode
    adapter_mode: str = "sandbox"  # mock, sandbox, real
    capital_deployment_mode: str = "conservative"
    
    # Reconciliation
    reconciled: bool = False
    reconciled_at: Optional[datetime] = None
    reconciliation_mismatch: bool = False
    reconciliation_notes: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self.remaining_quantity = self.quantity - self.filled_quantity
    
    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state."""
        return self.state in [
            OrderState.FILLED,
            OrderState.REJECTED,
            OrderState.CANCELLED,
            OrderState.EXPIRED
        ]
    
    @property
    def is_working(self) -> bool:
        """Check if order is still working."""
        return self.state in [
            OrderState.SUBMITTED,
            OrderState.ACKNOWLEDGED,
            OrderState.PARTIAL
        ]
    
    @property
    def slippage_cents(self) -> int:
        """Calculate slippage from expected fill price."""
        if self.avg_fill_price_cents == 0 or self.expected_fill_price_cents is None:
            return 0
        return abs(self.avg_fill_price_cents - self.expected_fill_price_cents)
    
    @property
    def total_cost_cents(self) -> int:
        """Total cost of filled quantity."""
        return self.filled_quantity * self.avg_fill_price_cents
    
    @property
    def total_fees_cents(self) -> int:
        """Total fees from all fills."""
        return sum(f.fee_cents for f in self.fills)
    
    def transition_to(self, new_state: OrderState, reason: Optional[str] = None, metadata: Dict = None):
        """
        Transition order to new state with audit trail.
        """
        if self.is_terminal and new_state != self.state:
            raise ValueError(f"Cannot transition from terminal state {self.state}")
        
        transition = OrderStateTransition(
            from_state=self.state,
            to_state=new_state,
            reason=reason,
            metadata=metadata or {}
        )
        
        self.state_history.append(transition)
        self.state = new_state
        
        # Update timestamps
        if new_state == OrderState.ACKNOWLEDGED:
            self.acknowledged_at = datetime.utcnow()
        elif new_state == OrderState.FILLED:
            self.filled_at = datetime.utcnow()
        elif new_state == OrderState.CANCELLED:
            self.cancelled_at = datetime.utcnow()
    
    def add_fill(self, fill: OrderFill):
        """Add a fill and update quantities."""
        self.fills.append(fill)
        self.filled_quantity += fill.quantity
        self.remaining_quantity = self.quantity - self.filled_quantity
        
        # Recalculate average fill price
        total_value = sum(f.quantity * f.price_cents for f in self.fills)
        if self.filled_quantity > 0:
            self.avg_fill_price_cents = total_value // self.filled_quantity
        
        # Update state
        if self.filled_quantity >= self.quantity:
            self.transition_to(OrderState.FILLED, "Fully filled")
        elif self.filled_quantity > 0:
            self.transition_to(OrderState.PARTIAL, f"Partial fill: {fill.quantity} @ {fill.price_cents}¢")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "idempotency_key": self.idempotency_key,
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "market_id": self.market_id,
            "market_ticker": self.market_ticker,
            "side": self.side.value,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "price_cents": self.price_cents,
            "avg_fill_price_cents": self.avg_fill_price_cents,
            "state": self.state.value,
            "is_terminal": self.is_terminal,
            "is_working": self.is_working,
            "slippage_cents": self.slippage_cents,
            "total_cost_cents": self.total_cost_cents,
            "total_fees_cents": self.total_fees_cents,
            "fills_count": len(self.fills),
            "adapter_mode": self.adapter_mode,
            "capital_deployment_mode": self.capital_deployment_mode,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "reconciled": self.reconciled,
            "reconciliation_mismatch": self.reconciliation_mismatch
        }


class PositionReconciliation(BaseModel):
    """Result of position reconciliation check."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    market_id: str
    
    # Local state
    local_quantity: int
    local_side: str
    local_avg_price_cents: int
    
    # Adapter-reported state
    adapter_quantity: int
    adapter_side: str
    adapter_avg_price_cents: int
    
    # Comparison
    quantity_match: bool
    side_match: bool
    price_match: bool
    fully_reconciled: bool
    
    # Mismatch details
    mismatch_type: Optional[str] = None  # "quantity", "side", "missing_local", "missing_remote"
    mismatch_severity: str = "none"  # "none", "warning", "critical"
    
    # Timestamps
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "local_quantity": self.local_quantity,
            "adapter_quantity": self.adapter_quantity,
            "fully_reconciled": self.fully_reconciled,
            "mismatch_type": self.mismatch_type,
            "mismatch_severity": self.mismatch_severity,
            "checked_at": self.checked_at.isoformat()
        }
