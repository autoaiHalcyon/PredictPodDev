"""
Tick Repository - Time-series data storage.
Optimized for time-series queries and future ML training data.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseRepository
from models.tick import ProbabilityTick, MarketTick

class TickRepository:
    """Repository for time-series tick data"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.prob_ticks = db.probability_ticks
        self.market_ticks = db.market_ticks
    
    # Probability Ticks
    async def create_prob_tick(self, tick: ProbabilityTick) -> ProbabilityTick:
        """Store a probability tick"""
        await self.prob_ticks.insert_one(tick.dict())
        return tick
    
    async def get_prob_ticks_for_game(
        self, 
        game_id: str, 
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[ProbabilityTick]:
        """Get probability ticks for a game within time range"""
        filters = {'game_id': game_id}
        if start_time:
            filters['timestamp'] = {'$gte': start_time}
        if end_time:
            filters.setdefault('timestamp', {})['$lte'] = end_time
        
        cursor = self.prob_ticks.find(filters).sort('timestamp', 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [ProbabilityTick(**doc) for doc in docs]
    
    async def get_latest_prob_tick(self, game_id: str) -> Optional[ProbabilityTick]:
        """Get the most recent probability tick for a game"""
        doc = await self.prob_ticks.find_one(
            {'game_id': game_id},
            sort=[('timestamp', -1)]
        )
        return ProbabilityTick(**doc) if doc else None
    
    # Market Ticks
    async def create_market_tick(self, tick: MarketTick) -> MarketTick:
        """Store a market tick"""
        await self.market_ticks.insert_one(tick.dict())
        return tick
    
    async def get_market_ticks_for_game(
        self,
        game_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[MarketTick]:
        """Get market ticks for a game within time range"""
        filters = {'game_id': game_id}
        if start_time:
            filters['timestamp'] = {'$gte': start_time}
        if end_time:
            filters.setdefault('timestamp', {})['$lte'] = end_time
        
        cursor = self.market_ticks.find(filters).sort('timestamp', 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [MarketTick(**doc) for doc in docs]
    
    async def get_latest_market_tick(self, market_id: str) -> Optional[MarketTick]:
        """Get the most recent market tick"""
        doc = await self.market_ticks.find_one(
            {'market_id': market_id},
            sort=[('timestamp', -1)]
        )
        return MarketTick(**doc) if doc else None
    
    # Analytics queries
    async def get_edge_distribution(self, game_id: str) -> Dict[str, float]:
        """Get edge statistics for a game"""
        pipeline = [
            {'$match': {'game_id': game_id}},
            {'$group': {
                '_id': None,
                'avg_edge': {'$avg': '$edge'},
                'max_edge': {'$max': '$edge'},
                'min_edge': {'$min': '$edge'},
                'count': {'$sum': 1}
            }}
        ]
        result = await self.prob_ticks.aggregate(pipeline).to_list(1)
        return result[0] if result else {}
    
    async def get_tick_count(self, collection: str = 'prob') -> int:
        """Get total tick count"""
        coll = self.prob_ticks if collection == 'prob' else self.market_ticks
        return await coll.count_documents({})
    
    # Cleanup
    async def cleanup_old_ticks(self, days: int = 30):
        """Remove ticks older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        await self.prob_ticks.delete_many({'timestamp': {'$lt': cutoff}})
        await self.market_ticks.delete_many({'timestamp': {'$lt': cutoff}})
