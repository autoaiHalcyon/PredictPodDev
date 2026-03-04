"""
Game Repository - MongoDB implementation.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseRepository
from models.game import Game, GameStatus

class GameRepository(BaseRepository[Game]):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.games
    
    async def create(self, game: Game) -> Game:
        game_dict = game.dict()
        game_dict['last_updated'] = datetime.utcnow()
        await self.collection.insert_one(game_dict)
        return game
    
    async def get_by_id(self, id: str) -> Optional[Game]:
        doc = await self.collection.find_one({'id': id})
        return Game(**doc) if doc else None
    
    async def get_all(self, limit: int = 100, skip: int = 0) -> List[Game]:
        cursor = self.collection.find().skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Game(**doc) for doc in docs]
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Game]:
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
    
    async def find(self, filters: Dict[str, Any], limit: int = 100) -> List[Game]:
        cursor = self.collection.find(filters).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Game(**doc) for doc in docs]
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        return await self.collection.count_documents(filters or {})
    
    # Game-specific queries
    async def get_live_games(self) -> List[Game]:
        """Get all currently live games"""
        return await self.find({'status': GameStatus.LIVE})
    
    async def get_upcoming_games(self, hours_ahead: int = 24) -> List[Game]:
        """Get games starting in the next N hours"""
        from datetime import timedelta
        now = datetime.utcnow()
        future = now + timedelta(hours=hours_ahead)
        return await self.find({
            'status': GameStatus.SCHEDULED,
            'start_time': {'$gte': now, '$lte': future}
        })
    
    async def get_by_espn_id(self, espn_id: str) -> Optional[Game]:
        """Get game by ESPN ID"""
        doc = await self.collection.find_one({'espn_id': espn_id})
        return Game(**doc) if doc else None
    
    async def upsert_by_espn_id(self, game: Game) -> Game:
        """Insert or update game by ESPN ID"""
        game_dict = game.dict()
        game_dict['last_updated'] = datetime.utcnow()
        await self.collection.update_one(
            {'espn_id': game.espn_id},
            {'$set': game_dict},
            upsert=True
        )
        return game
