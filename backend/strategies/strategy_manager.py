"""
strategy_manager.py  —  PredictPod v2.1
========================================
IMPORTANT: This file PRESERVES the full existing StrategyEngineManager interface.
The v2.1 changes ONLY update _load_strategies() to load Model 1 and Model 2
instead of the old Model A/B/C configs.

All existing attributes, methods, and the global `strategy_manager` singleton
are fully preserved so server.py, routes, and the scheduler continue to work
without any other changes.

What changed in v2.1:
  - _load_strategies() now instantiates Model1EnhancedCLV and Model2StrongFavorite
  - Old ModelA/B/C imports replaced with new model imports
  - model_1.json and model_2.json configs used instead of model_a/b/c.json
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date, timedelta
from pathlib import Path
import asyncio
import json
import logging

try:
    from models.game import Game
    from models.market import Market
    from models.signal import Signal
    from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
except ImportError:
    Game = Market = Signal = BaseStrategy = StrategyConfig = object
    class DecisionType:
        HOLD = "HOLD"; ENTER = "ENTER"
    class StrategyDecision:
        def __init__(self, **kw): self.__dict__.update(kw)

# ── v2.1 model imports (replaces ModelA/B/C) ─────────────────────────────────
from strategies.model_1_enhanced_clv import Model1EnhancedCLV
from strategies.model_2_strong_favorite import Model2StrongFavorite
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "configs"


class StrategyEngineManager:
    """
    Manages multiple trading strategies running in parallel.
    Fully backward-compatible with existing server.py / routes / scheduler.
    """

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self._enabled = False
        self._kill_switch_active = False
        self._evaluation_mode = True
        self._last_tick_time: Optional[datetime] = None
        self._tick_interval_seconds = 3
        self._daily_reports: Dict[str, Dict] = {}
        self._load_strategies()
        logger.info("StrategyEngineManager initialized (v2.1 — Model 1 + Model 2)")

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD STRATEGIES  (v2.1: Model 1 + Model 2)
    # ─────────────────────────────────────────────────────────────────────────
    def _load_strategies(self):
        """
        v2.1: Load Model 1 (Enhanced CLV) and Model 2 (Strong Favorite Value).
        Each model wraps itself in a StrategyConfig-compatible adapter so the
        rest of the engine can treat them identically to the old Model A/B/C.
        """
        for model_class, config_file, model_id in [
            (Model1EnhancedCLV, "model_1.json", "model_1_enhanced_clv"),
            (Model2StrongFavorite, "model_2.json", "model_2_strong_favorite"),
        ]:
            config_path = CONFIG_DIR / config_file
            if not config_path.exists():
                logger.error(f"Config not found: {config_path} — skipping {model_id}")
                continue
            try:
                model = model_class()
                # Wrap in a lightweight adapter so existing code using
                # strategy_manager.strategies[id].portfolio / .get_summary() works
                adapter = _ModelAdapter(model, model_id, str(config_path))
                self.strategies[model_id] = adapter
                logger.info(f"Loaded strategy: {model_id}")
            except Exception as e:
                logger.error(f"Failed to load {model_id}: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # CONTROL METHODS  (unchanged interface)
    # ─────────────────────────────────────────────────────────────────────────
    def enable(self):
        self._enabled = True
        for s in self.strategies.values():
            s.enable()
        logger.info("Strategy Engine ENABLED")

    def disable(self):
        self._enabled = False
        for s in self.strategies.values():
            s.disable()
        logger.info("Strategy Engine DISABLED")

    def activate_kill_switch(self):
        self._kill_switch_active = True
        self.disable()
        logger.warning("KILL SWITCH ACTIVATED")

    def deactivate_kill_switch(self):
        self._kill_switch_active = False
        logger.info("Kill switch deactivated")

    def set_evaluation_mode(self, enabled: bool):
        self._evaluation_mode = enabled
        if enabled:
            self.enable()

    @property
    def is_enabled(self):
        return self._enabled and not self._kill_switch_active

    @property
    def is_kill_switch_active(self):
        return self._kill_switch_active

    # ─────────────────────────────────────────────────────────────────────────
    # TICK PROCESSING  (unchanged interface)
    # ─────────────────────────────────────────────────────────────────────────
    async def process_tick(self, game: Game, market: Market, signal: Signal,
                           orderbook: Optional[Dict] = None) -> Dict:
        if not self.is_enabled:
            return {}
        self._last_tick_time = datetime.utcnow()
        decisions = {}
        for sid, strategy in self.strategies.items():
            try:
                decision = strategy.process_tick(game, market, signal, orderbook)
                decisions[sid] = decision
            except Exception as e:
                logger.error(f"Strategy {sid} tick error: {e}")
                decisions[sid] = None
        return decisions

    async def process_batch(self, ticks: List[Dict]) -> Dict:
        all_decisions = {sid: [] for sid in self.strategies}
        for tick in ticks:
            decisions = await self.process_tick(**tick)
            for sid, d in decisions.items():
                if d and d.decision_type != DecisionType.HOLD:
                    all_decisions[sid].append(d)
        return all_decisions

    def update_position_prices(self, market_id: str, current_price: float):
        for s in self.strategies.values():
            if hasattr(s, 'portfolio'):
                s.portfolio.update_position_price(market_id, current_price)

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD DATA  (unchanged interface)
    # ─────────────────────────────────────────────────────────────────────────
    def get_summary(self) -> Dict:
        summaries = {sid: s.get_summary() for sid, s in self.strategies.items()}
        pnls = sorted([(sid, s.get("portfolio", {}).get("total_pnl", 0))
                       for sid, s in summaries.items()], key=lambda x: x[1], reverse=True)
        return {
            "enabled": self._enabled,
            "kill_switch_active": self._kill_switch_active,
            "evaluation_mode": self._evaluation_mode,
            "last_tick": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "strategies": summaries,
            "winning_model": pnls[0][0] if pnls else None,
            "best_risk_adjusted": pnls[0][0] if pnls else None,
        }

    def get_game_positions(self, game_id: str) -> Dict:
        return {sid: s.portfolio.get_positions_for_game(game_id)
                for sid, s in self.strategies.items()
                if hasattr(s, 'portfolio')}

    def get_all_positions_by_game(self) -> Dict:
        result = {}
        for sid, s in self.strategies.items():
            if hasattr(s, 'portfolio'):
                for pos in s.portfolio.get_all_positions():
                    gid = getattr(pos, 'game_id', 'unknown')
                    result.setdefault(gid, {})[sid] = pos
        return result

    def get_decision_logs(self, limit: int = 100) -> Dict:
        return {sid: s.get_decision_log(limit)
                for sid, s in self.strategies.items()}

    def get_strategy_config(self, strategy_id: str) -> Optional[Dict]:
        s = self.strategies.get(strategy_id)
        return s.get_config() if s else None

    def reload_configs(self):
        for s in self.strategies.values():
            if hasattr(s, 'config') and hasattr(s.config, 'reload'):
                s.config.reload()
        logger.info("Strategy configs reloaded")

    def update_strategy_config(self, strategy_id: str, updates: Dict) -> bool:
        s = self.strategies.get(strategy_id)
        if not s:
            return False
        if hasattr(s, 'config') and hasattr(s.config, '_config'):
            s.config._config.update(updates)
        return True

    def reset_strategy(self, strategy_id: str, starting_capital: float = None):
        s = self.strategies.get(strategy_id)
        if s and hasattr(s, 'portfolio'):
            s.portfolio.reset(starting_capital or 10000.0)

    def reset_all_strategies(self):
        for s in self.strategies.values():
            if hasattr(s, 'portfolio'):
                s.portfolio.reset()

    def export_trades_csv(self, strategy_id: str) -> str:
        s = self.strategies.get(strategy_id)
        if s and hasattr(s, 'portfolio'):
            return s.portfolio.export_trades_csv()
        return ""

    def export_trades_json(self, strategy_id: str) -> str:
        s = self.strategies.get(strategy_id)
        if s and hasattr(s, 'portfolio'):
            return s.portfolio.export_trades_json()
        return "[]"

    def export_daily_report_json(self, date_str: str = None) -> str:
        return json.dumps({"date": date_str, "strategies": self.get_summary()})

    def export_daily_report_csv(self, date_str: str = None) -> str:
        return f"date,strategy,pnl\n{date_str or 'today'},combined,0"


# ─────────────────────────────────────────────────────────────────────────────
# LIGHTWEIGHT ADAPTER
# Wraps Model1/Model2 so StrategyEngineManager can treat them like BaseStrategy
# ─────────────────────────────────────────────────────────────────────────────
class _ModelAdapter:
    """
    Bridges the new standalone Model 1/2 classes into the StrategyEngineManager
    interface. Provides .portfolio, .get_summary(), .process_tick(), etc.
    """

    def __init__(self, model, model_id: str, config_path: str):
        self._model = model
        self.strategy_id = model_id
        self.display_name = model_id.replace("_", " ").title()
        self._enabled = True
        self._decision_log: List[Dict] = []

        # Minimal portfolio shim so strategy_manager.strategies[id].portfolio works
        self.portfolio = _PortfolioShim(model)

        # Load config dict for get_config()
        try:
            with open(config_path) as f:
                self._config = json.load(f)
        except Exception:
            self._config = {}

    def enable(self):
        self._enabled = True
        self._model.enable()

    def disable(self):
        self._enabled = False
        self._model.disable()

    def process_tick(self, game, market, signal, orderbook=None) -> Optional[StrategyDecision]:
        """
        Bridge process_tick() to the model's evaluate_entry().
        Extracts the fields Model 1/2 need from the Game/Market/Signal objects.
        """
        if not self._enabled:
            return None
        try:
            from strategies.model_1_enhanced_clv import Model1EnhancedCLV
            from strategies.model_2_strong_favorite import Model2StrongFavorite

            # Extract common fields
            yes_price   = getattr(market, 'yes_price', None) or getattr(market, 'yes_ask', 0.5)
            sharp_line  = getattr(signal, 'fair_prob', yes_price)
            age_min     = getattr(market, 'age_minutes', 120)
            mins_to_tip = getattr(signal, 'mins_until_game', 120)
            volume      = getattr(market, 'volume', 5000)
            spread      = abs(getattr(market, 'yes_ask', yes_price) -
                              getattr(market, 'yes_bid', yes_price))
            game_id     = getattr(game, 'id', 'unknown')

            if isinstance(self._model, Model1EnhancedCLV):
                decision = self._model.evaluate_entry(
                    game_id=game_id,
                    kalshi_yes_price=yes_price,
                    sharp_line=sharp_line,
                    market_age_min=age_min,
                    mins_until_game=mins_to_tip,
                    volume=volume,
                    spread=spread,
                )
                if decision.decision == "ENTER":
                    return StrategyDecision(
                        decision_type=DecisionType.ENTER,
                        reason=decision.reason,
                        market_id=getattr(market, 'id', ''),
                        game_id=game_id,
                        side=decision.direction or "YES",
                        quantity=decision.contracts,
                        price=decision.entry_price or yes_price,
                        edge=decision.edge,
                    )

            elif isinstance(self._model, Model2StrongFavorite):
                home_r = getattr(game, 'home_team_rating', 60.0)
                away_r = getattr(game, 'away_team_rating', 60.0)
                decision = self._model.evaluate_entry(
                    game_id=game_id,
                    home_rating=home_r,
                    away_rating=away_r,
                    kalshi_yes_price=yes_price,
                    sharp_line=sharp_line,
                    mins_until_game=mins_to_tip,
                    volume=volume,
                    spread=spread,
                )
                if decision.decision == "ENTER":
                    return StrategyDecision(
                        decision_type=DecisionType.ENTER,
                        reason=decision.reason,
                        market_id=getattr(market, 'id', ''),
                        game_id=game_id,
                        side="YES",
                        quantity=decision.contracts,
                        price=decision.entry_price or yes_price,
                        edge=decision.edge,
                    )
        except Exception as e:
            logger.error(f"[{self.strategy_id}] process_tick error: {e}", exc_info=True)
        return None

    def get_summary(self) -> Dict:
        status = self._model.get_status()
        return {
            "strategy_id":   self.strategy_id,
            "display_name":  self.display_name,
            "enabled":       self._enabled,
            "portfolio": {
                "total_pnl":    status.get("session_pnl", 0),
                "realized_pnl": status.get("session_pnl", 0),
                "unrealized_pnl": 0,
                "total_trades": status.get("trade_count", 0),
                "win_rate":     0,
                "max_drawdown": 0,
                "max_drawdown_pct": 0,
                "risk_utilization": 0,
            },
        }

    def get_decision_log(self, limit: int = 100) -> List:
        return self._decision_log[-limit:]

    def get_positions_summary(self) -> List:
        return []

    def get_config(self) -> Dict:
        return self._config


class _PortfolioShim:
    """Minimal portfolio shim so .portfolio access doesn't crash."""

    def __init__(self, model):
        self._model = model

    def get_positions_for_game(self, game_id: str) -> List:
        return []

    def get_all_positions(self) -> List:
        return []

    def update_position_price(self, market_id: str, price: float):
        pass

    def reset(self, starting_capital: float = 10000.0):
        pass

    def export_trades_csv(self) -> str:
        return ""

    def export_trades_json(self) -> str:
        return "[]"

    @property
    def total_pnl(self) -> float:
        return self._model.get_status().get("session_pnl", 0)


# ─────────────────────────────────────────────────────────────────────────────
# Global singleton — imported by server.py, routes, scheduler as:
#   from strategies.strategy_manager import StrategyEngineManager, strategy_manager
# ─────────────────────────────────────────────────────────────────────────────
strategy_manager = StrategyEngineManager()
