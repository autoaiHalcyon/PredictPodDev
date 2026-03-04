"""
Settings Repository
Handles storage and retrieval of Kalshi settings and credentials.
"""
from datetime import datetime
from typing import Optional
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.kalshi_settings import (
    KalshiSettings, 
    KalshiCredentials, 
    ValidationStatus,
    TradingMode,
    LiveTradingGuardrails
)

logger = logging.getLogger(__name__)


class SettingsRepository:
    """
    Repository for Kalshi settings management.
    Handles encrypted credential storage.
    """
    
    SETTINGS_COLLECTION = "kalshi_settings"
    GUARDRAILS_COLLECTION = "trading_guardrails"
    AUDIT_LOG_COLLECTION = "trading_audit_log"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.settings_col = db[self.SETTINGS_COLLECTION]
        self.guardrails_col = db[self.GUARDRAILS_COLLECTION]
        self.audit_col = db[self.AUDIT_LOG_COLLECTION]
    
    async def get_settings(self) -> KalshiSettings:
        """
        Get current Kalshi settings.
        Returns default settings if none exist.
        """
        doc = await self.settings_col.find_one({"_id": "default"})
        
        if not doc:
            return KalshiSettings()
        
        # Remove MongoDB _id before converting
        doc.pop("_id", None)
        
        # Parse credentials if present
        creds_data = doc.pop("credentials", None)
        credentials = None
        if creds_data:
            credentials = KalshiCredentials(**creds_data)
        
        settings = KalshiSettings(credentials=credentials, **doc)
        return settings
    
    async def save_credentials(
        self,
        encrypted_api_key: str,
        encrypted_private_key: str,
        masked_key_last4: str
    ) -> KalshiCredentials:
        """
        Save encrypted API credentials.
        """
        now = datetime.utcnow()
        credentials = KalshiCredentials(
            encrypted_api_key=encrypted_api_key,
            encrypted_private_key=encrypted_private_key,
            masked_key_last4=masked_key_last4,
            validation_status=ValidationStatus.NOT_VALIDATED,
            created_at=now,
            updated_at=now
        )
        
        # Update settings with new credentials
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "credentials": credentials.dict(),
                    "user_live_trading_enabled": False,  # Reset toggle
                    "user_confirmed_risk": False  # Reset confirmation
                }
            },
            upsert=True
        )
        
        # Log the credential update
        await self._log_audit_event("CREDENTIALS_SAVED", {
            "masked_key": masked_key_last4
        })
        
        logger.info(f"Kalshi credentials saved (masked: {masked_key_last4})")
        return credentials
    
    async def delete_credentials(self) -> bool:
        """
        Delete stored credentials and disable live trading.
        """
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "credentials": None,
                    "trading_mode": TradingMode.PAPER.value,
                    "user_live_trading_enabled": False,
                    "user_confirmed_risk": False
                }
            },
            upsert=True
        )
        
        await self._log_audit_event("CREDENTIALS_DELETED", {})
        logger.info("Kalshi credentials deleted")
        return True
    
    async def update_validation_status(
        self,
        status: ValidationStatus,
        message: Optional[str] = None
    ) -> None:
        """
        Update credential validation status.
        """
        now = datetime.utcnow()
        
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "credentials.validation_status": status.value,
                    "credentials.validation_message": message,
                    "credentials.last_validated_at": now,
                    "credentials.updated_at": now
                }
            }
        )
        
        await self._log_audit_event("VALIDATION_STATUS_UPDATED", {
            "status": status.value,
            "message": message
        })
        
        logger.info(f"Validation status updated: {status.value}")
    
    async def set_user_live_trading(
        self,
        enabled: bool,
        confirmed_risk: bool = False
    ) -> None:
        """
        Set user's live trading toggle.
        Both enabled and confirmed_risk must be True for live trading.
        """
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "user_live_trading_enabled": enabled,
                    "user_confirmed_risk": confirmed_risk
                }
            },
            upsert=True
        )
        
        await self._log_audit_event("LIVE_TRADING_TOGGLE", {
            "enabled": enabled,
            "confirmed_risk": confirmed_risk
        })
        
        logger.info(f"Live trading toggle: enabled={enabled}, confirmed={confirmed_risk}")
    
    async def activate_kill_switch(self) -> None:
        """
        Activate kill switch - immediately stops all live trading.
        """
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "kill_switch_active": True,
                    "user_live_trading_enabled": False
                }
            },
            upsert=True
        )
        
        await self._log_audit_event("KILL_SWITCH_ACTIVATED", {})
        logger.warning("KILL SWITCH ACTIVATED - Live trading disabled")
    
    async def deactivate_kill_switch(self) -> None:
        """
        Deactivate kill switch (requires manual user re-enable).
        """
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "kill_switch_active": False
                }
            },
            upsert=True
        )
        
        await self._log_audit_event("KILL_SWITCH_DEACTIVATED", {})
        logger.info("Kill switch deactivated")
    
    async def set_server_live_trading(self, enabled: bool) -> None:
        """
        Set server-level live trading flag.
        This is typically controlled by environment variable.
        """
        await self.settings_col.update_one(
            {"_id": "default"},
            {
                "$set": {
                    "server_live_trading_enabled": enabled
                }
            },
            upsert=True
        )
        
        await self._log_audit_event("SERVER_LIVE_TRADING_SET", {
            "enabled": enabled
        })
        
        logger.info(f"Server live trading set to: {enabled}")
    
    # ============================================
    # GUARDRAILS
    # ============================================
    
    async def get_guardrails(self) -> LiveTradingGuardrails:
        """Get current trading guardrails."""
        doc = await self.guardrails_col.find_one({"_id": "default"})
        
        if not doc:
            return LiveTradingGuardrails()
        
        doc.pop("_id", None)
        return LiveTradingGuardrails(**doc)
    
    async def save_guardrails(self, guardrails: LiveTradingGuardrails) -> None:
        """Save trading guardrails."""
        await self.guardrails_col.update_one(
            {"_id": "default"},
            {"$set": guardrails.dict()},
            upsert=True
        )
        
        await self._log_audit_event("GUARDRAILS_UPDATED", guardrails.dict())
        logger.info("Trading guardrails updated")
    
    # ============================================
    # AUDIT LOG
    # ============================================
    
    async def _log_audit_event(
        self,
        event_type: str,
        details: dict
    ) -> None:
        """Log an audit event for compliance tracking."""
        await self.audit_col.insert_one({
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.utcnow()
        })
    
    async def get_audit_log(self, limit: int = 100) -> list:
        """Get recent audit log entries."""
        cursor = self.audit_col.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
