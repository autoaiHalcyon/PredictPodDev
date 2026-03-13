"""
PredictPod Configuration
Centralized configuration management with environment variable support.
"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore'  # Ignore extra fields from env
    )
    
    # Database
    mongo_url: str = os.environ.get('MONGO_URL', 'mongodb+srv://HalMan_db_user:Halcyon%4012$@cluster0.ifvwnf.mongodb.net')
    db_name: str = os.environ.get('DB_NAME', 'predictpod')
    
    # CORS Configuration - env-based allowlist
    cors_origins: str = os.environ.get('CORS_ORIGINS', 'https://beta.predictpod.co')
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string to list"""
        origins = self.cors_origins.split(',')
        return [origin.strip() for origin in origins if origin.strip()]
    
    # Kalshi API (for future real integration)
    kalshi_api_key: Optional[str] = None
    kalshi_private_key: Optional[str] = None
    kalshi_demo_mode: bool = True
    kalshi_base_url: str = 'https://demo-api.kalshi.co/v1'
    
    # Trading Mode
    paper_trading_enabled: bool = True  # Always start in paper mode
    live_trading_enabled: bool = False  # Requires explicit enable
    
    # Risk Limits (defaults)
    max_position_size: float = 100.0  # Max $ per position
    max_daily_loss: float = 500.0  # Max daily loss limit
    max_open_exposure: float = 1000.0  # Max total exposure
    max_trades_per_day: int = 50  # Max trades per day
    
    # Signal Thresholds
    edge_threshold_buy: float = 0.03  # 3% edge for BUY
    edge_threshold_strong_buy: float = 0.05  # 5% edge for STRONG BUY
    late_game_threshold_time: int = 360  # 6 minutes in seconds
    late_game_threshold_lead: int = 6  # 6 point lead
    
    # Rate Limiting - Relaxed for development
    rate_limit_requests: int = 500  # Max requests per window
    rate_limit_window: int = 60  # Window in seconds
    
    # Refresh intervals (seconds)
    score_refresh_interval: int = 5
    market_refresh_interval: int = 3

settings = Settings()
