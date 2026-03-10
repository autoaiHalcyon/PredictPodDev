"""
Config Version Model

Stores versioned configurations for strategies with:
- Deterministic version IDs (MODEL_A_NBA_v0012)
- Base config + league overrides
- Diff tracking
- Rollback support
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import json


class TunerMode(str, Enum):
    """Auto-tuner operation modes."""
    OFF = "off"
    PROPOSE_ONLY = "propose_only"
    AUTO_APPLY_PAPER = "auto_apply_paper"


class ConfigChangeSource(str, Enum):
    """Source of configuration change."""
    MANUAL = "manual"
    AUTO_TUNER = "auto_tuner"
    ROLLBACK = "rollback"
    INITIAL = "initial"


class LeagueType(str, Enum):
    """Supported basketball leagues."""
    NBA = "NBA"
    NCAA_M = "NCAA_M"
    NCAA_W = "NCAA_W"
    GENERIC = "GENERIC"


class ConfigDiff(BaseModel):
    """Represents a single parameter change."""
    parameter: str
    old_value: Any
    new_value: Any
    league: Optional[str] = None  # None means base config


class ConfigVersion(BaseModel):
    """
    A versioned configuration for a strategy.
    
    Version ID format: MODEL_A_NBA_v0012
    """
    id: str = ""  # Will be set by repository
    model_id: str  # model_a_disciplined, model_b_high_frequency, model_c_institutional
    league: str  # NBA, NCAA_M, NCAA_W, GENERIC, or "BASE" for base config
    version_number: int = 1
    version_id: str = ""  # MODEL_A_NBA_v0001
    
    # The actual configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None
    applied_by: ConfigChangeSource = ConfigChangeSource.INITIAL
    
    # Change tracking
    diff_from_previous: List[ConfigDiff] = Field(default_factory=list)
    change_summary: str = ""
    
    # Status
    is_active: bool = False
    is_proposed: bool = False  # True if proposed but not yet applied
    
    # Tuner metadata
    tuner_score: Optional[float] = None
    tuner_metrics: Dict[str, float] = Field(default_factory=dict)
    
    def generate_version_id(self) -> str:
        """Generate deterministic version ID."""
        model_letter = self.model_id.split("_")[1][0].upper()  # a -> A, b -> B, c -> C
        return f"MODEL_{model_letter}_{self.league}_v{self.version_number:04d}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "model_id": self.model_id,
            "league": self.league,
            "version_number": self.version_number,
            "version_id": self.version_id,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "applied_by": self.applied_by.value,
            "diff_from_previous": [d.dict() for d in self.diff_from_previous],
            "change_summary": self.change_summary,
            "is_active": self.is_active,
            "is_proposed": self.is_proposed,
            "tuner_score": self.tuner_score,
            "tuner_metrics": self.tuner_metrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConfigVersion":
        """Create from dictionary."""
        data = dict(data)
        
        # Handle datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("applied_at") and isinstance(data["applied_at"], str):
            data["applied_at"] = datetime.fromisoformat(data["applied_at"])
        
        # Handle enums
        if isinstance(data.get("applied_by"), str):
            data["applied_by"] = ConfigChangeSource(data["applied_by"])
        
        # Handle diffs
        if data.get("diff_from_previous"):
            data["diff_from_previous"] = [
                ConfigDiff(**d) if isinstance(d, dict) else d 
                for d in data["diff_from_previous"]
            ]
        
        # Remove MongoDB _id if present
        data.pop("_id", None)
        
        return cls(**data)


class TunerProposal(BaseModel):
    """A proposed configuration change from the auto-tuner."""
    id: str = ""
    model_id: str
    league: str
    
    # Proposed changes
    proposed_config: Dict[str, Any] = Field(default_factory=dict)
    changes: List[ConfigDiff] = Field(default_factory=list)
    change_summary: str = ""
    
    # Expected impact
    expected_pnl_improvement: float = 0.0
    expected_drawdown_change: float = 0.0
    confidence_score: float = 0.0
    
    # Validation
    sample_size: int = 0
    train_window_days: int = 3
    validate_window_days: int = 1
    
    # Status
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, applied, rejected, expired
    applied_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "league": self.league,
            "proposed_config": self.proposed_config,
            "changes": [c.dict() for c in self.changes],
            "change_summary": self.change_summary,
            "expected_pnl_improvement": self.expected_pnl_improvement,
            "expected_drawdown_change": self.expected_drawdown_change,
            "confidence_score": self.confidence_score,
            "sample_size": self.sample_size,
            "train_window_days": self.train_window_days,
            "validate_window_days": self.validate_window_days,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rejected_reason": self.rejected_reason
        }


class TunerSettings(BaseModel):
    """Global auto-tuner settings."""
    mode: TunerMode = TunerMode.PROPOSE_ONLY
    
    # Schedule
    daily_run_hour_utc: int = 3  # 03:00 UTC
    enable_midday_runs: bool = False
    midday_interval_hours: int = 6
    
    # Thresholds
    min_sample_size_overall: int = 50
    min_sample_size_per_regime: int = 20
    min_improvement_pct: float = 5.0  # 5%
    max_drawdown_increase_pct: float = 10.0  # 10%
    
    # Safety
    auto_rollback_on_degradation: bool = True
    degradation_threshold_pct: float = 20.0  # 20% worse
    
    def to_dict(self) -> Dict:
        return {
            "mode": self.mode.value,
            "daily_run_hour_utc": self.daily_run_hour_utc,
            "enable_midday_runs": self.enable_midday_runs,
            "midday_interval_hours": self.midday_interval_hours,
            "min_sample_size_overall": self.min_sample_size_overall,
            "min_sample_size_per_regime": self.min_sample_size_per_regime,
            "min_improvement_pct": self.min_improvement_pct,
            "max_drawdown_increase_pct": self.max_drawdown_increase_pct,
            "auto_rollback_on_degradation": self.auto_rollback_on_degradation,
            "degradation_threshold_pct": self.degradation_threshold_pct
        }
