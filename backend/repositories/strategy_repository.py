"""
Strategy Repository - MongoDB CRUD operations for user-created strategies.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from models.strategy import StrategyInDB, StrategyCreate, StrategyUpdate, resolve_model_id

logger = logging.getLogger(__name__)


class StrategyRepository:
    """Repository for strategy CRUD operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.strategies
    
    async def create_indexes(self):
        """Create necessary indexes."""
        await self.collection.create_index("strategy_key", unique=True)
        await self.collection.create_index("model_id")
        await self.collection.create_index("enabled")
        await self.collection.create_index("created_at")
        logger.info("Strategy repository indexes created")
    
    async def create(self, strategy: StrategyCreate) -> StrategyInDB:
        """Create a new strategy."""
        now = datetime.utcnow()
        
        # Ensure config_json has the correct model_id
        config = strategy.config_json.copy()
        config["model_id"] = resolve_model_id(strategy.model_id)
        config["display_name"] = strategy.display_name
        config["description"] = strategy.description
        config["enabled"] = strategy.enabled
        
        doc = {
            "strategy_key": strategy.strategy_key,
            "model_id": strategy.model_id,
            "display_name": strategy.display_name,
            "description": strategy.description,
            "enabled": strategy.enabled,
            "config_json": config,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        logger.info(f"Created strategy: {strategy.display_name} ({strategy.strategy_key})")
        return StrategyInDB(**doc)
    
    async def get_all(self, include_disabled: bool = False) -> List[StrategyInDB]:
        """Get all strategies."""
        query = {} if include_disabled else {"enabled": True}
        cursor = self.collection.find(query).sort("created_at", -1)
        
        strategies = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            strategies.append(StrategyInDB(**doc))
        
        return strategies
    
    async def get_enabled(self) -> List[StrategyInDB]:
        """Get all enabled strategies."""
        return await self.get_all(include_disabled=False)
    
    async def get_by_id(self, strategy_id: str) -> Optional[StrategyInDB]:
        """Get strategy by ID."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(strategy_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return StrategyInDB(**doc)
        except Exception as e:
            logger.error(f"Error getting strategy {strategy_id}: {e}")
        return None
    
    async def get_by_key(self, strategy_key: str) -> Optional[StrategyInDB]:
        """Get strategy by unique key."""
        doc = await self.collection.find_one({"strategy_key": strategy_key})
        if doc:
            doc["_id"] = str(doc["_id"])
            return StrategyInDB(**doc)
        return None
    
    async def update(self, strategy_id: str, updates: StrategyUpdate) -> Optional[StrategyInDB]:
        """Update a strategy."""
        update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
        
        if not update_data:
            return await self.get_by_id(strategy_id)
        
        update_data["updated_at"] = datetime.utcnow()
        
        # If config_json is being updated, sync display_name and description
        if "config_json" in update_data:
            config = update_data["config_json"]
            if "display_name" in update_data:
                config["display_name"] = update_data["display_name"]
            if "description" in update_data:
                config["description"] = update_data["description"]
            if "enabled" in update_data:
                config["enabled"] = update_data["enabled"]
        
        try:
            await self.collection.update_one(
                {"_id": ObjectId(strategy_id)},
                {"$set": update_data}
            )
            logger.info(f"Updated strategy {strategy_id}")
            return await self.get_by_id(strategy_id)
        except Exception as e:
            logger.error(f"Error updating strategy {strategy_id}: {e}")
            return None
    
    async def delete(self, strategy_id: str) -> bool:
        """Delete a strategy."""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(strategy_id)})
            if result.deleted_count > 0:
                logger.info(f"Deleted strategy {strategy_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting strategy {strategy_id}: {e}")
        return False
    
    async def toggle_enabled(self, strategy_id: str, enabled: bool) -> Optional[StrategyInDB]:
        """Toggle strategy enabled status."""
        return await self.update(strategy_id, StrategyUpdate(enabled=enabled))
    
    async def count(self, include_disabled: bool = False) -> int:
        """Count strategies."""
        query = {} if include_disabled else {"enabled": True}
        return await self.collection.count_documents(query)
    
    async def seed_default_strategies(self, default_configs: Dict[str, Dict]) -> int:
        """
        Seed database with default strategies from JSON configs.
        Only creates if strategies don't exist.
        Returns count of strategies created.
        """
        created = 0
        
        for config_key, config in default_configs.items():
            # Check if already exists
            existing = await self.get_by_key(config_key)
            if existing:
                continue
            
            # Create strategy from config
            strategy = StrategyCreate(
                strategy_key=config_key,
                model_id=config.get("model_id", "model_a_disciplined"),
                display_name=config.get("display_name", config_key),
                description=config.get("description", ""),
                enabled=config.get("enabled", True),
                config_json=config
            )
            
            await self.create(strategy)
            created += 1
        
        logger.info(f"Seeded {created} default strategies")
        return created
