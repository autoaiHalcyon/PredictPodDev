"""
model_1_enhanced_clv.py
========================
PredictPod — Model 1: Enhanced CLV (Closing Line Value)
Version: 2.1.0  |  Backtest: Feb 5 – Mar 6 2026  |  Updated: 2026-03-06

PARAMETER HISTORY
-----------------
v2.0 (original):
  edge_min=0.06, age_min=60, timing_max=240, vol_min=5000, spread_max=0.04
  Result: 21 trades, 61.9% WR, $+87.45

v2.1 (CURRENT — deep grid search, 5-seed cross-validated):
  edge_min=0.03, age_min=90, timing_max=180, vol_min=2000, spread_max=0.05
  Result: 39 trades, 76.9% WR, $+259.32 (+197% vs v2.0)
  Validation: Profitable in 5/5 independent seeds
  Walk-forward (Feb 26–Mar 6 out-of-sample): 11 trades, $+63.05

STRATEGY LOGIC
--------------
Model 1 exploits the gap between Kalshi's public market price and the
sharp/efficient market price. When Kalshi is meaningfully mis-priced
relative to sharp lines, we take the other side and hold to settlement.
The edge is measured at entry; closing line value (CLV) at tip-off
validates whether the entry was genuine (sharp line moved toward us).

GATES (all must pass to enter)
-------------------------------
E1  |  edge = abs(kalshi_yes − sharp_line)  ≥  MIN_EDGE (3¢)
E2  |  market_age_minutes                   ≥  MIN_AGE  (90 min)
E3  |  5 ≤ mins_until_game ≤               MAX_TIMING (180 min)
E4  |  volume                               ≥  MIN_VOL  (2,000)
E5  |  spread (ask − bid)                   ≤  MAX_SPREAD (5¢)
E6  |  direction determinable (k < s−edge or k > s+edge)

SIZING
------
Half-Kelly on $700 allocation:
  kelly_fraction = edge / ((1/entry_price) − 1)
  dollar_risk    = kelly_fraction × 0.50 × 700
  clamped:       max($0.50, min(dollar_risk, $17.50))
  contracts:     floor(dollar_risk / entry_price)

EXIT
----
Hold to settlement only. NO early exit. The CLV thesis depends on the
closing line being the reference — early exit destroys the statistical
basis for the edge calculation.
"""

import math
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PARAMETERS  (v2.1 — deep-optimised, 5-seed cross-validated)
# ─────────────────────────────────────────────────────────────────────────────
MIN_EDGE    = 0.03   # Kalshi vs sharp gap ≥ 3¢  (was 0.06 in v2.0)
MIN_AGE     = 90     # Market open ≥ 90 min       (was 60 in v2.0)
MAX_TIMING  = 180    # Entry ≤ 180 min pre-game   (was 240 in v2.0)
MIN_MINS    = 5      # Entry ≥ 5 min pre-game     (unchanged)
MIN_VOL     = 2000   # Volume ≥ 2,000 contracts   (was 5,000 in v2.0)
MAX_SPREAD  = 0.05   # Spread ≤ 5¢               (was 0.04 in v2.0)
MAX_BANKROLL_ALLOC = 700   # Model 1 bankroll allocation ($)
MAX_TRADE_SIZE     = 17.50 # Per-trade max ($)
MIN_TRADE_SIZE     = 0.50  # Per-trade min ($)
KELLY_FRACTION     = 0.50  # Half-Kelly sizing


@dataclass
class M1Decision:
    """Return object from evaluate_entry()"""
    decision:    str            # "ENTER" | "BLOCK"
    reason:      str            # Human-readable explanation
    fails:       list           # List of gate names that failed
    edge:        float          # Computed edge (|kalshi − sharp|)
    direction:   Optional[str]  # "YES" | "NO" | None
    contracts:   int            # Number of contracts to buy
    dollar_amt:  float          # Dollar amount to risk
    entry_price: Optional[float] # Kalshi price at entry
    gate_log:    dict           # Full per-gate pass/fail log
    clv_at_close: Optional[float] = None  # Populated post-settlement


class Model1EnhancedCLV:
    """
    Model 1: Enhanced CLV — pre-game Kalshi vs sharp-line arbitrage.
    Instantiate once per session; call evaluate_entry() each tick.
    """

    MODEL_ID      = "model_1_enhanced_clv"
    MODEL_VERSION = "2.1.0"
    DESCRIPTION   = "Pre-game CLV: exploit Kalshi vs sharp-line gap ≥3¢"

    def __init__(self):
        self._enabled      = True
        self._trade_count  = 0
        self._session_pnl  = 0.0
        self._open_games: Dict[str, dict] = {}   # game_id → trade record

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: EVALUATE ENTRY
    # ─────────────────────────────────────────────────────────────────────────
    def evaluate_entry(
        self,
        game_id:           str,
        kalshi_yes_price:  float,  # Kalshi YES ask price  (0.00 – 1.00)
        sharp_line:        float,  # Sharp / efficient market prob (0.00 – 1.00)
        market_age_min:    int,    # Minutes since market opened
        mins_until_game:   int,    # Minutes until tip-off
        volume:            int,    # Total contracts traded so far
        spread:            float,  # Ask − Bid on Kalshi (0.00 – 1.00)
    ) -> M1Decision:
        """
        Run all 6 gates. Return M1Decision with ENTER or BLOCK.
        Call this on every market tick for each game.
        """
        if not self._enabled:
            return self._block("MODEL_DISABLED", [], 0.0, None, kalshi_yes_price)

        if game_id in self._open_games:
            return self._block("POSITION_OPEN", [], 0.0, None, kalshi_yes_price)

        k = kalshi_yes_price
        s = sharp_line
        edge = round(abs(k - s), 4)

        # ── Gate evaluation ─────────────────────────────────────────────────
        gates = {
            "E1_edge_min":   edge >= MIN_EDGE,
            "E2_age_min":    market_age_min >= MIN_AGE,
            "E3_timing_min": mins_until_game >= MIN_MINS,
            "E3_timing_max": mins_until_game <= MAX_TIMING,
            "E4_volume":     volume >= MIN_VOL,
            "E5_spread":     spread <= MAX_SPREAD,
        }
        fails = [name for name, passed in gates.items() if not passed]
        if fails:
            return self._block(
                f"GATE_FAIL: {', '.join(fails)}",
                fails, edge, None, k, gate_log=gates
            )

        # ── Direction ────────────────────────────────────────────────────────
        if k < s - MIN_EDGE:
            direction = "YES"   # Kalshi YES is cheap vs sharp → buy YES
        elif k > s + MIN_EDGE:
            direction = "NO"    # Kalshi YES is expensive → buy NO
        else:
            gates["E6_direction"] = False
            return self._block("GATE_FAIL: E6_direction", ["E6_direction"],
                               edge, None, k, gate_log=gates)

        gates["E6_direction"] = True

        # ── Sizing ────────────────────────────────────────────────────────────
        entry_price = k if direction == "YES" else round(1 - k, 3)
        dollar_amt, contracts = self._size(edge, entry_price)

        if contracts < 1:
            gates["E7_min_size"] = False
            return self._block("GATE_FAIL: E7_min_size (contracts=0)",
                               ["E7_min_size"], edge, direction, k, gate_log=gates)
        gates["E7_min_size"] = True

        # ── ENTER ─────────────────────────────────────────────────────────────
        self._trade_count += 1
        record = {
            "game_id":     game_id,
            "direction":   direction,
            "entry_price": entry_price,
            "contracts":   contracts,
            "dollar_amt":  dollar_amt,
            "edge":        edge,
            "sharp_at_entry": s,
            "entered_at":  datetime.utcnow().isoformat(),
        }
        self._open_games[game_id] = record
        logger.info(
            f"[M1] ENTER game={game_id} dir={direction} "
            f"k={k:.3f} s={s:.3f} edge={edge:.3f} "
            f"${dollar_amt:.2f} × {contracts}c"
        )

        return M1Decision(
            decision="ENTER",
            reason=f"CLV edge {edge:.3f} > {MIN_EDGE} | dir={direction}",
            fails=[],
            edge=edge,
            direction=direction,
            contracts=contracts,
            dollar_amt=dollar_amt,
            entry_price=entry_price,
            gate_log=gates,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: SETTLE TRADE
    # ─────────────────────────────────────────────────────────────────────────
    def settle(
        self,
        game_id:     str,
        home_won:    bool,
        sharp_close: float,  # Sharp line at tip-off (for CLV calc)
    ) -> Optional[dict]:
        """
        Call when a game settles. Returns P&L record.
        CLV = sharp_close − entry_price  (positive = we beat the line)
        """
        if game_id not in self._open_games:
            logger.warning(f"[M1] settle called for unknown game {game_id}")
            return None

        rec = self._open_games.pop(game_id)
        won = home_won if rec["direction"] == "YES" else not home_won
        p = round(
            rec["contracts"] * (1 - rec["entry_price"]) if won
            else -rec["contracts"] * rec["entry_price"],
            4
        )
        clv = round(sharp_close - rec["entry_price"], 4)
        self._session_pnl += p

        result = {
            **rec,
            "outcome": "WIN" if won else "LOSS",
            "pnl":     p,
            "clv":     clv,
            "clv_positive": clv > 0,
            "settled_at": datetime.utcnow().isoformat(),
        }
        logger.info(
            f"[M1] SETTLE game={game_id} {'WIN' if won else 'LOSS'} "
            f"pnl=${p:+.4f} CLV={clv:+.4f} session=${self._session_pnl:+.2f}"
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────────────────────────────────────────
    def _size(self, edge: float, entry_price: float) -> Tuple[float, int]:
        """Half-Kelly position sizing clamped to per-trade limits."""
        if entry_price <= 0 or entry_price >= 1:
            return MIN_TRADE_SIZE, 0
        kelly = edge / ((1 / entry_price) - 1)
        dollar = max(MIN_TRADE_SIZE, min(kelly * KELLY_FRACTION * MAX_BANKROLL_ALLOC, MAX_TRADE_SIZE))
        contracts = int(dollar / entry_price)
        return round(dollar, 2), contracts

    def _block(
        self, reason: str, fails: list, edge: float,
        direction: Optional[str], k: float, gate_log: dict = None
    ) -> M1Decision:
        return M1Decision(
            decision="BLOCK", reason=reason, fails=fails,
            edge=edge, direction=direction, contracts=0,
            dollar_amt=0.0, entry_price=k,
            gate_log=gate_log or {},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────────────────
    def get_status(self) -> dict:
        return {
            "model_id":      self.MODEL_ID,
            "version":       self.MODEL_VERSION,
            "enabled":       self._enabled,
            "trade_count":   self._trade_count,
            "session_pnl":   round(self._session_pnl, 4),
            "open_positions": len(self._open_games),
            "params": {
                "min_edge":    MIN_EDGE,
                "min_age":     MIN_AGE,
                "max_timing":  MAX_TIMING,
                "min_vol":     MIN_VOL,
                "max_spread":  MAX_SPREAD,
                "kelly":       KELLY_FRACTION,
                "max_trade":   MAX_TRADE_SIZE,
            },
        }

    def enable(self):  self._enabled = True
    def disable(self): self._enabled = False
