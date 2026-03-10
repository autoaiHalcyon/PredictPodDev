"""
Trading Model - Database model for user trading models with rules configuration.
"""
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field


class ModelRules(BaseModel):
    """Rule configuration for a trading model."""
    min_edge_threshold: float = Field(default=0.03, description="Minimum edge threshold")
    min_clv_required: float = Field(default=0.02, description="Minimum CLV required")
    max_odds: float = Field(default=0.85, description="Maximum odds")
    min_odds: float = Field(default=0.05, description="Minimum odds")
    kelly_fraction: float = Field(default=0.5, description="Kelly fraction for sizing")
    max_position_size_pct: float = Field(default=0.05, description="Max position size % of bankroll")
    lookback_window_hours: int = Field(default=24, description="Lookback window in hours")
    min_market_volume: int = Field(default=1000, description="Minimum market volume ($)")
    notes: str = Field(default="", description="Strategy notes/description")


class TradingModelCreate(BaseModel):
    """Request model for creating a trading model."""
    name: str = Field(..., description="Model name")
    status: str = Field(default="active", description="active or disabled")
    capital_allocation_pct: float = Field(default=50.0, description="Capital allocation %")
    rules: ModelRules = Field(default_factory=ModelRules)


class TradingModelUpdate(BaseModel):
    """Request model for updating a trading model."""
    name: Optional[str] = None
    status: Optional[str] = None
    capital_allocation_pct: Optional[float] = None
    rules: Optional[Dict[str, Any]] = None


class TradingModelInDB(BaseModel):
    """Trading model as stored in MongoDB."""
    id: str
    name: str
    status: str = "active"
    capital_allocation_pct: float = 50.0
    rules: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "capital_allocation_pct": self.capital_allocation_pct,
            "rules": self.rules,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Default models to seed
DEFAULT_MODELS = [
    {
        "name": "Enhanced CLV",
        "status": "active",
        "capital_allocation_pct": 70.0,
        "rules": {
            "min_edge_threshold": 0.03,
            "min_clv_required": 0.025,
            "max_odds": 0.85,
            "min_odds": 0.05,
            "kelly_fraction": 0.5,
            "max_position_size_pct": 0.05,
            "lookback_window_hours": 24,
            "min_market_volume": 1500,
            "notes": "Focus on closing line value with moderate edge requirements. Best for liquid markets."
        }
    },
    {
        "name": "Strong Favorite Value",
        "status": "active",
        "capital_allocation_pct": 30.0,
        "rules": {
            "min_edge_threshold": 0.02,
            "min_clv_required": 0.015,
            "max_odds": 0.95,
            "min_odds": 0.70,
            "kelly_fraction": 0.4,
            "max_position_size_pct": 0.03,
            "lookback_window_hours": 48,
            "min_market_volume": 2000,
            "notes": "Targets strong favorites with high edge. More conservative sizing for safer bets."
        }
    }
]
