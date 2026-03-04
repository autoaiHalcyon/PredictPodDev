"""
Performance Tracking Service

Comprehensive performance tracking for multi-model strategy comparison.
Tracks actual vs expected outcomes, slippage, and performance by various dimensions.

Features:
- Expected vs Actual profit comparison
- Slippage tracking
- Stop hit and missed target tracking
- Performance breakdown by:
  - League (NBA, NCAA M/W, etc.)
  - Game phase (pre-game, live, clutch)
  - Volatility regime
  - Liquidity depth
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class GamePhase(str, Enum):
    PRE_GAME = "pre_game"
    FIRST_HALF = "first_half"
    HALFTIME = "halftime"
    SECOND_HALF = "second_half"
    CLUTCH = "clutch"  # Last 5 minutes
    OVERTIME = "overtime"


class VolatilityRegime(str, Enum):
    LOW = "low"        # < 5% price change per minute
    MEDIUM = "medium"  # 5-15%
    HIGH = "high"      # > 15%


class LiquidityDepth(str, Enum):
    DEEP = "deep"      # > 1000 contracts
    NORMAL = "normal"  # 100-1000
    SHALLOW = "shallow"  # < 100


@dataclass
class TradePerformanceRecord:
    """Individual trade performance record"""
    trade_id: str
    model_id: str
    game_id: str
    market_ticker: str
    league: str
    
    # Trade details
    side: str
    direction: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    
    # Expected vs Actual
    expected_profit: float = 0.0
    actual_profit: float = 0.0
    slippage: float = 0.0  # Expected - Actual
    
    # Targets
    target_price: float = 0.0
    stop_loss: float = 0.0
    hit_target: bool = False
    hit_stop: bool = False
    
    # Context
    game_phase: GamePhase = GamePhase.PRE_GAME
    volatility_regime: VolatilityRegime = VolatilityRegime.MEDIUM
    liquidity_depth: LiquidityDepth = LiquidityDepth.NORMAL
    
    # Timestamps
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "model_id": self.model_id,
            "game_id": self.game_id,
            "market_ticker": self.market_ticker,
            "league": self.league,
            "side": self.side,
            "direction": self.direction,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "expected_profit": round(self.expected_profit, 2),
            "actual_profit": round(self.actual_profit, 2),
            "slippage": round(self.slippage, 2),
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "hit_target": self.hit_target,
            "hit_stop": self.hit_stop,
            "game_phase": self.game_phase.value,
            "volatility_regime": self.volatility_regime.value,
            "liquidity_depth": self.liquidity_depth.value,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None
        }


@dataclass
class ModelPerformanceMetrics:
    """Aggregated performance metrics for a model"""
    model_id: str
    model_name: str
    
    # Core metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # PnL
    total_expected_profit: float = 0.0
    total_actual_profit: float = 0.0
    total_slippage: float = 0.0
    average_slippage: float = 0.0
    
    # Target/Stop tracking
    targets_hit: int = 0
    stops_hit: int = 0
    target_hit_rate: float = 0.0
    stop_hit_rate: float = 0.0
    missed_targets: int = 0  # Closed without hitting target or stop
    
    # Risk-adjusted
    sharpe_like_score: float = 0.0
    max_drawdown: float = 0.0
    average_edge: float = 0.0
    
    # Breakdown by league
    by_league: Dict[str, Dict] = field(default_factory=dict)
    
    # Breakdown by game phase
    by_game_phase: Dict[str, Dict] = field(default_factory=dict)
    
    # Breakdown by volatility
    by_volatility: Dict[str, Dict] = field(default_factory=dict)
    
    # Breakdown by liquidity
    by_liquidity: Dict[str, Dict] = field(default_factory=dict)
    
    # Time tracking
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_expected_profit": round(self.total_expected_profit, 2),
            "total_actual_profit": round(self.total_actual_profit, 2),
            "total_slippage": round(self.total_slippage, 2),
            "average_slippage": round(self.average_slippage, 2),
            "targets_hit": self.targets_hit,
            "stops_hit": self.stops_hit,
            "target_hit_rate": round(self.target_hit_rate, 2),
            "stop_hit_rate": round(self.stop_hit_rate, 2),
            "missed_targets": self.missed_targets,
            "sharpe_like_score": round(self.sharpe_like_score, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "average_edge": round(self.average_edge, 3),
            "by_league": self.by_league,
            "by_game_phase": self.by_game_phase,
            "by_volatility": self.by_volatility,
            "by_liquidity": self.by_liquidity,
            "last_updated": self.last_updated.isoformat()
        }


class PerformanceTracker:
    """
    Tracks and analyzes performance across all trading models.
    
    Enables:
    - Expected vs actual profit comparison
    - Slippage analysis
    - Performance attribution by dimension
    - Model ranking and comparison
    """
    
    def __init__(self, db=None):
        """
        Initialize performance tracker.
        
        Args:
            db: MongoDB database instance for persistence
        """
        self.db = db
        
        # In-memory storage
        self._trades: Dict[str, TradePerformanceRecord] = {}  # trade_id -> record
        self._model_metrics: Dict[str, ModelPerformanceMetrics] = {}
        
        # Rolling windows for sharpe calculation
        self._daily_returns: Dict[str, List[float]] = defaultdict(list)
        
        logger.info("PerformanceTracker initialized")
    
    async def record_trade_entry(
        self,
        trade_id: str,
        model_id: str,
        model_name: str,
        game_id: str,
        market_ticker: str,
        league: str,
        side: str,
        direction: str,
        quantity: int,
        entry_price: float,
        expected_profit: float,
        target_price: float,
        stop_loss: float,
        game_phase: GamePhase = GamePhase.PRE_GAME,
        volatility_regime: VolatilityRegime = VolatilityRegime.MEDIUM,
        liquidity_depth: LiquidityDepth = LiquidityDepth.NORMAL
    ):
        """Record a new trade entry"""
        record = TradePerformanceRecord(
            trade_id=trade_id,
            model_id=model_id,
            game_id=game_id,
            market_ticker=market_ticker,
            league=league,
            side=side,
            direction=direction,
            quantity=quantity,
            entry_price=entry_price,
            expected_profit=expected_profit,
            target_price=target_price,
            stop_loss=stop_loss,
            game_phase=game_phase,
            volatility_regime=volatility_regime,
            liquidity_depth=liquidity_depth
        )
        
        self._trades[trade_id] = record
        
        # Initialize model metrics if needed
        if model_id not in self._model_metrics:
            self._model_metrics[model_id] = ModelPerformanceMetrics(
                model_id=model_id,
                model_name=model_name
            )
        
        # Store to DB if available
        if self.db is not None:
            await self.db.performance_trades.insert_one(record.to_dict())
        
        logger.info(f"Trade entry recorded: {trade_id} for {model_id}")
    
    async def record_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        hit_target: bool = False,
        hit_stop: bool = False
    ):
        """Record a trade exit and calculate performance"""
        if trade_id not in self._trades:
            logger.warning(f"Trade {trade_id} not found for exit recording")
            return
        
        record = self._trades[trade_id]
        record.exit_price = exit_price
        record.exit_time = datetime.now(timezone.utc)
        record.hit_target = hit_target
        record.hit_stop = hit_stop
        
        # Calculate actual profit (simplified - assumes YES side)
        if record.direction == "buy":
            record.actual_profit = (exit_price - record.entry_price) * record.quantity
        else:
            record.actual_profit = (record.entry_price - exit_price) * record.quantity
        
        # Calculate slippage
        record.slippage = record.expected_profit - record.actual_profit
        
        # Update model metrics
        await self._update_model_metrics(record)
        
        # Store to DB
        if self.db is not None:
            await self.db.performance_trades.update_one(
                {"trade_id": trade_id},
                {"$set": record.to_dict()}
            )
        
        logger.info(f"Trade exit recorded: {trade_id}, actual PnL: ${record.actual_profit:.2f}")
    
    async def _update_model_metrics(self, record: TradePerformanceRecord):
        """Update aggregated metrics for a model after trade exit"""
        metrics = self._model_metrics.get(record.model_id)
        if not metrics:
            return
        
        # Core counts
        metrics.total_trades += 1
        if record.actual_profit > 0:
            metrics.winning_trades += 1
        else:
            metrics.losing_trades += 1
        
        metrics.win_rate = metrics.winning_trades / metrics.total_trades * 100 if metrics.total_trades > 0 else 0
        
        # PnL
        metrics.total_expected_profit += record.expected_profit
        metrics.total_actual_profit += record.actual_profit
        metrics.total_slippage += record.slippage
        metrics.average_slippage = metrics.total_slippage / metrics.total_trades
        
        # Target/Stop tracking
        if record.hit_target:
            metrics.targets_hit += 1
        if record.hit_stop:
            metrics.stops_hit += 1
        if not record.hit_target and not record.hit_stop:
            metrics.missed_targets += 1
        
        metrics.target_hit_rate = metrics.targets_hit / metrics.total_trades * 100 if metrics.total_trades > 0 else 0
        metrics.stop_hit_rate = metrics.stops_hit / metrics.total_trades * 100 if metrics.total_trades > 0 else 0
        
        # Update breakdowns
        self._update_breakdown(metrics.by_league, record.league, record)
        self._update_breakdown(metrics.by_game_phase, record.game_phase.value, record)
        self._update_breakdown(metrics.by_volatility, record.volatility_regime.value, record)
        self._update_breakdown(metrics.by_liquidity, record.liquidity_depth.value, record)
        
        # Rolling returns for Sharpe
        self._daily_returns[record.model_id].append(record.actual_profit)
        
        # Calculate Sharpe-like score (simplified)
        returns = self._daily_returns[record.model_id][-100:]  # Last 100 trades
        if len(returns) >= 10:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            metrics.sharpe_like_score = (avg_return / std_return * 16) if std_return > 0 else 0  # Annualized-ish
        
        metrics.last_updated = datetime.now(timezone.utc)
    
    def _update_breakdown(
        self,
        breakdown: Dict,
        key: str,
        record: TradePerformanceRecord
    ):
        """Update a breakdown dictionary with trade data"""
        if key not in breakdown:
            breakdown[key] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "total_slippage": 0.0
            }
        
        b = breakdown[key]
        b["trades"] += 1
        
        if record.actual_profit > 0:
            b["wins"] += 1
        else:
            b["losses"] += 1
        
        b["win_rate"] = b["wins"] / b["trades"] * 100 if b["trades"] > 0 else 0
        b["total_pnl"] += record.actual_profit
        b["avg_pnl"] = b["total_pnl"] / b["trades"]
        b["total_slippage"] += record.slippage
    
    def get_model_metrics(self, model_id: str) -> Optional[Dict]:
        """Get performance metrics for a specific model"""
        if model_id in self._model_metrics:
            return self._model_metrics[model_id].to_dict()
        return None
    
    def get_all_model_metrics(self) -> Dict[str, Dict]:
        """Get metrics for all models"""
        return {k: v.to_dict() for k, v in self._model_metrics.items()}
    
    def get_comparison_table(self) -> Dict:
        """
        Get side-by-side comparison table of all models.
        
        Returns data suitable for dashboard display.
        """
        if not self._model_metrics:
            return {"models": [], "metrics": []}
        
        models = list(self._model_metrics.keys())
        
        metrics_rows = [
            {
                "metric": "Total Trades",
                "values": {m: self._model_metrics[m].total_trades for m in models}
            },
            {
                "metric": "Win Rate %",
                "values": {m: round(self._model_metrics[m].win_rate, 1) for m in models}
            },
            {
                "metric": "Expected Profit",
                "values": {m: round(self._model_metrics[m].total_expected_profit, 2) for m in models}
            },
            {
                "metric": "Actual Profit",
                "values": {m: round(self._model_metrics[m].total_actual_profit, 2) for m in models}
            },
            {
                "metric": "Total Slippage",
                "values": {m: round(self._model_metrics[m].total_slippage, 2) for m in models}
            },
            {
                "metric": "Avg Slippage",
                "values": {m: round(self._model_metrics[m].average_slippage, 2) for m in models}
            },
            {
                "metric": "Target Hit %",
                "values": {m: round(self._model_metrics[m].target_hit_rate, 1) for m in models}
            },
            {
                "metric": "Stop Hit %",
                "values": {m: round(self._model_metrics[m].stop_hit_rate, 1) for m in models}
            },
            {
                "metric": "Sharpe-like Score",
                "values": {m: round(self._model_metrics[m].sharpe_like_score, 2) for m in models}
            }
        ]
        
        return {
            "models": models,
            "metrics": metrics_rows
        }
    
    def get_league_breakdown(self, model_id: str) -> Dict:
        """Get performance breakdown by league for a model"""
        if model_id not in self._model_metrics:
            return {}
        return self._model_metrics[model_id].by_league
    
    def get_recent_trades(self, model_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get recent trade records"""
        trades = list(self._trades.values())
        
        if model_id:
            trades = [t for t in trades if t.model_id == model_id]
        
        # Sort by entry time descending
        trades.sort(key=lambda t: t.entry_time, reverse=True)
        
        return [t.to_dict() for t in trades[:limit]]
    
    async def initialize_from_db(self):
        """Load historical data from database"""
        if self.db is None:
            return
        
        try:
            cursor = self.db.performance_trades.find({}).sort("entry_time", -1).limit(1000)
            async for doc in cursor:
                record = TradePerformanceRecord(**doc)
                self._trades[record.trade_id] = record
                
                # Rebuild metrics
                if record.exit_price is not None:
                    if record.model_id not in self._model_metrics:
                        self._model_metrics[record.model_id] = ModelPerformanceMetrics(
                            model_id=record.model_id,
                            model_name=record.model_id
                        )
                    await self._update_model_metrics(record)
            
            logger.info(f"Loaded {len(self._trades)} historical trades")
            
        except Exception as e:
            logger.error(f"Failed to load from DB: {e}")


# Global instance
performance_tracker: Optional[PerformanceTracker] = None
