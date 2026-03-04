"""
Kalshi Settings Model
Stores encrypted API credentials and trading configuration.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class ValidationStatus(str, Enum):
    """Status of API credential validation."""
    NOT_VALIDATED = "not_validated"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


class TradingMode(str, Enum):
    """Current trading mode."""
    PAPER = "paper"
    LIVE = "live"


class KalshiCredentials(BaseModel):
    """
    Encrypted Kalshi API credentials stored in database.
    NEVER store decrypted credentials!
    """
    # Encrypted credentials (AES-GCM via Fernet)
    encrypted_api_key: str = ""
    encrypted_private_key: str = ""
    
    # Safe to expose to frontend
    masked_key_last4: str = ""
    
    # Validation tracking
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    validation_message: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KalshiSettings(BaseModel):
    """
    Complete Kalshi integration settings for a user.
    """
    # Credentials
    credentials: Optional[KalshiCredentials] = None
    
    # Trading mode - NEVER auto-enable live trading
    trading_mode: TradingMode = TradingMode.PAPER
    
    # Server-level flag - must be True to allow live trading
    server_live_trading_enabled: bool = False
    
    # User's manual live trading toggle - requires confirmation
    user_live_trading_enabled: bool = False
    
    # User acknowledged risk
    user_confirmed_risk: bool = False
    
    # Kill switch - instantly disables live trading
    kill_switch_active: bool = False
    
    # Demo mode flag (uses Kalshi demo API)
    demo_mode: bool = True
    
    @property
    def is_live_trading_active(self) -> bool:
        """
        Check if live trading should be active.
        ALL conditions must be met:
        1. Credentials exist and are validated
        2. Server-level flag is enabled
        3. User toggle is enabled
        4. User confirmed risk
        5. Kill switch is NOT active
        """
        if self.kill_switch_active:
            return False
        
        if not self.credentials:
            return False
        
        if self.credentials.validation_status != ValidationStatus.VALID:
            return False
        
        if not self.server_live_trading_enabled:
            return False
        
        if not self.user_live_trading_enabled:
            return False
        
        if not self.user_confirmed_risk:
            return False
        
        return True
    
    def get_effective_trading_mode(self) -> TradingMode:
        """Get the actual trading mode based on all conditions."""
        if self.is_live_trading_active:
            return TradingMode.LIVE
        return TradingMode.PAPER
    
    def to_safe_dict(self) -> dict:
        """
        Convert to dict safe for frontend exposure.
        NEVER expose encrypted credentials or full keys!
        """
        creds_info = None
        if self.credentials:
            creds_info = {
                "has_credentials": True,
                "masked_key_last4": self.credentials.masked_key_last4,
                "validation_status": self.credentials.validation_status.value,
                "validation_message": self.credentials.validation_message,
                "last_validated_at": self.credentials.last_validated_at.isoformat() if self.credentials.last_validated_at else None
            }
        
        return {
            "has_credentials": self.credentials is not None,
            "credentials_info": creds_info,
            "trading_mode": self.get_effective_trading_mode().value,
            "server_live_trading_enabled": self.server_live_trading_enabled,
            "user_live_trading_enabled": self.user_live_trading_enabled,
            "user_confirmed_risk": self.user_confirmed_risk,
            "kill_switch_active": self.kill_switch_active,
            "is_live_trading_active": self.is_live_trading_active,
            "demo_mode": self.demo_mode
        }


class LiveTradingGuardrails(BaseModel):
    """
    Trading guardrails - enforced before ANY live trade.
    """
    # Per-trade limits
    max_dollars_per_trade: float = 10.0
    
    # Exposure limits
    max_open_exposure: float = 100.0
    max_position_concentration_pct: float = 25.0  # Max % of balance in one position
    
    # Loss limits
    max_daily_loss: float = 50.0
    
    # Rate limits
    max_trades_per_hour: int = 20
    max_trades_per_day: int = 100
    
    # Order limits
    max_order_size_pct_of_liquidity: float = 10.0  # Max % of orderbook
    
    # Enabled flag
    guardrails_enabled: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_dollars_per_trade": 10.0,
                "max_open_exposure": 100.0,
                "max_daily_loss": 50.0,
                "max_trades_per_hour": 20,
                "max_trades_per_day": 100
            }
        }
