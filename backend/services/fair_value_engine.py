"""
PredictPod Fair Value Engine
============================
Implements EXACT fair value formulas from Master Rules spec for all 5 models.
No rounding on thresholds. All numbers implementable as-is.
"""

import math
from dataclasses import dataclass
from typing import Optional


def normal_cdf(z: float) -> float:
    """Standard normal CDF approximation: 1 / (1 + exp(-1.7 * z))"""
    return 1.0 / (1.0 + math.exp(-1.7 * z))


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class LiveGameState:
    """Live game state for in-game models (A and C)."""
    home_score: int
    away_score: int
    periods_remaining: int        # periods left AFTER current
    seconds_in_current_period: int  # seconds elapsed in current period
    period_length_seconds: int    # 