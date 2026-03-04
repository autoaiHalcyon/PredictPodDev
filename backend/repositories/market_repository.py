"""
Market Repository - MongoDB implementation.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseRepository
from models.market import Market

class MarketRepository(BaseRepository[Market]):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.markets
    
    async def create(self, market: Market) -> Market:
        market_dict = market.dict()
        market_dict['last_updated'] = datetime.utcnow()
        await self.collection.insert_one(market_dict)
        return market
    
    async def get_by_id(self, id: str) -> Optional[Market]:
        doc = await self.collection.find_one({'id': id})
        return Market(**doc) if doc else None
    
    async def get_all(self, limit: int = 100, skip: int = 0) -> List[Market]:
        cursor = self.collection.find().skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Market(**doc) for doc in docs]
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Market]:
        data['last_updated'] = datetime.utcnow()
        result = await self.collection.update_one(
            {'id': id},
            {'$set': data}
        )
        if result.modified_count:
            return await self.get_by_id(id)
        return None
    
    async def delete(self, id: str) -> bool:
        result = await self.collection.delete_one({'id': id})
        return result.deleted_count > 0
    
    async def find(self, filters: Dict[str, Any], limit: int = 100) -> List[Market]:
        cursor = self.collection.find(filters).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Market(**doc) for doc in docs]
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        return await self.collection.count_documents(filters or {})
    
    # Market-specific queries
    async def get_by_game_id(self, game_id: str) -> List[Market]:
        """Get all markets for a game"""
        return await self.find({'game_id': game_id})
    
    async def get_active_markets(self) -> List[Market]:
        """Get all active (unsettled) markets"""
        return await self.find({'is_active': True, 'settled': False})
    
    async def upsert_by_game_and_outcome(self, market: Market) -> Market:
        """Insert or update market by game_id and outcome"""
        market_dict = market.dict()
        market_dict['last_updated'] = datetime.utcnow()
        await self.collection.update_one(
            {'game_id': market.game_id, 'outcome': market.outcome},
            {'$set': market_dict},
            upsert=True
        )
        return market
