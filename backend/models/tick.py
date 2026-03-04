"""
Tick Models - Time-series data for prices and probabilities.
Critical for building proprietary dataset for future ML.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class ProbabilityTick(BaseModel):
    """Stores probability updates for time-series analysis"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Probabilities
    market_prob: float  # Kalshi implied probability
    fair_prob: float    # Our model's probability
    edge: float         # fair_prob - market_prob
    
    # Game state at this tick
    home_score: int
    away_score: int
    score_diff: int  # home - away
    quarter: int
    time_remaining_seconds: int
    
    # Signal generated
    signal: Optional[str] = None  # BUY, STRONG_BUY, SELL, etc.
    
    class Config:
        # Enable time-series indexing
        schema_extra = {
            "indexes": [
                {"fields": ["game_id", "timestamp"]},
                {"fields": ["timestamp"]}
            ]
        }

class MarketTick(BaseModel):
    """Stores market price updates for time-series analysis"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    market_id: str
    game_id: str
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Prices
    yes_price: float
    no_price: float
    yes_bid: float
    yes_ask: float
    spread: float
    
    # Volume
    volume: int
    volume_delta: int = 0  # Change since last tick
    
    class Config:
        schema_extra = {
            "indexes": [
                {"fields": ["market_id", "timestamp"]},
                {"fields": ["game_id", "timestamp"]}
            ]
        }
