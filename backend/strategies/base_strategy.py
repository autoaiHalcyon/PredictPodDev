"""
Base Strategy - Abstract base class for all trading strategies.

Each strategy:
- Receives market data from single feed
- Applies its own execution rules
- Maintains independent virtual portfolio
- Logs decisions independently
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal, SignalType
from strategies.virtual_portfolio import VirtualPortfolio, VirtualTrade, VirtualPosition

try:
    from services import decision_tracer as _tracer
except ImportError:
    _tracer = None  # Tracer unavailable — decisions still execute normally

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Types of strategy decisions."""
    ENTER = "ENTER"
    EXIT = "EXIT"
    TRIM = "TRIM"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


@dataclass
class StrategyDecision:
    """A decision made by a strategy."""
    decision_type: DecisionType
    reason: str
    market_id: str = ""
    game_id: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    edge: float = 0.0
    signal_score: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "market_id": self.market_id,
            "game_id": self.game_id,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "edge": self.edge,
            "signal_score": self.signal_score,
            "timestamp": self.timestamp.isoformat()
        }


class StrategyConfig:
    """Configuration wrapper for strategy parameters."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config: Dict = {}
        self.load()
    
    def load(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            self._config = {}
    
    def reload(self):
        """Reload configuration from file."""
        self.load()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation support."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    @property
    def model_id(self) -> str:
        return self._config.get("model_id", "unknown")
    
    @property
    def display_name(self) -> str:
        return self._config.get("display_name", "Unknown Strategy")
    
    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)
    
    @property
    def starting_capital(self) -> float:
        return self._config.get("starting_capital", 10000.0)
    
    @property
    def entry_rules(self) -> Dict:
        return self._config.get("entry_rules", {})
    
    @property
    def exit_rules(self) -> Dict:
        return self._config.get("exit_rules", {})
    
    @property
    def position_sizing(self) -> Dict:
        return self._config.get("position_sizing", {})
    
    @property
    def risk_limits(self) -> Dict:
        return self._config.get("risk_limits", {})
    
    @property
    def filters(self) -> Dict:
        return self._config.get("filters", {})
    
    @property
    def trim_rules(self) -> Dict:
        return self._config.get("trim_rules", {})
    
    @property
    def circuit_breakers(self) -> Dict:
        return self._config.get("circuit_breakers", {})


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    Each strategy must implement:
    - evaluate_entry(): Decide if should enter a position
    - evaluate_exit(): Decide if should exit a position
    - calculate_size(): Determine position size
    """
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.strategy_id = config.model_id
        self.display_name = config.display_name
        
        # Virtual portfolio
        self.portfolio = VirtualPortfolio(
            strategy_id=self.strategy_id,
            starting_capital=config.starting_capital
        )
        
        # Decision log
        self._decision_log: List[StrategyDecision] = []
        self._max_log_size = 1000
        
        # Edge persistence tracking (for multi-tick confirmation)
        self._edge_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Cooldown tracking per game
        self._last_entry_time: Dict[str, datetime] = {}
        self._entries_per_game: Dict[str, int] = {}
        
        # State
        self._enabled = config.enabled
        self._last_tick_time: Optional[datetime] = None
        
        logger.info(f"Strategy {self.display_name} initialized")
    
    # ==========================================
    # ABSTRACT METHODS
    # ==========================================
    
    @abstractmethod
    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """
        Evaluate whether to enter a position.
        
        Returns StrategyDecision if should enter, None otherwise.
        """
        pass
    
    @abstractmethod
    def evaluate_exit(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        position: VirtualPosition,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """
        Evaluate whether to exit a position.
        
        Returns StrategyDecision if should exit, None otherwise.
        """
        pass
    
    @abstractmethod
    def calculate_size(
        self,
        signal: Signal,
        available_capital: float
    ) -> int:
        """
        Calculate position size in contracts.
        """
        pass
    
    # ==========================================
    # CORE METHODS
    # ==========================================
    
    def process_tick(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None,
        volume_5m: Optional[float] = None,
        volume_60m: Optional[float] = None,
    ) -> Optional[StrategyDecision]:
        """
        Process a market tick and make trading decision.
        
        This is the main entry point called by the strategy manager.
        Every decision path writes one JSON-Lines record via decision_tracer.
        """
        if not self._enabled:
            return None
        
        self._last_tick_time = datetime.utcnow()
        
        # Update edge history for persistence tracking
        self._update_edge_history(market.id, signal.edge)
        
        # Update position prices
        if self.portfolio.has_position(market.id):
            self.portfolio.update_position_price(market.id, market.implied_probability)
        
        decision: Optional[StrategyDecision] = None
        position = self.portfolio.get_position(market.id)

        # Check circuit breaker
        if self.portfolio.is_circuit_breaker_active:
            decision = StrategyDecision(
                decision_type=DecisionType.CIRCUIT_BREAKER,
                reason="Circuit breaker active",
                market_id=market.id,
                game_id=game.id
            )
            self._log_decision(decision)
            self._trace(game, market, signal, decision, orderbook, position, volume_5m, volume_60m)
            return decision
        
        # Check risk limits
        risk_block = self._check_risk_limits()
        if risk_block:
            decision = StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=risk_block,
                market_id=market.id,
                game_id=game.id
            )
            self._log_decision(decision)
            self._trace(game, market, signal, decision, orderbook, position, volume_5m, volume_60m)
            return decision
        
        if position:
            # Evaluate exit
            exit_decision = self.evaluate_exit(game, market, signal, position, orderbook)
            if exit_decision:
                self._execute_decision(exit_decision)
                self._trace(game, market, signal, exit_decision, orderbook, position, volume_5m, volume_60m)
                return exit_decision
            
            # Check trim
            trim_decision = self._evaluate_trim(game, market, signal, position)
            if trim_decision:
                self._execute_decision(trim_decision)
                self._trace(game, market, signal, trim_decision, orderbook, position, volume_5m, volume_60m)
                return trim_decision
            
            # Hold
            decision = StrategyDecision(
                decision_type=DecisionType.HOLD,
                reason="Position held",
                market_id=market.id,
                game_id=game.id
            )
            self._trace(game, market, signal, decision, orderbook, position, volume_5m, volume_60m)
            return decision
        else:
            # Evaluate entry
            entry_decision = self.evaluate_entry(game, market, signal, orderbook)
            if entry_decision:
                self._execute_decision(entry_decision)
                self._trace(game, market, signal, entry_decision, orderbook, None, volume_5m, volume_60m)
                return entry_decision
        
        # NO_TRADE — no position and no entry signal fired
        self._trace(game, market, signal, None, orderbook, None, volume_5m, volume_60m)
        return None

    def _trace(
        self,
        game,
        market,
        signal,
        decision,
        orderbook,
        position,
        volume_5m,
        volume_60m,
    ):
        """Write one decision-trace JSONL record (best-effort; never raises)."""
        if _tracer is None:
            return
        _tracer.write_decision(
            game=game,
            market=market,
            signal=signal,
            decision=decision,
            strategy=self,
            orderbook=orderbook,
            position=position,
            volume_5m=volume_5m,
            volume_60m=volume_60m,
        )
    
    def _execute_decision(self, decision: StrategyDecision):
        """Execute a trading decision."""
        if decision.decision_type == DecisionType.ENTER:
            trade = self.portfolio.open_position(
                market_id=decision.market_id,
                game_id=decision.game_id,
                side=decision.side,
                quantity=decision.quantity,
                price=decision.price,
                edge=decision.edge,
                signal_score=decision.signal_score,
                reason=decision.reason
            )
            
            if trade:
                # Track entries per game
                if decision.game_id not in self._entries_per_game:
                    self._entries_per_game[decision.game_id] = 0
                self._entries_per_game[decision.game_id] += 1
                self._last_entry_time[decision.game_id] = datetime.utcnow()
        
        elif decision.decision_type in [DecisionType.EXIT, DecisionType.TRIM]:
            self.portfolio.close_position(
                market_id=decision.market_id,
                price=decision.price,
                quantity=decision.quantity if decision.decision_type == DecisionType.TRIM else None,
                edge_at_exit=decision.edge,
                reason=decision.reason
            )
        
        self._log_decision(decision)
        
        # Check for circuit breaker triggers
        self._check_circuit_breakers()
    
    # ==========================================
    # HELPER METHODS
    # ==========================================
    
    def _update_edge_history(self, market_id: str, edge: float):
        """Track edge over time for persistence checks."""
        now = datetime.utcnow()
        
        if market_id not in self._edge_history:
            self._edge_history[market_id] = []
        
        self._edge_history[market_id].append((now, edge))
        
        # Keep only last 2 minutes
        cutoff = now - timedelta(minutes=2)
        self._edge_history[market_id] = [
            (t, e) for t, e in self._edge_history[market_id] if t > cutoff
        ]
    
    def check_edge_persistence(self, market_id: str, min_ticks: int, min_edge: float) -> bool:
        """Check if edge has persisted above threshold for N ticks."""
        history = self._edge_history.get(market_id, [])
        
        if len(history) < min_ticks:
            return False
        
        # Check last N ticks
        recent = history[-min_ticks:]
        return all(e >= min_edge for _, e in recent)
    
    def check_cooldown(self, game_id: str) -> bool:
        """Check if cooldown period has passed for a game."""
        cooldown_seconds = self.config.entry_rules.get("cooldown_seconds", 120)
        
        last_entry = self._last_entry_time.get(game_id)
        if not last_entry:
            return True
        
        elapsed = (datetime.utcnow() - last_entry).total_seconds()
        return elapsed >= cooldown_seconds
    
    def check_max_entries(self, game_id: str) -> bool:
        """Check if max entries per game reached."""
        max_entries = self.config.entry_rules.get("max_entries_per_game", 5)
        current_entries = self._entries_per_game.get(game_id, 0)
        return current_entries < max_entries
    
    def check_filters(self, game: Game, market: Market, orderbook: Optional[Dict]) -> Tuple[bool, str]:
        """Check market filters. Returns (passes, reason)."""
        filters = self.config.filters
        
        # League filter
        allowed_leagues = filters.get("allowed_leagues", ["NBA", "NCAA_M", "NCAA_W"])
        game_league = self._infer_league(game)
        if game_league not in allowed_leagues:
            return False, f"League {game_league} not allowed"
        
        # Game progress filter
        min_progress = filters.get("min_game_progress", 0.0)
        max_progress = filters.get("max_game_progress", 1.0)
        if game.game_progress < min_progress:
            return False, f"Game progress {game.game_progress:.0%} below min {min_progress:.0%}"
        if game.game_progress > max_progress:
            return False, f"Game progress {game.game_progress:.0%} above max {max_progress:.0%}"
        
        # Spread filter
        max_spread = filters.get("max_spread_pct", 0.10)
        if market.spread and market.spread > max_spread:
            return False, f"Spread {market.spread:.1%} exceeds max {max_spread:.1%}"
        
        # Liquidity filter
        min_liquidity = filters.get("min_liquidity_contracts", 0)
        if orderbook:
            total_liquidity = orderbook.get("total_liquidity", 0)
            if total_liquidity < min_liquidity:
                return False, f"Liquidity {total_liquidity} below min {min_liquidity}"
        
        return True, "Filters passed"
    
    def _infer_league(self, game: Game) -> str:
        """Infer league from game data."""
        game_id_upper = game.id.upper()
        if "NCAAM" in game_id_upper or "NCAA_M" in game_id_upper:
            return "NCAA_M"
        elif "NCAAW" in game_id_upper or "NCAA_W" in game_id_upper:
            return "NCAA_W"
        elif "NBA" in game_id_upper:
            return "NBA"
        
        # Try game attributes
        if hasattr(game, 'league'):
            return game.league
        
        return "NBA"  # Default fallback
    
    def _evaluate_trim(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        position: VirtualPosition
    ) -> Optional[StrategyDecision]:
        """Evaluate whether to trim position."""
        trim_rules = self.config.trim_rules
        
        if not trim_rules.get("enable_trim", False):
            return None
        
        # Trim at profit target
        profit_threshold = trim_rules.get("trim_at_profit_pct", 0.10)
        if position.unrealized_pnl_pct >= profit_threshold:
            trim_qty = int(position.quantity * trim_rules.get("trim_size_pct", 0.50))
            if trim_qty > 0:
                return StrategyDecision(
                    decision_type=DecisionType.TRIM,
                    reason=f"Profit target {profit_threshold:.0%} reached",
                    market_id=market.id,
                    game_id=game.id,
                    side=position.side,
                    quantity=trim_qty,
                    price=market.implied_probability,
                    edge=signal.edge
                )
        
        # Trim on edge decay
        if trim_rules.get("trim_on_edge_decay", False):
            decay_threshold = trim_rules.get("edge_decay_threshold", 0.02)
            if signal.edge < position.entry_edge - decay_threshold:
                trim_qty = int(position.quantity * trim_rules.get("trim_size_pct", 0.50))
                if trim_qty > 0:
                    return StrategyDecision(
                        decision_type=DecisionType.TRIM,
                        reason=f"Edge decay below {decay_threshold:.0%}",
                        market_id=market.id,
                        game_id=game.id,
                        side=position.side,
                        quantity=trim_qty,
                        price=market.implied_probability,
                        edge=signal.edge
                    )
        
        return None
    
    def _check_risk_limits(self) -> Optional[str]:
        """Check risk limits. Returns block reason if violated."""
        limits = self.config.risk_limits
        
        # Daily loss limit
        max_daily_loss_pct = limits.get("max_daily_loss_pct", 0.10)
        if self.portfolio.check_daily_loss_limit(max_daily_loss_pct):
            return f"Daily loss limit {max_daily_loss_pct:.0%} reached"
        
        # Max exposure
        max_exposure_pct = limits.get("max_exposure_pct", 0.30)
        if self.portfolio.risk_utilization / 100 >= max_exposure_pct:
            return f"Max exposure {max_exposure_pct:.0%} reached"
        
        # Max open trades (concurrent positions)
        max_open_trades = limits.get("max_open_trades", 999)
        if len(self.portfolio.get_all_positions()) >= max_open_trades:
            return f"Max open trades limit {max_open_trades} reached"
        
        # Hourly trade limit
        max_per_hour = limits.get("max_trades_per_hour", 10)
        if self.portfolio._trades_this_hour >= max_per_hour:
            return f"Hourly trade limit {max_per_hour} reached"
        
        # Daily trade limit
        max_per_day = limits.get("max_trades_per_day", 50)
        if self.portfolio._trades_today >= max_per_day:
            return f"Daily trade limit {max_per_day} reached"
        
        # Drawdown limit
        max_drawdown_pct = limits.get("max_drawdown_pct", 0.15)
        if self.portfolio.check_drawdown_limit(max_drawdown_pct):
            return f"Max drawdown {max_drawdown_pct:.0%} reached"
        
        return None
    
    def _check_circuit_breakers(self):
        """Check and activate circuit breakers if needed."""
        breakers = self.config.circuit_breakers
        
        # Consecutive losses
        max_losses = breakers.get("pause_on_consecutive_losses", 5)
        if self.portfolio._consecutive_losses >= max_losses:
            duration = breakers.get("pause_duration_seconds", 600)
            self.portfolio.activate_circuit_breaker(duration)
            return
        
        # Drawdown
        drawdown_trigger = breakers.get("pause_on_drawdown_pct", 0.10)
        if self.portfolio.max_drawdown_pct >= (drawdown_trigger * 100):
            if not breakers.get("require_manual_reset", False):
                duration = breakers.get("pause_duration_seconds", 600)
                self.portfolio.activate_circuit_breaker(duration)
    
    def _log_decision(self, decision: StrategyDecision):
        """Log a decision."""
        self._decision_log.append(decision)
        
        # Trim log if too large
        if len(self._decision_log) > self._max_log_size:
            self._decision_log = self._decision_log[-self._max_log_size:]
        
        # Log to file
        log_level = logging.INFO if decision.decision_type in [DecisionType.ENTER, DecisionType.EXIT] else logging.DEBUG
        logger.log(
            log_level,
            f"[{self.strategy_id}] {decision.decision_type.value}: {decision.reason} | "
            f"Market: {decision.market_id} | Edge: {decision.edge:.2%}"
        )
    
    # ==========================================
    # PUBLIC API
    # ==========================================
    
    def enable(self):
        """Enable strategy."""
        self._enabled = True
        logger.info(f"Strategy {self.display_name} ENABLED")
    
    def disable(self):
        """Disable strategy."""
        self._enabled = False
        logger.info(f"Strategy {self.display_name} DISABLED")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def reset_portfolio(self, starting_capital: Optional[float] = None):
        """Reset portfolio to initial state."""
        self.portfolio.reset(starting_capital)
        self._entries_per_game.clear()
        self._last_entry_time.clear()
        self._edge_history.clear()
    
    def get_summary(self) -> Dict:
        """Get strategy summary for dashboard."""
        return {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "enabled": self._enabled,
            "last_tick": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "portfolio": self.portfolio.get_summary(),
            "config": {
                "min_edge": self.config.entry_rules.get("min_edge_threshold", 0),
                "cooldown": self.config.entry_rules.get("cooldown_seconds", 0),
                "max_daily_loss": self.config.risk_limits.get("max_daily_loss_pct", 0)
            }
        }
    
    def get_decision_log(self, limit: int = 100) -> List[Dict]:
        """Get recent decisions."""
        return [d.to_dict() for d in self._decision_log[-limit:]]
    
    def get_positions_summary(self) -> List[Dict]:
        """Get all positions summary."""
        return [p.to_dict() for p in self.portfolio.get_all_positions()]
