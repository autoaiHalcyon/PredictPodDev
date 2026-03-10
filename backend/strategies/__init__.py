"""
Multi-Model Strategy Engine

Provides parallel execution of multiple trading strategies:
- Model A: Disciplined Edge Trader
- Model B: High Frequency Edge Hunter  
- Model C: Institutional Risk-First

Each strategy maintains independent:
- Virtual capital
- PnL tracking
- Risk limits
- Trade logs
"""
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.virtual_portfolio import VirtualPortfolio, VirtualPosition, VirtualTrade
from strategies.model_a_disciplined import ModelADisciplined
from strategies.model_b_high_frequency import ModelBHighFrequency
from strategies.model_c_institutional import ModelCInstitutional
from strategies.strategy_manager import StrategyEngineManager, strategy_manager

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "StrategyDecision",
    "DecisionType",
    "VirtualPortfolio",
    "VirtualPosition",
    "VirtualTrade",
    "ModelADisciplined",
    "ModelBHighFrequency",
    "ModelCInstitutional",
    "StrategyEngineManager",
    "strategy_manager"
]
