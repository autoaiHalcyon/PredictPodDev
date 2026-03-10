"""
Strategy Model - Database model for user-created trading strategies.

Stores strategy metadata and the full JSON config required by the trading engines.
The config_json field preserves the exact schema expected by existing strategy classes.
"""
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class StrategyBase(BaseModel):
    """Base fields for strategy creation/update."""
    strategy_key: str = Field(..., description="Unique key for the strategy (e.g., 'sharp_edge_hunter')")
    model_id: str = Field(..., description="Base model type: model_a, model_b, model_c, model_d, model_e")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Strategy description")
    enabled: bool = Field(default=True, description="Whether strategy is active")
    config_json: Dict[str, Any] = Field(..., description="Full JSON config matching existing schema")


class StrategyCreate(StrategyBase):
    """Request model for creating a strategy."""
    pass


class StrategyUpdate(BaseModel):
    """Request model for updating a strategy (all fields optional)."""
    strategy_key: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None


class StrategyInDB(StrategyBase):
    """Strategy as stored in MongoDB."""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "strategy_key": self.strategy_key,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "config_json": self.config_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Base model ID to strategy class mapping
BASE_MODEL_MAPPING = {
    "model_a": "model_a_disciplined",
    "model_b": "model_b_high_frequency",
    "model_c": "model_c_institutional",
    "model_d": "model_d_growth_focused",
    "model_e": "model_e_balanced_hunter",
    # Also allow full IDs for backwards compatibility
    "model_a_disciplined": "model_a_disciplined",
    "model_b_high_frequency": "model_b_high_frequency",
    "model_c_institutional": "model_c_institutional",
    "model_d_growth_focused": "model_d_growth_focused",
    "model_e_balanced_hunter": "model_e_balanced_hunter",
}


def resolve_model_id(model_id: str) -> str:
    """Resolve short model_id to full model_id for strategy class resolution."""
    return BASE_MODEL_MAPPING.get(model_id.lower(), "model_a_disciplined")
