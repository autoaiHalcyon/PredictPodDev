"""
strategy_manager.py
====================
PredictPod — Strategy Manager v2.1
Orchestrates Model 1 (Enhanced CLV) and Model 2 (Strong Favorite Value).
Handles conflict resolution, circuit breakers, and session tracking.

Version: 2.1.0  |  Updated: 2026-03-06
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from strategies.model_1_enhanced_clv import Model1EnhancedCLV, M1Decision
from strategies.model_2_strong_favorite import Model2StrongFavorite, M2Decision

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Central coordinator for all PredictPod trading models.

    Responsibilities:
    - Route market ticks to both models
    - Enforce conflict rule: M1 and M2 cannot both have open positions on same game
    - Circuit breaker: pause model after N consecutive losses
    - Session-level P&L and trade count tracking
    - Kill switch for emergency shutdown
    """

    def __init__(self):
        self.model1 = Model1EnhancedCLV()
        self.model2 = Model2StrongFavorite()

        self._kill_switch = False
        self._session_start = datetime.utcnow()

        # Circuit breaker state
        self._cb: Dict[str, dict] = {
            "model_1": {"consecutive_losses": 0, "paused_until": None, "max_losses": 4},
            "model_2": {"consecutive_losses": 0, "paused_until": None, "max_losses": 3},
        }

        # Open position registry (game_id → which model has it)
        self._game_positions: Dict[str, str] = {}   # game_id → "model_1" | "model_2"

        # Trade history
        self._trades: List[dict] = []

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: EVALUATE BOTH MODELS ON A GAME TICK
    # ─────────────────────────────────────────────────────────────────────────
    def evaluate(
        self,
        game_id:          str,
        # Market data
        kalshi_yes_price: float,
        sharp_line:       float,
        market_age_min:   int,
        mins_until_game:  int,
        volume:           int,
        spread:           float,
        # For Model 2 fair value
        home_rating:      float = 60.0,
        away_rating:      float = 60.0,
        home_rest:        int   = 1,
        away_rest:        int   = 1,
    ) -> dict:
        """
        Evaluate both models for a single game tick.
        Returns decision dict with both model outcomes.
        """
        if self._kill_switch:
            return {"status": "KILL_SWITCH_ACTIVE", "game_id": game_id}

        results = {"game_id": game_id, "timestamp": datetime.utcnow().isoformat()}

        # ── Model 1 ─────────────────────────────────────────────────────────
        m1_blocked_by_cb = self._is_circuit_broken("model_1")
        m1_blocked_by_conflict = game_id in self._game_positions and \
                                  self._game_positions[game_id] == "model_2"

        if m1_blocked_by_cb:
            results["model_1"] = {"decision": "BLOCK", "reason": "CIRCUIT_BREAKER"}
        elif m1_blocked_by_conflict:
            results["model_1"] = {"decision": "BLOCK", "reason": "CONFLICT_M2_OPEN"}
        else:
            d1: M1Decision = self.model1.evaluate_entry(
                game_id, kalshi_yes_price, sharp_line,
                market_age_min, mins_until_game, volume, spread
            )
            results["model_1"] = {
                "decision":    d1.decision,
                "reason":      d1.reason,
                "fails":       d1.fails,
                "edge":        d1.edge,
                "direction":   d1.direction,
                "contracts":   d1.contracts,
                "dollar_amt":  d1.dollar_amt,
                "entry_price": d1.entry_price,
                "gate_log":    d1.gate_log,
            }
            if d1.decision == "ENTER":
                self._game_positions[game_id] = "model_1"
                logger.info(f"[MGR] Model 1 entered game={game_id}")

        # ── Model 2 ─────────────────────────────────────────────────────────
        m2_blocked_by_cb = self._is_circuit_broken("model_2")
        m2_blocked_by_conflict = game_id in self._game_positions and \
                                  self._game_positions[game_id] == "model_1"

        if m2_blocked_by_cb:
            results["model_2"] = {"decision": "BLOCK", "reason": "CIRCUIT_BREAKER"}
        elif m2_blocked_by_conflict:
            results["model_2"] = {"decision": "BLOCK", "reason": "CONFLICT_M1_OPEN"}
        else:
            d2: M2Decision = self.model2.evaluate_entry(
                game_id, home_rating, away_rating,
                kalshi_yes_price, sharp_line,
                mins_until_game, volume, spread,
                home_rest, away_rest
            )
            results["model_2"] = {
                "decision":   d2.decision,
                "reason":     d2.reason,
                "fails":      d2.fails,
                "fv":         d2.fv,
                "edge":       d2.edge,
                "direction":  d2.direction,
                "units":      d2.units,
                "contracts":  d2.contracts,
                "dollar_amt": d2.dollar_amt,
                "entry_price":d2.entry_price,
                "gate_log":   d2.gate_log,
            }
            if d2.decision == "ENTER":
                self._game_positions[game_id] = "model_2"
                logger.info(f"[MGR] Model 2 entered game={game_id}")

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: SETTLE A GAME
    # ─────────────────────────────────────────────────────────────────────────
    def settle(
        self,
        game_id:     str,
        home_won:    bool,
        sharp_close: float = 0.0,   # For M1 CLV calculation
    ) -> dict:
        """
        Settle all open positions for a game.
        Updates circuit breakers based on outcome.
        """
        model_id = self._game_positions.pop(game_id, None)
        results  = {"game_id": game_id, "home_won": home_won}

        if model_id == "model_1":
            rec = self.model1.settle(game_id, home_won, sharp_close)
            if rec:
                results["model_1"] = rec
                self._update_circuit_breaker("model_1", rec["outcome"] == "WIN")
                self._trades.append({"model": "model_1", **rec})

        elif model_id == "model_2":
            rec = self.model2.settle(game_id, home_won)
            if rec:
                results["model_2"] = rec
                self._update_circuit_breaker("model_2", rec["outcome"] == "WIN")
                self._trades.append({"model": "model_2", **rec})

        else:
            results["status"] = "NO_OPEN_POSITION"

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # CIRCUIT BREAKER
    # ─────────────────────────────────────────────────────────────────────────
    def _is_circuit_broken(self, model_id: str) -> bool:
        cb = self._cb[model_id]
        if cb["paused_until"] and datetime.utcnow() < cb["paused_until"]:
            return True
        if cb["paused_until"] and datetime.utcnow() >= cb["paused_until"]:
            cb["paused_until"] = None
            cb["consecutive_losses"] = 0
            logger.info(f"[CB] {model_id} circuit breaker reset — resuming")
        return False

    def _update_circuit_breaker(self, model_id: str, won: bool):
        cb = self._cb[model_id]
        if won:
            cb["consecutive_losses"] = 0
        else:
            cb["consecutive_losses"] += 1
            if cb["consecutive_losses"] >= cb["max_losses"]:
                pause = 600 if model_id == "model_1" else 900
                cb["paused_until"] = datetime.utcnow() + timedelta(seconds=pause)
                logger.warning(
                    f"[CB] {model_id} circuit breaker TRIGGERED — "
                    f"{cb['consecutive_losses']} consecutive losses — "
                    f"pausing {pause}s"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: STATUS & CONTROLS
    # ─────────────────────────────────────────────────────────────────────────
    def get_summary(self) -> dict:
        m1 = self.model1.get_status()
        m2 = self.model2.get_status()

        m1_trades = [t for t in self._trades if t["model"] == "model_1"]
        m2_trades = [t for t in self._trades if t["model"] == "model_2"]
        total_pnl = sum(t["pnl"] for t in self._trades)

        return {
            "session_start":   self._session_start.isoformat(),
            "kill_switch":     self._kill_switch,
            "total_trades":    len(self._trades),
            "total_pnl":       round(total_pnl, 4),
            "open_positions":  len(self._game_positions),
            "model_1": {
                **m1,
                "circuit_breaker": {
                    "consecutive_losses": self._cb["model_1"]["consecutive_losses"],
                    "paused": self._cb["model_1"]["paused_until"] is not None,
                    "paused_until": self._cb["model_1"]["paused_until"].isoformat()
                        if self._cb["model_1"]["paused_until"] else None,
                },
                "session_trades": len(m1_trades),
                "session_wins":   sum(1 for t in m1_trades if t["outcome"] == "WIN"),
            },
            "model_2": {
                **m2,
                "circuit_breaker": {
                    "consecutive_losses": self._cb["model_2"]["consecutive_losses"],
                    "paused": self._cb["model_2"]["paused_until"] is not None,
                    "paused_until": self._cb["model_2"]["paused_until"].isoformat()
                        if self._cb["model_2"]["paused_until"] else None,
                },
                "session_trades": len(m2_trades),
                "session_wins":   sum(1 for t in m2_trades if t["outcome"] == "WIN"),
            },
        }

    def kill(self):
        self._kill_switch = True
        logger.critical("[MGR] KILL SWITCH ACTIVATED — all models halted")

    def resume(self):
        self._kill_switch = False
        logger.info("[MGR] Kill switch cleared — models resuming")

    def reset_circuit_breaker(self, model_id: str):
        if model_id in self._cb:
            self._cb[model_id]["consecutive_losses"] = 0
            self._cb[model_id]["paused_until"] = None
            logger.info(f"[MGR] Circuit breaker manually reset for {model_id}")
