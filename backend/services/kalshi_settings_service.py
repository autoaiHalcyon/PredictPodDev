"""
Kalshi Settings Service
Handles credential management, validation, and trading mode switching.
"""
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from models.kalshi_settings import (
    KalshiSettings,
    KalshiCredentials,
    ValidationStatus,
    TradingMode,
    LiveTradingGuardrails
)
from repositories.settings_repository import SettingsRepository
from services.encryption_service import get_encryption_service
from adapters.kalshi.real_adapter import RealKalshiAdapter

logger = logging.getLogger(__name__)


class KalshiSettingsService:
    """
    Service for managing Kalshi API credentials and trading settings.
    Handles encryption, validation, and secure storage.
    """
    
    def __init__(self, settings_repo: SettingsRepository):
        self.settings_repo = settings_repo
        self.encryption = get_encryption_service()
        self._cached_adapter: Optional[RealKalshiAdapter] = None
    
    async def get_settings(self) -> KalshiSettings:
        """Get current Kalshi settings."""
        return await self.settings_repo.get_settings()
    
    async def get_settings_for_frontend(self) -> Dict[str, Any]:
        """
        Get settings safe for frontend exposure.
        NEVER exposes encrypted credentials or full keys.
        """
        settings = await self.get_settings()
        return settings.to_safe_dict()
    
    async def save_credentials(
        self,
        api_key: str,
        private_key: str
    ) -> Dict[str, Any]:
        """
        Save Kalshi API credentials securely.
        
        Args:
            api_key: Kalshi API key ID
            private_key: Kalshi private key (PEM format)
            
        Returns:
            Dict with save status
        """
        if not api_key or not private_key:
            raise ValueError("Both API key and private key are required")
        
        # Encrypt credentials
        encrypted_api_key = self.encryption.encrypt(api_key)
        encrypted_private_key = self.encryption.encrypt(private_key)
        
        # Create masked version for display
        masked_key = self.encryption.mask_key(api_key, show_chars=4)
        
        # Save to database
        credentials = await self.settings_repo.save_credentials(
            encrypted_api_key=encrypted_api_key,
            encrypted_private_key=encrypted_private_key,
            masked_key_last4=masked_key
        )
        
        # Clear cached adapter so it will be recreated with new credentials
        self._cached_adapter = None
        
        return {
            "success": True,
            "message": "Credentials saved successfully",
            "masked_key": masked_key,
            "validation_status": credentials.validation_status.value
        }
    
    async def delete_credentials(self) -> Dict[str, Any]:
        """Delete stored credentials."""
        await self.settings_repo.delete_credentials()
        self._cached_adapter = None
        
        return {
            "success": True,
            "message": "Credentials deleted successfully"
        }
    
    async def validate_credentials(self) -> Dict[str, Any]:
        """
        Validate stored credentials by making a test API call.
        
        Returns:
            Dict with validation result including:
            - valid: bool
            - message: str
            - balance: float (if valid)
        """
        settings = await self.get_settings()
        
        if not settings.credentials:
            return {
                "valid": False,
                "message": "No credentials stored"
            }
        
        # Update status to validating
        await self.settings_repo.update_validation_status(
            ValidationStatus.VALIDATING,
            "Validating credentials..."
        )
        
        try:
            # Decrypt credentials
            api_key = self.encryption.decrypt(settings.credentials.encrypted_api_key)
            private_key = self.encryption.decrypt(settings.credentials.encrypted_private_key)
            
            # Create adapter and validate
            adapter = RealKalshiAdapter(
                api_key=api_key,
                private_key=private_key,
                demo_mode=settings.demo_mode
            )
            
            result = await adapter.validate_credentials()
            await adapter.close()
            
            if result["valid"]:
                await self.settings_repo.update_validation_status(
                    ValidationStatus.VALID,
                    "API credentials validated successfully"
                )
                return {
                    "valid": True,
                    "message": result["message"],
                    "balance": result.get("balance", 0)
                }
            else:
                await self.settings_repo.update_validation_status(
                    ValidationStatus.INVALID,
                    result.get("message", "Invalid credentials")
                )
                return {
                    "valid": False,
                    "message": result.get("message", "Invalid credentials")
                }
        
        except ValueError as e:
            # Decryption failed
            await self.settings_repo.update_validation_status(
                ValidationStatus.ERROR,
                f"Decryption error: {str(e)}"
            )
            return {
                "valid": False,
                "message": f"Error decrypting credentials: {str(e)}"
            }
        
        except Exception as e:
            await self.settings_repo.update_validation_status(
                ValidationStatus.ERROR,
                f"Validation error: {str(e)}"
            )
            logger.error(f"Credential validation error: {e}")
            return {
                "valid": False,
                "message": f"Validation failed: {str(e)}"
            }
    
    async def enable_live_trading(
        self,
        confirmed_risk: bool
    ) -> Dict[str, Any]:
        """
        Enable live trading with user confirmation.
        
        Args:
            confirmed_risk: User must explicitly confirm understanding of risks
            
        Returns:
            Dict with result
        """
        if not confirmed_risk:
            return {
                "success": False,
                "message": "You must acknowledge the risk of live trading"
            }
        
        settings = await self.get_settings()
        
        # Check all prerequisites
        if not settings.credentials:
            return {
                "success": False,
                "message": "No API credentials configured"
            }
        
        if settings.credentials.validation_status != ValidationStatus.VALID:
            return {
                "success": False,
                "message": "API credentials not validated. Please validate first."
            }
        
        if settings.kill_switch_active:
            return {
                "success": False,
                "message": "Kill switch is active. Please deactivate first."
            }
        
        # Check server-level flag
        server_enabled = os.environ.get("LIVE_TRADING_ENABLED", "false").lower() == "true"
        if server_enabled:
            await self.settings_repo.set_server_live_trading(True)
        
        # Enable user toggle
        await self.settings_repo.set_user_live_trading(
            enabled=True,
            confirmed_risk=True
        )
        
        # Re-fetch to check effective status
        settings = await self.get_settings()
        
        if settings.is_live_trading_active:
            return {
                "success": True,
                "message": "LIVE TRADING ENABLED - Trading with real money",
                "trading_mode": TradingMode.LIVE.value
            }
        else:
            return {
                "success": False,
                "message": "Live trading prerequisites not met. Check server configuration.",
                "trading_mode": TradingMode.PAPER.value,
                "server_enabled": server_enabled
            }
    
    async def disable_live_trading(self) -> Dict[str, Any]:
        """Disable live trading and return to paper mode."""
        await self.settings_repo.set_user_live_trading(
            enabled=False,
            confirmed_risk=False
        )
        
        return {
            "success": True,
            "message": "Live trading disabled. Now in paper trading mode.",
            "trading_mode": TradingMode.PAPER.value
        }
    
    async def activate_kill_switch(self) -> Dict[str, Any]:
        """
        EMERGENCY: Activate kill switch to stop all live trading.
        """
        await self.settings_repo.activate_kill_switch()
        
        return {
            "success": True,
            "message": "KILL SWITCH ACTIVATED - All live trading stopped",
            "trading_mode": TradingMode.PAPER.value
        }
    
    async def deactivate_kill_switch(self) -> Dict[str, Any]:
        """Deactivate kill switch."""
        await self.settings_repo.deactivate_kill_switch()
        
        return {
            "success": True,
            "message": "Kill switch deactivated. Re-enable live trading to resume."
        }
    
    async def get_real_adapter(self) -> Optional[RealKalshiAdapter]:
        """
        Get a real Kalshi adapter if credentials are valid.
        Returns None if in paper mode or credentials invalid.
        """
        settings = await self.get_settings()
        
        if not settings.is_live_trading_active:
            return None
        
        if not settings.credentials:
            return None
        
        try:
            api_key = self.encryption.decrypt(settings.credentials.encrypted_api_key)
            private_key = self.encryption.decrypt(settings.credentials.encrypted_private_key)
            
            adapter = RealKalshiAdapter(
                api_key=api_key,
                private_key=private_key,
                demo_mode=settings.demo_mode
            )
            
            return adapter
        
        except Exception as e:
            logger.error(f"Failed to create real adapter: {e}")
            return None
    
    # ============================================
    # GUARDRAILS
    # ============================================
    
    async def get_guardrails(self) -> LiveTradingGuardrails:
        """Get current trading guardrails."""
        return await self.settings_repo.get_guardrails()
    
    async def update_guardrails(
        self,
        guardrails: LiveTradingGuardrails
    ) -> Dict[str, Any]:
        """Update trading guardrails."""
        await self.settings_repo.save_guardrails(guardrails)
        
        return {
            "success": True,
            "message": "Guardrails updated",
            "guardrails": guardrails.dict()
        }
    
    async def check_guardrails(
        self,
        trade_amount: float,
        current_exposure: float,
        daily_pnl: float,
        trades_this_hour: int,
        trades_today: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade passes all guardrails.
        
        Returns:
            Tuple of (passes, reason_if_blocked)
        """
        guardrails = await self.get_guardrails()
        
        if not guardrails.guardrails_enabled:
            return True, None
        
        # Check trade size
        if trade_amount > guardrails.max_dollars_per_trade:
            return False, f"Trade amount ${trade_amount:.2f} exceeds max ${guardrails.max_dollars_per_trade:.2f}"
        
        # Check exposure
        if current_exposure + trade_amount > guardrails.max_open_exposure:
            return False, f"Would exceed max exposure of ${guardrails.max_open_exposure:.2f}"
        
        # Check daily loss
        if daily_pnl < -guardrails.max_daily_loss:
            return False, f"Daily loss limit of ${guardrails.max_daily_loss:.2f} reached"
        
        # Check rate limits
        if trades_this_hour >= guardrails.max_trades_per_hour:
            return False, f"Hourly trade limit of {guardrails.max_trades_per_hour} reached"
        
        if trades_today >= guardrails.max_trades_per_day:
            return False, f"Daily trade limit of {guardrails.max_trades_per_day} reached"
        
        return True, None
    
    async def get_audit_log(self, limit: int = 100) -> list:
        """Get recent audit log entries."""
        return await self.settings_repo.get_audit_log(limit)
