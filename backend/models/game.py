"""
Game Model - Represents an NBA game with live state.
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class GameStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    HALFTIME = "halftime"
    FINAL = "final"
    POSTPONED = "postponed"

class Team(BaseModel):
    id: str
    name: str
    abbreviation: str
    logo_url: Optional[str] = None

class Game(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    league: str = "NBA"
    
    # Teams
    home_team: Team
    away_team: Team
    
    # Schedule
    start_time: datetime
    status: GameStatus = GameStatus.SCHEDULED
    
    # Live Score
    home_score: int = 0
    away_score: int = 0
    quarter: int = 0  # 0 = not started, 1-4 = quarters, 5 = OT
    time_remaining: str = "12:00"  # MM:SS format
    time_remaining_seconds: int = 720  # Seconds remaining in quarter
    
    # Metadata
    espn_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def score_differential(self) -> int:
        """Positive = home leading, negative = away leading"""
        return self.home_score - self.away_score
    
    @property
    def total_seconds_remaining(self) -> int:
        """Total seconds remaining in game"""
        if self.status == GameStatus.FINAL:
            return 0
        quarters_remaining = max(0, 4 - self.quarter)
        return self.time_remaining_seconds + (quarters_remaining * 720)
    
    @property
    def game_progress(self) -> float:
        """Game progress as 0-1 (1 = game over)"""
        total_game_seconds = 4 * 720  # 48 minutes
        elapsed = total_game_seconds - self.total_seconds_remaining
        return min(1.0, max(0.0, elapsed / total_game_seconds))
    
    def to_dict(self) -> dict:
        return {
            **self.dict(),
            'score_differential': self.score_differential,
            'total_seconds_remaining': self.total_seconds_remaining,
            'game_progress': self.game_progress
        }
