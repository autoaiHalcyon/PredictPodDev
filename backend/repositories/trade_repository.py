"""
Trade Repository - MongoDB implementation.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from .base import BaseRepository
from models.trade import Trade, TradeStatus

class TradeRepository(BaseRepository[Trade]):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.trades

    def _normalize_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert non-JSON-serializable Mongo types (e.g. ObjectId) to JSON-friendly types."""
        if not doc:
            return doc
        # Convert ObjectId to string so Pydantic / FastAPI can JSON-encode responses
        if "_id" in doc and doc["_id"] is not None:
            try:
                doc["_id"] = str(doc["_id"])
            except Exception:
                # If conversion fails, remove the field to avoid serialization errors
                doc.pop("_id", None)
        return doc
    
    async def create(self, trade: Trade) -> Trade:
        trade_dict = trade.dict()
        await self.collection.insert_one(trade_dict)
        return trade
    
    async def get_by_id(self, id: str) -> Optional[Trade]:
        doc = await self.collection.find_one({'id': id})
        if not doc:
            return None
        doc = self._normalize_doc(doc)
        try:
            return Trade(**doc)
        except Exception as e:
            # If there's a validation error, log it and still return a basic Trade
            import logging
            logging.error(f"Error creating Trade from doc: {e}, doc keys: {doc.keys()}")
            # Return None and let the caller handle it
            return None
    
    async def get_all(self, limit: int = 100, skip: int = 0) -> List[Trade]:
        cursor = self.collection.find().sort('created_at', -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Trade(**self._normalize_doc(doc)) for doc in docs]
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Trade]:
        result = await self.collection.update_one(
            {'id': id},
            {'$set': data}
        )
        # Return the updated document regardless of whether fields changed
        if result.matched_count:
            return await self.get_by_id(id)
        return None
    
    async def delete(self, id: str) -> bool:
        result = await self.collection.delete_one({'id': id})
        return result.deleted_count > 0
    
    async def find(self, filters: Dict[str, Any], limit: int = 100) -> List[Trade]:
        cursor = self.collection.find(filters).sort('created_at', -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Trade(**self._normalize_doc(doc)) for doc in docs]
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        return await self.collection.count_documents(filters or {})
    
    # Trade-specific queries
    async def get_trades_today(self) -> List[Trade]:
        """Get all trades from today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.find({'created_at': {'$gte': today_start}})
    
    async def count_trades_today(self) -> int:
        """Count trades placed today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.count({'created_at': {'$gte': today_start}})
    
    async def count_trades_last_hour(self) -> int:
        """Count trades in the last hour"""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        return await self.count({'created_at': {'$gte': hour_ago}})
    
    async def get_by_game_id(self, game_id: str) -> List[Trade]:
        """Get all trades for a game"""
        return await self.find({'game_id': game_id})
    
    async def get_daily_pnl(self) -> float:
        """Calculate realized PnL for today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        pipeline = [
            {'$match': {
                'status': TradeStatus.FILLED,
                'executed_at': {'$gte': today_start}
            }},
            {'$group': {'_id': None, 'total_pnl': {'$sum': '$realized_pnl'}}}
        ]
        result = await self.collection.aggregate(pipeline).to_list(1)
        return result[0]['total_pnl'] if result else 0.0
