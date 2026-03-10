"""
Strategies API Routes - CRUD endpoints for dynamic strategy management.
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user-strategies", tags=["strategies"])

# Global reference to repository (set in server.py lifespan)
strategy_repo = None


def set_strategy_repo(repo):
    """Set the strategy repository instance."""
    global strategy_repo
    strategy_repo = repo


class CreateStrategyRequest(BaseModel):
    """Request body for creating a strategy."""
    strategy_key: str
    base_model: str  # model_a, model_b, etc.
    display_name: str
    description: str = ""
    enabled: bool = True
    config_overrides: Dict[str, Any] = {}


class UpdateStrategyRequest(BaseModel):
    """Request body for updating a strategy."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None


class CloneStrategyRequest(BaseModel):
    """Request body for cloning a strategy."""
    new_strategy_key: str
    new_display_name: str
    description: str = ""


def load_base_config(model_id: str) -> Dict[str, Any]:
    """Load base model config from JSON file."""
    config_dir = Path(__file__).parent.parent / "strategies" / "configs"
    
    # Map model_id to config file
    model_map = {
        "model_a": "model_a.json",
        "model_b": "model_b.json",
        "model_c": "model_c.json",
        "model_d": "model_d.json",
        "model_e": "model_e.json",
        "model_a_disciplined": "model_a.json",
        "model_b_high_frequency": "model_b.json",
        "model_c_institutional": "model_c.json",
        "model_d_growth_focused": "model_d.json",
        "model_e_balanced_hunter": "model_e.json",
    }
    
    config_file = model_map.get(model_id.lower(), "model_a.json")
    config_path = config_dir / config_file
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    
    raise HTTPException(status_code=400, detail=f"Unknown base model: {model_id}")


def deep_merge(base: Dict, overrides: Dict) -> Dict:
    """Deep merge overrides into base config."""
    result = base.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@router.get("")
async def list_strategies(include_disabled: bool = False):
    """List all user-created strategies."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    strategies = await strategy_repo.get_all(include_disabled=include_disabled)
    return {
        "strategies": [s.to_dict() for s in strategies],
        "count": len(strategies)
    }


@router.get("/base-models")
async def get_base_models():
    """Get available base models and their configs."""
    base_models = []
    for model_id in ["model_a", "model_b", "model_c", "model_d", "model_e"]:
        try:
            config = load_base_config(model_id)
            base_models.append({
                "model_id": model_id,
                "display_name": config.get("display_name", model_id),
                "description": config.get("description", ""),
                "config": config
            })
        except Exception as e:
            logger.warning(f"Could not load config for {model_id}: {e}")
    
    return {"base_models": base_models}


@router.get("/parameter-bounds")
async def get_parameter_bounds():
    """Get parameter bounds for validation."""
    config_dir = Path(__file__).parent.parent / "strategies" / "configs"
    bounds_path = config_dir / "parameter_bounds.json"
    
    if bounds_path.exists():
        with open(bounds_path, 'r') as f:
            return json.load(f)
    
    return {"error": "Parameter bounds not found"}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get a specific strategy by ID."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    strategy = await strategy_repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy.to_dict()


@router.post("")
async def create_strategy(request: CreateStrategyRequest):
    """Create a new strategy based on a base model."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    # Check if key already exists
    existing = await strategy_repo.get_by_key(request.strategy_key)
    if existing:
        raise HTTPException(status_code=400, detail=f"Strategy key '{request.strategy_key}' already exists")
    
    # Load base config
    base_config = load_base_config(request.base_model)
    
    # Merge overrides
    config_json = deep_merge(base_config, request.config_overrides)
    
    # Update metadata in config
    config_json["display_name"] = request.display_name
    config_json["description"] = request.description
    config_json["enabled"] = request.enabled
    
    # Create strategy
    from models.strategy import StrategyCreate
    strategy = StrategyCreate(
        strategy_key=request.strategy_key,
        model_id=request.base_model,
        display_name=request.display_name,
        description=request.description,
        enabled=request.enabled,
        config_json=config_json
    )
    
    created = await strategy_repo.create(strategy)
    
    # Trigger strategy manager reload
    await reload_strategy_manager()
    
    return {
        "message": "Strategy created successfully",
        "strategy": created.to_dict()
    }


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str, request: UpdateStrategyRequest):
    """Update an existing strategy."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    # Check exists
    existing = await strategy_repo.get_by_id(strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Build updates
    from models.strategy import StrategyUpdate
    updates = StrategyUpdate(
        display_name=request.display_name,
        description=request.description,
        enabled=request.enabled,
        config_json=request.config_json
    )
    
    updated = await strategy_repo.update(strategy_id, updates)
    
    # Trigger strategy manager reload
    await reload_strategy_manager()
    
    return {
        "message": "Strategy updated successfully",
        "strategy": updated.to_dict() if updated else None
    }


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete a strategy."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    # Check exists
    existing = await strategy_repo.get_by_id(strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Don't allow deleting default strategies
    default_keys = [
        "model_a_disciplined", "model_b_high_frequency", 
        "model_c_institutional", "model_d_growth_focused", 
        "model_e_balanced_hunter"
    ]
    if existing.strategy_key in default_keys:
        raise HTTPException(status_code=400, detail="Cannot delete default strategies")
    
    success = await strategy_repo.delete(strategy_id)
    
    if success:
        # Trigger strategy manager reload
        await reload_strategy_manager()
        return {"message": "Strategy deleted successfully"}
    
    raise HTTPException(status_code=500, detail="Failed to delete strategy")


@router.post("/{strategy_id}/clone")
async def clone_strategy(strategy_id: str, request: CloneStrategyRequest):
    """Clone an existing strategy with new name."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    # Get source strategy
    source = await strategy_repo.get_by_id(strategy_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source strategy not found")
    
    # Check if new key already exists
    existing = await strategy_repo.get_by_key(request.new_strategy_key)
    if existing:
        raise HTTPException(status_code=400, detail=f"Strategy key '{request.new_strategy_key}' already exists")
    
    # Clone config
    new_config = source.config_json.copy()
    new_config["display_name"] = request.new_display_name
    new_config["description"] = request.description or f"Cloned from {source.display_name}"
    
    # Create new strategy
    from models.strategy import StrategyCreate
    new_strategy = StrategyCreate(
        strategy_key=request.new_strategy_key,
        model_id=source.model_id,
        display_name=request.new_display_name,
        description=request.description or f"Cloned from {source.display_name}",
        enabled=True,
        config_json=new_config
    )
    
    created = await strategy_repo.create(new_strategy)
    
    # Trigger strategy manager reload
    await reload_strategy_manager()
    
    return {
        "message": "Strategy cloned successfully",
        "strategy": created.to_dict()
    }


@router.post("/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str, enabled: bool):
    """Toggle strategy enabled/disabled."""
    if not strategy_repo:
        raise HTTPException(status_code=503, detail="Strategy repository not available")
    
    updated = await strategy_repo.toggle_enabled(strategy_id, enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Trigger strategy manager reload
    await reload_strategy_manager()
    
    return {
        "message": f"Strategy {'enabled' if enabled else 'disabled'}",
        "strategy": updated.to_dict()
    }


async def reload_strategy_manager():
    """Reload strategy manager with updated strategies from DB."""
    try:
        # Import here to avoid circular imports
        from strategies import strategy_manager
        
        # Generate config files for all enabled strategies
        if strategy_repo:
            strategies = await strategy_repo.get_enabled()
            generated_dir = Path(__file__).parent.parent / "strategies" / "configs" / "generated"
            generated_dir.mkdir(exist_ok=True)
            
            for strategy in strategies:
                config_path = generated_dir / f"{strategy.strategy_key}.json"
                with open(config_path, 'w') as f:
                    json.dump(strategy.config_json, f, indent=2)
                logger.info(f"Generated config: {config_path}")
        
        # Reload strategy configs
        strategy_manager.reload_configs()
        logger.info("Strategy manager reloaded")
    except Exception as e:
        logger.error(f"Failed to reload strategy manager: {e}")
