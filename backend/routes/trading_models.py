"""
Trading Models API Routes - CRUD endpoints for trading model management.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading-models", tags=["trading-models"])

# Global reference to database (set in server.py lifespan)
db = None


def set_db(database):
    """Set the database instance."""
    global db
    db = database


@router.get("")
async def list_models(include_disabled: bool = True):
    """List all trading models."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    query = {} if include_disabled else {"status": "active"}
    cursor = db.trading_models.find(query).sort("created_at", -1)
    
    models = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        models.append(doc)
    
    return {"models": models, "count": len(models)}


@router.get("/{model_id}")
async def get_model(model_id: str):
    """Get a specific trading model by ID."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        doc = await db.trading_models.find_one({"_id": ObjectId(model_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Model not found")
        doc["id"] = str(doc.pop("_id"))
        return doc
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}")
        raise HTTPException(status_code=404, detail="Model not found")


@router.post("")
async def create_model(
    name: str,
    status: str = "active",
    capital_allocation_pct: float = 50.0,
    rules: Optional[dict] = None
):
    """Create a new trading model."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Model name is required")
    
    # Check for duplicate name
    existing = await db.trading_models.find_one({"name": name})
    if existing:
        raise HTTPException(status_code=400, detail=f"Model with name '{name}' already exists")
    
    now = datetime.utcnow()
    default_rules = {
        "min_edge_threshold": 0.03,
        "min_clv_required": 0.02,
        "max_odds": 0.85,
        "min_odds": 0.05,
        "kelly_fraction": 0.5,
        "max_position_size_pct": 0.05,
        "lookback_window_hours": 24,
        "min_market_volume": 1000,
        "notes": ""
    }
    
    doc = {
        "name": name.strip(),
        "status": status,
        "capital_allocation_pct": capital_allocation_pct,
        "rules": rules if rules else default_rules,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await db.trading_models.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    if "_id" in doc:
        del doc["_id"]
    
    logger.info(f"Created trading model: {name}")
    return {"message": "Model created successfully", "model": doc}


@router.put("/{model_id}")
async def update_model(
    model_id: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
    capital_allocation_pct: Optional[float] = None,
    rules: Optional[dict] = None
):
    """Update an existing trading model."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Check exists
    try:
        existing = await db.trading_models.find_one({"_id": ObjectId(model_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Model not found")
    except:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Build update
    update_data = {"updated_at": datetime.utcnow()}
    
    if name is not None:
        if not name.strip():
            raise HTTPException(status_code=400, detail="Model name cannot be empty")
        # Check for duplicate name (excluding current model)
        dup = await db.trading_models.find_one({"name": name, "_id": {"$ne": ObjectId(model_id)}})
        if dup:
            raise HTTPException(status_code=400, detail=f"Model with name '{name}' already exists")
        update_data["name"] = name.strip()
    
    if status is not None:
        update_data["status"] = status
    
    if capital_allocation_pct is not None:
        update_data["capital_allocation_pct"] = capital_allocation_pct
    
    if rules is not None:
        update_data["rules"] = rules
    
    await db.trading_models.update_one(
        {"_id": ObjectId(model_id)},
        {"$set": update_data}
    )
    
    # Fetch updated doc
    doc = await db.trading_models.find_one({"_id": ObjectId(model_id)})
    doc["id"] = str(doc.pop("_id"))
    
    logger.info(f"Updated trading model: {model_id}")
    return {"message": "Model updated successfully", "model": doc}


@router.patch("/{model_id}/toggle")
async def toggle_model_status(model_id: str):
    """Toggle model active/disabled status."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        doc = await db.trading_models.find_one({"_id": ObjectId(model_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Model not found")
        
        new_status = "disabled" if doc.get("status") == "active" else "active"
        
        await db.trading_models.update_one(
            {"_id": ObjectId(model_id)},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
        )
        
        return {"message": f"Model {new_status}", "status": new_status}
    except Exception as e:
        logger.error(f"Error toggling model {model_id}: {e}")
        raise HTTPException(status_code=404, detail="Model not found")


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    """Delete a trading model."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        result = await db.trading_models.delete_one({"_id": ObjectId(model_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Model not found")
        
        logger.info(f"Deleted trading model: {model_id}")
        return {"message": "Model deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting model {model_id}: {e}")
        raise HTTPException(status_code=404, detail="Model not found")


async def seed_default_models():
    """Seed default models if none exist."""
    if db is None:
        return
    
    count = await db.trading_models.count_documents({})
    if count > 0:
        logger.info(f"Trading models already exist ({count}), skipping seed")
        return
    
    from models.trading_model import DEFAULT_MODELS
    
    now = datetime.utcnow()
    for model_data in DEFAULT_MODELS:
        doc = {
            **model_data,
            "created_at": now,
            "updated_at": now,
        }
        await db.trading_models.insert_one(doc)
        logger.info(f"Seeded default model: {model_data['name']}")
    
    logger.info(f"Seeded {len(DEFAULT_MODELS)} default trading models")
