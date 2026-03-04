"""
Kalshi Adapters

Adapter Modes:
- MockKalshiAdapter: Paper trading with simulated data (DEFAULT)
- KalshiAdapterSandbox: Demo API or Full Lifecycle Simulation
- RealKalshiAdapter: Live trading with real money (requires credentials)
"""
from .interface import KalshiAdapter
from .mock_adapter import MockKalshiAdapter
from .real_adapter import RealKalshiAdapter
from .sandbox_adapter import KalshiAdapterSandbox

__all__ = [
    'KalshiAdapter', 
    'MockKalshiAdapter', 
    'RealKalshiAdapter',
    'KalshiAdapterSandbox'
]
