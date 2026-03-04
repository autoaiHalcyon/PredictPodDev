"""
External Adapters - Interfaces for external data sources.
"""
from .nba import NBADataProvider, ESPNAdapter
from .kalshi import KalshiAdapter, MockKalshiAdapter

__all__ = [
    'NBADataProvider',
    'ESPNAdapter',
    'KalshiAdapter',
    'MockKalshiAdapter'
]
