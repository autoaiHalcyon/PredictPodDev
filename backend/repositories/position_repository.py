"""
Position Repository - MongoDB implementation.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseRepository
from models.position import Position

class PositionRepository(BaseRepository[Position]):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.positions
    
    async def create(self, position: Position) -> Position:
        position_dict = position.dict()
        position_dict['last_updated'] = datetime.utcnow()
        await self.collection.insert_one(position_dict)
        return position
    
    async def get_by_id(self, id: str) -> Optional[Position]:
        doc = await self.collection.find_one({'id': id})
        return Position(**doc) if doc else None
    
    async def get_all(self, limit: int = 100, skip: int = 0) -> List[Position]:
        cursor = self.collection.find().skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Position(**doc) for doc in docs]
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Position]:
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
    
    async def find(self, filters: Dict[str, Any], limit: int = 100) -> List[Position]:
        cursor = self.collection.find(filters).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Position(**doc) for doc in docs]
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        return await self.collection.count_documents(filters or {})
    
    # Position-specific queries
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return await self.find({'closed_at': None, 'quantity': {'$gt': 0}})
    
    async def get_by_game_id(self, game_id: str) -> List[Position]:
        """Get positions for a specific game"""
        return await self.find({'game_id': game_id})
    
    async def get_by_market_id(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        docs = await self.find({'market_id': market_id}, limit=1)
        return docs[0] if docs else None
    
    async def get_total_exposure(self) -> float:
        """Get total exposure across all open positions"""
        pipeline = [
            {'$match': {'closed_at': None, 'quantity': {'$gt': 0}}},
            {'$group': {'_id': None, 'total': {'$sum': '$cost_basis'}}}
        ]
        result = await self.collection.aggregate(pipeline).to_list(1)
        return result[0]['total'] if result else 0.0
