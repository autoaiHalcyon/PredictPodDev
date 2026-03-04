"""
Capital Deployment Mode Model
Safety settings for live trading with CONSERVATIVE/NORMAL/AGGRESSIVE modes.
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class CapitalDeploymentMode(str, Enum):
    """
    Trading aggressiveness level.
    CONSERVATIVE is DEFAULT and REQUIRED for initial live trading.
    """
    CONSERVATIVE = "conservative"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"


class CapitalDeploymentSettings(BaseModel):
    """
    Settings for each capital deployment mode.
    Server-side enforced - cannot be bypassed by frontend.
    """
    mode: CapitalDeploymentMode = CapitalDeploymentMode.CONSERVATIVE
    
    # Per-trade limits (in cents for precision)
    max_trade_size_cents: int = 500  # $5 default (conservative)
    
    # Daily limits
    max_daily_loss_cents: int = 2500  # $25 default (conservative)
    max_daily_profit_take_cents: int = 10000  # $100 - lock profits
    
    # Exposure limits
    max_total_exposure_cents: int = 5000  # $50 max exposure (conservative)
    max_single_position_pct: float = 50.0  # Max % of exposure in one position
    
    # Liquidity limits
    max_order_pct_of_book: float = 5.0  # Block if order > 5% of top-of-book
    max_spread_cents: int = 10  # Warn if spread > 10¢
    
    # Rate limits
    max_orders_per_minute: int = 5
    max_orders_per_hour: int = 20
    
    # Confirmation requirements
    requires_double_confirmation: bool = False
    requires_explicit_acknowledgment: bool = False
    
    # Timestamps
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def conservative(cls) -> "CapitalDeploymentSettings":
        """Factory for CONSERVATIVE mode - safest settings."""
        return cls(
            mode=CapitalDeploymentMode.CONSERVATIVE,
            max_trade_size_cents=500,        # $5 per trade
            max_daily_loss_cents=2500,       # $25 daily loss cap
            max_total_exposure_cents=5000,   # $50 max exposure
            max_single_position_pct=50.0,
            max_order_pct_of_book=5.0,
            max_spread_cents=10,
            max_orders_per_minute=5,
            max_orders_per_hour=20,
            requires_double_confirmation=False,
            requires_explicit_acknowledgment=False
        )
    
    @classmethod
    def normal(cls) -> "CapitalDeploymentSettings":
        """Factory for NORMAL mode - standard settings."""
        return cls(
            mode=CapitalDeploymentMode.NORMAL,
            max_trade_size_cents=2500,       # $25 per trade
            max_daily_loss_cents=10000,      # $100 daily loss cap
            max_total_exposure_cents=25000,  # $250 max exposure
            max_single_position_pct=33.0,
            max_order_pct_of_book=10.0,
            max_spread_cents=15,
            max_orders_per_minute=10,
            max_orders_per_hour=50,
            requires_double_confirmation=False,
            requires_explicit_acknowledgment=False
        )
    
    @classmethod
    def aggressive(cls) -> "CapitalDeploymentSettings":
        """Factory for AGGRESSIVE mode - requires double confirmation."""
        return cls(
            mode=CapitalDeploymentMode.AGGRESSIVE,
            max_trade_size_cents=10000,      # $100 per trade
            max_daily_loss_cents=50000,      # $500 daily loss cap
            max_total_exposure_cents=100000, # $1000 max exposure
            max_single_position_pct=25.0,
            max_order_pct_of_book=15.0,
            max_spread_cents=20,
            max_orders_per_minute=20,
            max_orders_per_hour=100,
            requires_double_confirmation=True,
            requires_explicit_acknowledgment=True
        )
    
    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "max_trade_size_dollars": self.max_trade_size_cents / 100,
            "max_daily_loss_dollars": self.max_daily_loss_cents / 100,
            "max_total_exposure_dollars": self.max_total_exposure_cents / 100,
            "max_single_position_pct": self.max_single_position_pct,
            "max_order_pct_of_book": self.max_order_pct_of_book,
            "max_spread_cents": self.max_spread_cents,
            "max_orders_per_minute": self.max_orders_per_minute,
            "max_orders_per_hour": self.max_orders_per_hour,
            "requires_double_confirmation": self.requires_double_confirmation,
            "requires_explicit_acknowledgment": self.requires_explicit_acknowledgment
        }


class TradeConfirmation(BaseModel):
    """
    Pre-trade confirmation display data.
    Must be shown before every live order.
    """
    # Account state
    account_balance_cents: int
    buying_power_cents: int
    today_realized_pnl_cents: int
    today_open_risk_cents: int
    
    # Order details
    order_side: str
    order_action: str
    order_quantity: int
    order_price_cents: int
    order_total_cents: int
    
    # Risk analysis
    max_loss_cents: int
    worst_case_loss_cents: int
    daily_risk_utilization_pct: float
    exposure_after_trade_cents: int
    exposure_utilization_pct: float
    
    # Liquidity check
    orderbook_depth: int
    spread_cents: int
    order_pct_of_book: float
    liquidity_warning: bool = False
    liquidity_blocked: bool = False
    
    # Capital deployment check
    within_trade_limit: bool
    within_daily_loss_limit: bool
    within_exposure_limit: bool
    within_rate_limit: bool
    all_checks_passed: bool
    
    # Blocking reasons (if any)
    blocking_reasons: list = Field(default_factory=list)
    warning_reasons: list = Field(default_factory=list)
    
    # Confirmation requirements
    requires_double_confirmation: bool = False
    requires_explicit_acknowledgment: bool = False
    
    def to_dict(self) -> dict:
        return {
            "account": {
                "balance_dollars": self.account_balance_cents / 100,
                "buying_power_dollars": self.buying_power_cents / 100,
                "today_realized_pnl_dollars": self.today_realized_pnl_cents / 100,
                "today_open_risk_dollars": self.today_open_risk_cents / 100
            },
            "order": {
                "side": self.order_side,
                "action": self.order_action,
                "quantity": self.order_quantity,
                "price_cents": self.order_price_cents,
                "total_dollars": self.order_total_cents / 100
            },
            "risk": {
                "max_loss_dollars": self.max_loss_cents / 100,
                "worst_case_loss_dollars": self.worst_case_loss_cents / 100,
                "daily_risk_utilization_pct": round(self.daily_risk_utilization_pct, 1),
                "exposure_after_dollars": self.exposure_after_trade_cents / 100,
                "exposure_utilization_pct": round(self.exposure_utilization_pct, 1)
            },
            "liquidity": {
                "orderbook_depth": self.orderbook_depth,
                "spread_cents": self.spread_cents,
                "order_pct_of_book": round(self.order_pct_of_book, 1),
                "warning": self.liquidity_warning,
                "blocked": self.liquidity_blocked
            },
            "checks": {
                "within_trade_limit": self.within_trade_limit,
                "within_daily_loss_limit": self.within_daily_loss_limit,
                "within_exposure_limit": self.within_exposure_limit,
                "within_rate_limit": self.within_rate_limit,
                "all_passed": self.all_checks_passed
            },
            "blocking_reasons": self.blocking_reasons,
            "warning_reasons": self.warning_reasons,
            "requires_double_confirmation": self.requires_double_confirmation,
            "requires_explicit_acknowledgment": self.requires_explicit_acknowledgment
        }
