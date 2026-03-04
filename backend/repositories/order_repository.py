"""
Order Repository
Persistent storage for order lifecycle tracking with crash recovery.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.order_lifecycle import (
    LiveOrder, OrderState, OrderFill, PositionReconciliation
)

logger = logging.getLogger(__name__)


class OrderRepository:
    """
    Repository for persistent order storage.
    Ensures orders survive restarts and crashes.
    """
    
    ORDERS_COLLECTION = "live_orders"
    RECONCILIATION_COLLECTION = "position_reconciliations"
    IDEMPOTENCY_COLLECTION = "idempotency_keys"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.orders_col = db[self.ORDERS_COLLECTION]
        self.recon_col = db[self.RECONCILIATION_COLLECTION]
        self.idemp_col = db[self.IDEMPOTENCY_COLLECTION]
    
    async def create_indexes(self):
        """Create required indexes for performance."""
        # Orders indexes
        await self.orders_col.create_index([("idempotency_key", 1)], unique=True)
        await self.orders_col.create_index([("state", 1), ("created_at", -1)])
        await self.orders_col.create_index([("market_id", 1), ("state", 1)])
        await self.orders_col.create_index([("exchange_order_id", 1)])
        await self.orders_col.create_index([("created_at", -1)])
        
        # Idempotency indexes
        await self.idemp_col.create_index([("key", 1)], unique=True)
        await self.idemp_col.create_index([("expires_at", 1)], expireAfterSeconds=0)
        
        # Reconciliation indexes
        await self.recon_col.create_index([("market_id", 1), ("checked_at", -1)])
        await self.recon_col.create_index([("fully_reconciled", 1)])
        
        logger.info("Order repository indexes created")
    
    # ============================================
    # IDEMPOTENCY
    # ============================================
    
    async def check_idempotency_key(
        self,
        key: str,
        window_minutes: int = 60
    ) -> Optional[LiveOrder]:
        """
        Check if idempotency key already exists.
        Returns existing order if duplicate, None if new.
        """
        # Check idempotency collection first
        existing = await self.idemp_col.find_one({"key": key})
        if existing:
            # Key exists - check if order exists
            order = await self.get_order_by_idempotency_key(key)
            if order:
                logger.warning(f"Duplicate order attempt blocked: {key}")
                return order
        
        return None
    
    async def register_idempotency_key(
        self,
        key: str,
        order_id: str,
        window_minutes: int = 60
    ):
        """
        Register idempotency key with TTL.
        Key expires after window to allow retries later.
        """
        expires_at = datetime.utcnow() + timedelta(minutes=window_minutes)
        
        await self.idemp_col.update_one(
            {"key": key},
            {
                "$set": {
                    "key": key,
                    "order_id": order_id,
                    "created_at": datetime.utcnow(),
                    "expires_at": expires_at
                }
            },
            upsert=True
        )
    
    # ============================================
    # ORDERS
    # ============================================
    
    async def save_order(self, order: LiveOrder) -> LiveOrder:
        """
        Save order to database.
        Uses upsert for idempotency.
        """
        order_dict = order.dict()
        order_dict["_id"] = order.id
        
        # Convert enums to values for MongoDB
        order_dict["state"] = order.state.value
        order_dict["side"] = order.side.value
        order_dict["action"] = order.action.value
        order_dict["order_type"] = order.order_type.value
        
        # Convert state history
        order_dict["state_history"] = [
            {
                "from_state": t.from_state.value if t.from_state else None,
                "to_state": t.to_state.value,
                "timestamp": t.timestamp,
                "reason": t.reason,
                "metadata": t.metadata
            }
            for t in order.state_history
        ]
        
        # Convert fills
        order_dict["fills"] = [f.dict() for f in order.fills]
        
        await self.orders_col.update_one(
            {"_id": order.id},
            {"$set": order_dict},
            upsert=True
        )
        
        logger.info(f"Order saved: {order.id} state={order.state.value}")
        return order
    
    async def get_order(self, order_id: str) -> Optional[LiveOrder]:
        """Get order by ID."""
        doc = await self.orders_col.find_one({"_id": order_id})
        if not doc:
            return None
        return self._doc_to_order(doc)
    
    async def get_order_by_idempotency_key(self, key: str) -> Optional[LiveOrder]:
        """Get order by idempotency key."""
        doc = await self.orders_col.find_one({"idempotency_key": key})
        if not doc:
            return None
        return self._doc_to_order(doc)
    
    async def get_order_by_exchange_id(self, exchange_id: str) -> Optional[LiveOrder]:
        """Get order by exchange order ID."""
        doc = await self.orders_col.find_one({"exchange_order_id": exchange_id})
        if not doc:
            return None
        return self._doc_to_order(doc)
    
    async def get_working_orders(self) -> List[LiveOrder]:
        """Get all orders in working state (not terminal)."""
        working_states = [
            OrderState.SUBMITTED.value,
            OrderState.ACKNOWLEDGED.value,
            OrderState.PARTIAL.value
        ]
        
        cursor = self.orders_col.find({"state": {"$in": working_states}})
        orders = []
        async for doc in cursor:
            orders.append(self._doc_to_order(doc))
        return orders
    
    async def get_orders_for_market(
        self,
        market_id: str,
        include_terminal: bool = False
    ) -> List[LiveOrder]:
        """Get all orders for a market."""
        query = {"market_id": market_id}
        if not include_terminal:
            working_states = [
                OrderState.SUBMITTED.value,
                OrderState.ACKNOWLEDGED.value,
                OrderState.PARTIAL.value
            ]
            query["state"] = {"$in": working_states}
        
        cursor = self.orders_col.find(query).sort("created_at", -1)
        orders = []
        async for doc in cursor:
            orders.append(self._doc_to_order(doc))
        return orders
    
    async def get_recent_orders(
        self,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[LiveOrder]:
        """Get recent orders."""
        query = {}
        if since:
            query["created_at"] = {"$gte": since}
        
        cursor = self.orders_col.find(query).sort("created_at", -1).limit(limit)
        orders = []
        async for doc in cursor:
            orders.append(self._doc_to_order(doc))
        return orders
    
    async def count_orders_in_window(
        self,
        window_minutes: int = 60
    ) -> int:
        """Count orders in time window for rate limiting."""
        since = datetime.utcnow() - timedelta(minutes=window_minutes)
        return await self.orders_col.count_documents({
            "created_at": {"$gte": since}
        })
    
    async def update_order_state(
        self,
        order_id: str,
        new_state: OrderState,
        reason: Optional[str] = None,
        metadata: Dict = None
    ) -> Optional[LiveOrder]:
        """Update order state with audit trail."""
        order = await self.get_order(order_id)
        if not order:
            return None
        
        order.transition_to(new_state, reason, metadata)
        return await self.save_order(order)
    
    async def add_fill_to_order(
        self,
        order_id: str,
        fill: OrderFill
    ) -> Optional[LiveOrder]:
        """Add fill to order and update state."""
        order = await self.get_order(order_id)
        if not order:
            return None
        
        order.add_fill(fill)
        return await self.save_order(order)
    
    # ============================================
    # RECONCILIATION
    # ============================================
    
    async def save_reconciliation(
        self,
        recon: PositionReconciliation
    ) -> PositionReconciliation:
        """Save reconciliation result."""
        recon_dict = recon.dict()
        recon_dict["_id"] = recon.id
        
        await self.recon_col.update_one(
            {"_id": recon.id},
            {"$set": recon_dict},
            upsert=True
        )
        
        return recon
    
    async def get_unreconciled_positions(self) -> List[PositionReconciliation]:
        """Get all unreconciled positions."""
        cursor = self.recon_col.find({
            "fully_reconciled": False,
            "resolved_at": None
        }).sort("checked_at", -1)
        
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(PositionReconciliation(**doc))
        return results
    
    async def get_reconciliation_history(
        self,
        market_id: str,
        limit: int = 20
    ) -> List[PositionReconciliation]:
        """Get reconciliation history for a market."""
        cursor = self.recon_col.find(
            {"market_id": market_id}
        ).sort("checked_at", -1).limit(limit)
        
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(PositionReconciliation(**doc))
        return results
    
    # ============================================
    # HELPERS
    # ============================================
    
    def _doc_to_order(self, doc: Dict) -> LiveOrder:
        """Convert MongoDB document to LiveOrder."""
        doc.pop("_id", None)
        
        # Convert state string back to enum
        doc["state"] = OrderState(doc["state"])
        doc["side"] = doc["side"]  # Keep as string, model handles enum
        doc["action"] = doc["action"]
        doc["order_type"] = doc["order_type"]
        
        # State history already has string values, model handles conversion
        
        return LiveOrder(**doc)
    
    async def cleanup_old_orders(self, days: int = 30):
        """Clean up old terminal orders."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        terminal_states = [
            OrderState.FILLED.value,
            OrderState.REJECTED.value,
            OrderState.CANCELLED.value,
            OrderState.EXPIRED.value
        ]
        
        result = await self.orders_col.delete_many({
            "state": {"$in": terminal_states},
            "created_at": {"$lt": cutoff}
        })
        
        logger.info(f"Cleaned up {result.deleted_count} old orders")
