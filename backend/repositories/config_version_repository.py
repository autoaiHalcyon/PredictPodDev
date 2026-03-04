"""
Config Version Repository

MongoDB repository for versioned strategy configurations.
Handles CRUD operations, version history, and rollback.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import uuid

from models.config_version import (
    ConfigVersion, ConfigDiff, ConfigChangeSource, 
    TunerProposal, TunerSettings, LeagueType
)

logger = logging.getLogger(__name__)


class ConfigVersionRepository:
    """Repository for config versions in MongoDB."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.configs = db.config_versions
        self.proposals = db.tuner_proposals
        self.settings = db.tuner_settings
    
    async def create_indexes(self):
        """Create database indexes."""
        await self.configs.create_index([("model_id", 1), ("league", 1), ("version_number", -1)])
        await self.configs.create_index([("model_id", 1), ("league", 1), ("is_active", 1)])
        await self.configs.create_index("version_id", unique=True)
        await self.proposals.create_index([("model_id", 1), ("league", 1), ("status", 1)])
        logger.info("Config version repository indexes created")
    
    # ==========================================
    # CONFIG VERSIONS
    # ==========================================
    
    async def save_config(self, config: ConfigVersion) -> ConfigVersion:
        """Save a new config version or update if exists."""
        # Generate ID if not set
        if not config.id:
            config.id = str(uuid.uuid4())
        
        # Generate version ID from version_number (must be set by caller)
        config.version_id = config.generate_version_id()
        
        # Check if this version_id already exists to avoid duplicate key error
        existing = await self.get_config_by_version_id(config.version_id)
        
        doc = config.to_dict()
        
        if existing:
            # Update the existing document instead of inserting
            logger.info(f"Config version already exists: {config.version_id}, updating...")
            result = await self.configs.update_one(
                {"version_id": config.version_id},
                {"$set": doc}
            )
            if result.matched_count == 0:
                raise RuntimeError(f"Failed to update existing config: {config.version_id}")
        else:
            # Save as new document
            try:
                await self.configs.insert_one(doc)
            except Exception as e:
                if "duplicate key error" in str(e).lower():
                    logger.warning(f"Duplicate key detected for {config.version_id}, attempting update...")
                    await self.configs.update_one(
                        {"version_id": config.version_id},
                        {"$set": doc}
                    )
                else:
                    raise
        
        logger.info(f"Saved config version: {config.version_id}")
        return config
    
    async def get_config_by_id(self, config_id: str) -> Optional[ConfigVersion]:
        """Get config by ID."""
        doc = await self.configs.find_one({"id": config_id})
        if doc:
            return ConfigVersion.from_dict(doc)
        return None
    
    async def get_config_by_version_id(self, version_id: str) -> Optional[ConfigVersion]:
        """Get config by version ID (e.g., MODEL_A_NBA_v0012)."""
        doc = await self.configs.find_one({"version_id": version_id})
        if doc:
            return ConfigVersion.from_dict(doc)
        return None
    
    async def get_latest_version(self, model_id: str, league: str) -> Optional[ConfigVersion]:
        """Get the latest version for a model/league."""
        doc = await self.configs.find_one(
            {"model_id": model_id, "league": league},
            sort=[("version_number", -1)]
        )
        if doc:
            return ConfigVersion.from_dict(doc)
        return None
    
    async def get_active_config(self, model_id: str, league: str) -> Optional[ConfigVersion]:
        """Get the currently active config for a model/league."""
        doc = await self.configs.find_one(
            {"model_id": model_id, "league": league, "is_active": True}
        )
        if doc:
            return ConfigVersion.from_dict(doc)
        return None
    
    async def get_version_history(
        self, 
        model_id: str, 
        league: str, 
        limit: int = 10
    ) -> List[ConfigVersion]:
        """Get version history for a model/league."""
        cursor = self.configs.find(
            {"model_id": model_id, "league": league}
        ).sort("version_number", -1).limit(limit)
        
        configs = []
        async for doc in cursor:
            configs.append(ConfigVersion.from_dict(doc))
        return configs
    
    async def activate_config(self, version_id: str) -> bool:
        """Activate a specific config version (deactivates others)."""
        # Get the config
        config = await self.get_config_by_version_id(version_id)
        if not config:
            logger.error(f"Config not found: {version_id}")
            return False
        
        # Deactivate all other versions for this model/league
        await self.configs.update_many(
            {"model_id": config.model_id, "league": config.league},
            {"$set": {"is_active": False}}
        )
        
        # Activate this version
        await self.configs.update_one(
            {"version_id": version_id},
            {"$set": {"is_active": True, "applied_at": datetime.utcnow().isoformat()}}
        )
        
        logger.info(f"Activated config: {version_id}")
        return True
    
    async def rollback_to_version(
        self, 
        model_id: str, 
        league: str, 
        target_version_id: str
    ) -> Optional[ConfigVersion]:
        """
        Rollback to a specific version by creating a new version 
        with the old config content.
        """
        # Get the target version
        target = await self.get_config_by_version_id(target_version_id)
        if not target:
            logger.error(f"Target version not found: {target_version_id}")
            return None
        
        # Get current active for diff
        current = await self.get_active_config(model_id, league)
        
        # Create new version with rollback content
        new_config = ConfigVersion(
            model_id=model_id,
            league=league,
            config=target.config.copy(),
            applied_by=ConfigChangeSource.ROLLBACK,
            change_summary=f"Rollback to {target_version_id}",
            diff_from_previous=self._compute_diff(
                current.config if current else {}, 
                target.config
            )
        )
        
        # Save and activate
        saved = await self.save_config(new_config)
        await self.activate_config(saved.version_id)
        
        logger.info(f"Rolled back {model_id}/{league} to {target_version_id}")
        return saved
    
    def _compute_diff(
        self, 
        old_config: Dict, 
        new_config: Dict,
        prefix: str = ""
    ) -> List[ConfigDiff]:
        """Compute diff between two configs."""
        diffs = []
        
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recurse into nested dicts
                diffs.extend(self._compute_diff(old_val, new_val, full_key))
            elif old_val != new_val:
                diffs.append(ConfigDiff(
                    parameter=full_key,
                    old_value=old_val,
                    new_value=new_val
                ))
        
        return diffs
    
    # ==========================================
    # TUNER PROPOSALS
    # ==========================================
    
    async def save_proposal(self, proposal: TunerProposal) -> TunerProposal:
        """Save a tuner proposal."""
        if not proposal.id:
            proposal.id = str(uuid.uuid4())
        
        doc = proposal.to_dict()
        await self.proposals.insert_one(doc)
        
        logger.info(f"Saved tuner proposal for {proposal.model_id}/{proposal.league}")
        return proposal
    
    async def get_pending_proposals(
        self, 
        model_id: Optional[str] = None,
        league: Optional[str] = None
    ) -> List[TunerProposal]:
        """Get pending proposals."""
        query = {"status": "pending"}
        if model_id:
            query["model_id"] = model_id
        if league:
            query["league"] = league
        
        cursor = self.proposals.find(query).sort("created_at", -1)
        
        proposals = []
        async for doc in cursor:
            doc.pop("_id", None)
            proposals.append(TunerProposal(**doc))
        return proposals
    
    async def update_proposal_status(
        self, 
        proposal_id: str, 
        status: str,
        rejected_reason: Optional[str] = None
    ):
        """Update proposal status."""
        update = {"status": status}
        if status == "applied":
            update["applied_at"] = datetime.utcnow().isoformat()
        if rejected_reason:
            update["rejected_reason"] = rejected_reason
        
        await self.proposals.update_one(
            {"id": proposal_id},
            {"$set": update}
        )
    
    # ==========================================
    # TUNER SETTINGS
    # ==========================================
    
    async def get_tuner_settings(self) -> TunerSettings:
        """Get global tuner settings."""
        doc = await self.settings.find_one({"_id": "global"})
        if doc:
            doc.pop("_id", None)
            return TunerSettings(**doc)
        return TunerSettings()
    
    async def save_tuner_settings(self, settings: TunerSettings):
        """Save tuner settings."""
        await self.settings.update_one(
            {"_id": "global"},
            {"$set": settings.to_dict()},
            upsert=True
        )
        logger.info("Saved tuner settings")
    
    # ==========================================
    # INITIALIZATION
    # ==========================================
    
    async def initialize_base_configs(self, strategy_configs: Dict[str, Dict]):
        """
        Initialize base configs from strategy JSON files.
        Only creates if no versions exist.
        """
        leagues = ["BASE", "NBA", "NCAA_M", "NCAA_W", "GENERIC"]
        
        for model_id, base_config in strategy_configs.items():
            for league in leagues:
                existing = await self.get_latest_version(model_id, league)
                if not existing:
                    # Create initial version
                    config = ConfigVersion(
                        model_id=model_id,
                        league=league,
                        config=base_config.copy() if league == "BASE" else {},
                        applied_by=ConfigChangeSource.INITIAL,
                        change_summary="Initial configuration",
                        is_active=(league == "BASE")  # Base is active by default
                    )
                    await self.save_config(config)
                    if league == "BASE":
                        await self.activate_config(config.version_id)
                    
                    logger.info(f"Initialized config: {model_id}/{league}")
