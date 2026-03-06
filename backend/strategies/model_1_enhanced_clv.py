"""
Model 1: Enhanced CLV (Closing Line Value)
==========================================
Spec: PredictPod 2-Model Master Rules v2.0

Core concept: Beat the closing line = long-term profit.
If you consistently get better prices than the closing line, you have an edge.

Academic backing: 20+ papers since 1990s (Dixon & Coles, Buchdahl, etc.)

Capital allocation: $700 (70% of $1,000 total)
Expected ROI: 4% → ~$28/year
Hold to settlement — NO early exit.

Entry gates (ALL must pass):
    E1: edge >= 0.06 (6¢ minimum)
    E2: market_age >= 60 minutes
    E3: 5 min < time_until_game < 4 hours
    E4: volume >= 5,000 contracts [HARD]
    E5: spread <= 0.04 (4¢) [HARD]

Plus Global Safety Gates G1-G6.

Exit: Hold to settlement only.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

from strategies.base_strategy import (
    BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
)
from models.game import Game
from models.market import Market
from models.signal import Signal
from strategies.virtual_portfolio import VirtualPosition

logger = logging.getLogger(__name__)

# ── Spec constants ────────────────────────────────────────────────────────────
MODEL_ID             = "model_1"
MODEL_ALLOCATION     = 700.0          # $700 of $1,000 total

MIN_EDGE             = 0.06           # E1: 6¢ minimum edge
MARKET_AGE_MIN_MINS  = 60            # E2: market must be open ≥60 min
TIME_UNTIL_MIN_MINS  = 5             # E3: no entry <5 min before game
TIME_UNTIL_MAX_HOURS = 4             # E3: no entry >4 hr before game
VOLUME_MIN           = 5000          # E4: HARD GATE
SPREAD_MAX           = 0.04          # E5: HARD GATE — 4¢ max

MIN_POSITION         = 0.50          # $0.50 floor
MAX_POSITION_PCT     = 0.025         # 2.5% of $700 = $17.50 ceiling


class Model1EnhancedCLV(BaseStrategy):
    """
    Model 1: Enhanced CLV

    Scans pre-game Kalshi markets for price gaps vs. sharp closing lines.
    Enters when edge ≥ 6¢ and all gates pass.
    Holds to settlement — CLV only works if you don't exit early.
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        logger.info(
            f"[{MODEL_ID}] Initialized — allocation=${MODEL_ALLOCATION} "
            f"min_edge={MIN_EDGE:.0%} timing={TIME_UNTIL_MIN_MINS}m-{TIME_UNTIL_MAX_HOURS}h"
        )

    # ── Entry ─────────────────────────────────────────────────────────────────

    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """
        Evaluate all entry gates exactly as specified.
        Returns ENTER decision or None (with debug log of which gate failed).
        """
        # Need sharp line data — stored in signal.fair_prob when scheduler
        # has fetched it from The Odds API.
        sharp_line = getattr(signal, "sharp_line", None) or getattr(signal, "fair_prob", None)
        if sharp_line is None:
            return self._block("No sharp line available")

        kalshi_price = market.yes_price

        # ── E1: Minimum Edge ─────────────────────────────────────────────────
        edge = abs(kalshi_price - sharp_line)
        if edge < MIN_EDGE:
            return self._block(f"E1 edge {edge:.3f} < {MIN_EDGE:.3f}")

        # ── E2: Market Maturity ───────────────────────────────────────────────
        market_opened_at = getattr(market, "opened_at", None)
        if market_opened_at:
            age_mins = (datetime.utcnow() - market_opened_at).total_seconds() / 60
            if age_mins < MARKET_AGE_MIN_MINS:
                return self._block(f"E2 market age {age_mins:.0f}m < {MARKET_AGE_MIN_MINS}m")

        # ── E3: Timing Gate ───────────────────────────────────────────────────
        game_start = getattr(game, "scheduled_start", None) or getattr(game, "start_time", None)
        if game_start:
            mins_until = (game_start - datetime.utcnow()).total_seconds() / 60
            if mins_until < TIME_UNTIL_MIN_MINS:
                return self._block(f"E3 only {mins_until:.0f}m until game (<{TIME_UNTIL_MIN_MINS}m)")
            if mins_until > TIME_UNTIL_MAX_HOURS * 60:
                return self._block(f"E3 {mins_until/60:.1f}h until game (>{TIME_UNTIL_MAX_HOURS}h)")
        else:
            # If no game start time, only safe to trade in-window if game is live
            if game.status not in ("scheduled", "pre_game"):
                pass  # Live game — timing gate N/A for pre-game windows

        # ── E4: Volume Gate [HARD] ────────────────────────────────────────────
        volume = getattr(market, "volume_24h", None) or getattr(market, "volume", 0)
        if volume < VOLUME_MIN:
            return self._block(f"E4 volume {volume:,} < {VOLUME_MIN:,} [HARD]")

        # ── E5: Spread Gate [HARD] ────────────────────────────────────────────
        spread = market.spread if hasattr(market, "spread") and market.spread else (
            market.yes_ask - market.yes_bid if hasattr(market, "yes_ask") and hasattr(market, "yes_bid")
            else abs(market.yes_price - market.no_price)
        )
        if spread > SPREAD_MAX:
            return self._block(f"E5 spread {spread:.3f} > {SPREAD_MAX:.3f} [HARD]")

        # ── E6: Direction ─────────────────────────────────────────────────────
        if kalshi_price < sharp_line - MIN_EDGE:
            direction = "YES"   # Kalshi underpriced vs sharp line
        elif kalshi_price > sharp_line + MIN_EDGE:
            direction = "NO"    # Kalshi overpriced vs sharp line
        else:
            return self._block(f"E6 edge {edge:.3f} insufficient for clear direction")

        # ── All gates passed — calculate size ─────────────────────────────────
        contracts, dollar_amt, kelly_frac = self._size(edge, kalshi_price)
        if contracts < 1:
            return self._block(f"Size rounds to 0 contracts (${dollar_amt:.2f})")

        logger.info(
            f"[{MODEL_ID}] ENTER {direction} | market={market.id} "
            f"kalshi={kalshi_price:.3f} sharp={sharp_line:.3f} "
            f"edge={edge:.3f} contracts={contracts} ${dollar_amt:.2f} kelly={kelly_frac:.3f}"
        )

        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=(
                f"CLV edge={edge:.3f} sharp={sharp_line:.3f} "
                f"kalshi={kalshi_price:.3f} kelly={kelly_frac:.3f}"
            ),
            market_id=market.id,
            game_id=game.id,
            side=direction,
            quantity=contracts,
            price=kalshi_price,
            edge=edge,
            signal_score=edge  # CLV model uses edge directly
        )

    # ── Exit: HOLD TO SETTLEMENT ONLY ─────────────────────────────────────────

    def evaluate_exit(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        position: VirtualPosition,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """
        Model 1 exit rule: NONE — hold to settlement.

        "CLV models do NOT exit early. Closing line is the benchmark.
        Exiting early destroys the CLV edge."
        — Master Rules v2.0
        """
        return None  # Always hold

    # ── Size: Half-Kelly ──────────────────────────────────────────────────────

    def calculate_size(self, signal: Signal, available_capital: float) -> int:
        contracts, _, _ = self._size(signal.edge, signal.market_prob)
        return contracts

    def _size(self, edge: float, kalshi_price: float):
        """
        Half-Kelly position sizing per spec.

        Returns (contracts, dollar_amount, kelly_fraction)
        """
        # Avoid division by zero
        if kalshi_price <= 0 or kalshi_price >= 1:
            return 0, 0.0, 0.0

        decimal_odds = 1.0 / kalshi_price
        kelly_fraction = edge / (decimal_odds - 1.0)
        half_kelly = kelly_fraction * 0.5

        dollar_amt = half_kelly * MODEL_ALLOCATION

        # Apply limits per spec
        max_position = MODEL_ALLOCATION * MAX_POSITION_PCT  # $17.50
        dollar_amt = max(MIN_POSITION, min(dollar_amt, max_position))

        contracts = int(dollar_amt / kalshi_price)
        return contracts, dollar_amt, half_kelly

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _block(self, reason: str) -> None:
        logger.debug(f"[{MODEL_ID}] SKIP — {reason}")
        return None
