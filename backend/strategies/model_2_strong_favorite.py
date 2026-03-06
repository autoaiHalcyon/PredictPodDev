"""
Model 2: Strong Favorite Value
================================
Spec: PredictPod 2-Model Master Rules v2.0

Core concept: Heavy favorites are systematically underpriced.
"Favorite-longshot bias" — public loves underdogs, creating value on favorites.

Academic backing: Favorite-longshot bias documented in 50+ studies.

Capital allocation: $300 (30% of $1,000 total)
Expected ROI: 6% → ~$18/year
Hold to settlement — NO early exit.

Entry gates (ALL must pass):
    E1: fair_value >= 0.72 (strong favorite filter)
    E2: edge = fair_value - kalshi_yes_price >= 0.06
    E3: sharp_line >= 0.68 (sharp confirmation)
    E4: time_until_game <= 30 minutes (last 30 min only)
    E5: volume >= 5,000 [HARD]
    E6: spread <= 0.04 [HARD]
    E7: direction always YES (betting the favorite)

Fair value formula:
    rating_diff = home_rating - away_rating
    rest_adj    = (home_rest - away_rest) * 0.5
    total_adv   = rating_diff + 3.2 + rest_adj
    z           = total_adv * 0.028
    fair_value  = 1 / (1 + exp(-z)), clamped [0.10, 0.90]

Position sizing: Tiered
    edge >= 0.10  → 2.0 units ($6.00, capped at $7.50)
    edge >= 0.08  → 1.5 units ($4.50)
    edge >= 0.06  → 1.0 unit  ($3.00)
    unit_size = $3.00, max = 2.5% of $300 = $7.50
"""

import math
import logging
from datetime import datetime
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
MODEL_ID             = "model_2"
MODEL_ALLOCATION     = 300.0          # $300 of $1,000 total

FAIR_VALUE_MIN       = 0.72           # E1: must be ≥72% favorite
MIN_EDGE             = 0.06           # E2: 6¢ minimum underpricing
SHARP_LINE_MIN       = 0.68           # E3: sharp books must also see ≥68%
TIME_UNTIL_MAX_MINS  = 30             # E4: only last 30 min before game
VOLUME_MIN           = 5000           # E5: HARD GATE
SPREAD_MAX           = 0.04           # E6: HARD GATE — 4¢ max

HOME_COURT_ADVANTAGE = 3.2            # NBA home court ~3.2 points
REST_ADJ_PER_DAY     = 0.5            # 0.5 points per rest day difference
POINT_TO_PROB_COEFF  = 0.028          # Each point ≈ 2.8% win probability

UNIT_SIZE            = 3.0            # $3 per unit
MAX_POSITION_PCT     = 0.025          # 2.5% of $300 = $7.50 ceiling
FAIR_VALUE_CLAMP_LO  = 0.10
FAIR_VALUE_CLAMP_HI  = 0.90


class Model2StrongFavorite(BaseStrategy):
    """
    Model 2: Strong Favorite Value

    Scans pre-game Kalshi markets for underpriced heavy favorites.
    Uses logistic fair value formula combining team ratings, home court,
    and rest days.  Enters only in last 30 minutes before tip.
    Always bets YES.  Holds to settlement.
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        logger.info(
            f"[{MODEL_ID}] Initialized — allocation=${MODEL_ALLOCATION} "
            f"fv_min={FAIR_VALUE_MIN:.0%} edge_min={MIN_EDGE:.0%} "
            f"window=last {TIME_UNTIL_MAX_MINS}min"
        )

    # ── Fair Value Formula (exact spec) ───────────────────────────────────────

    @staticmethod
    def calculate_fair_value(
        home_rating: float,
        away_rating: float,
        home_rest_days: float = 1.0,
        away_rest_days: float = 1.0
    ) -> float:
        """
        Convert team ratings + rest to win probability.

        spec formula:
            rating_diff   = home_rating - away_rating
            rest_adj      = (home_rest - away_rest) * 0.5
            total_adv     = rating_diff + 3.2 (home court) + rest_adj
            z             = total_adv * 0.028
            probability   = 1 / (1 + exp(-z))
            fair_value    = clamp(probability, 0.10, 0.90)
        """
        rating_diff  = home_rating - away_rating
        rest_adj     = (home_rest_days - away_rest_days) * REST_ADJ_PER_DAY
        total_adv    = rating_diff + HOME_COURT_ADVANTAGE + rest_adj
        z            = total_adv * POINT_TO_PROB_COEFF
        probability  = 1.0 / (1.0 + math.exp(-z))
        return max(FAIR_VALUE_CLAMP_LO, min(FAIR_VALUE_CLAMP_HI, probability))

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
        """
        # Need team rating data
        home_rating   = getattr(game, "home_rating",   None)
        away_rating   = getattr(game, "away_rating",   None)
        home_rest     = getattr(game, "home_rest_days", 1.0)
        away_rest     = getattr(game, "away_rest_days", 1.0)

        if home_rating is None or away_rating is None:
            return self._block("No team ratings available — required for fair value")

        # ── E1: Strong Favorite Filter ────────────────────────────────────────
        fair_value = self.calculate_fair_value(home_rating, away_rating, home_rest, away_rest)
        if fair_value < FAIR_VALUE_MIN:
            return self._block(f"E1 fair_value {fair_value:.3f} < {FAIR_VALUE_MIN:.3f}")

        # ── E2: Market Mispricing ─────────────────────────────────────────────
        kalshi_price = market.yes_price
        edge = fair_value - kalshi_price
        if edge < MIN_EDGE:
            return self._block(f"E2 edge {edge:.3f} < {MIN_EDGE:.3f}")

        # ── E3: Sharp Line Confirmation ───────────────────────────────────────
        sharp_line = getattr(signal, "sharp_line", None) or getattr(signal, "fair_prob", None)
        if sharp_line is None:
            return self._block("E3 no sharp line for confirmation")
        if sharp_line < SHARP_LINE_MIN:
            return self._block(f"E3 sharp_line {sharp_line:.3f} < {SHARP_LINE_MIN:.3f}")

        # ── E4: Timing Gate — last 30 minutes only ────────────────────────────
        game_start = getattr(game, "scheduled_start", None) or getattr(game, "start_time", None)
        if game_start:
            mins_until = (game_start - datetime.utcnow()).total_seconds() / 60
            if mins_until > TIME_UNTIL_MAX_MINS:
                return self._block(
                    f"E4 {mins_until:.0f}m until game — window is last {TIME_UNTIL_MAX_MINS}m only"
                )
            if mins_until < 0:
                return self._block("E4 game already started")

        # ── E5: Volume Gate [HARD] ────────────────────────────────────────────
        volume = getattr(market, "volume_24h", None) or getattr(market, "volume", 0)
        if volume < VOLUME_MIN:
            return self._block(f"E5 volume {volume:,} < {VOLUME_MIN:,} [HARD]")

        # ── E6: Spread Gate [HARD] ────────────────────────────────────────────
        spread = market.spread if hasattr(market, "spread") and market.spread else (
            market.yes_ask - market.yes_bid if hasattr(market, "yes_ask") and hasattr(market, "yes_bid")
            else abs(market.yes_price - market.no_price)
        )
        if spread > SPREAD_MAX:
            return self._block(f"E6 spread {spread:.3f} > {SPREAD_MAX:.3f} [HARD]")

        # ── E7: Direction always YES ──────────────────────────────────────────
        direction = "YES"

        # ── All gates passed — tiered size ────────────────────────────────────
        contracts, dollar_amt, units = self._size(edge, kalshi_price)
        if contracts < 1:
            return self._block(f"Size rounds to 0 contracts (${dollar_amt:.2f})")

        logger.info(
            f"[{MODEL_ID}] ENTER {direction} | market={market.id} "
            f"fv={fair_value:.3f} sharp={sharp_line:.3f} kalshi={kalshi_price:.3f} "
            f"edge={edge:.3f} units={units} contracts={contracts} ${dollar_amt:.2f}"
        )

        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=(
                f"StrongFav fv={fair_value:.3f} sharp={sharp_line:.3f} "
                f"edge={edge:.3f} units={units}"
            ),
            market_id=market.id,
            game_id=game.id,
            side=direction,
            quantity=contracts,
            price=kalshi_price,
            edge=edge,
            signal_score=edge
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
        Model 2 exit rule: NONE — hold to settlement.

        "Favorites work best held to completion. No early exit."
        — Master Rules v2.0
        """
        return None  # Always hold

    # ── Size: Tiered ─────────────────────────────────────────────────────────

    def calculate_size(self, signal: Signal, available_capital: float) -> int:
        contracts, _, _ = self._size(signal.edge, signal.market_prob)
        return contracts

    def _size(self, edge: float, kalshi_price: float):
        """
        Tiered position sizing per spec.

        Returns (contracts, dollar_amount, units)

        Tiers:
            edge >= 0.10  → 2.0 units
            edge >= 0.08  → 1.5 units
            edge >= 0.06  → 1.0 unit
            unit_size = $3.00
            max = 2.5% of $300 = $7.50
        """
        if edge >= 0.10:
            units = 2.0
        elif edge >= 0.08:
            units = 1.5
        else:
            units = 1.0

        dollar_amt = units * UNIT_SIZE

        # Cap at 2.5% of model allocation
        max_position = MODEL_ALLOCATION * MAX_POSITION_PCT  # $7.50
        dollar_amt = min(dollar_amt, max_position)

        contracts = int(dollar_amt / kalshi_price) if kalshi_price > 0 else 0
        return contracts, dollar_amt, units

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _block(self, reason: str) -> None:
        logger.debug(f"[{MODEL_ID}] SKIP — {reason}")
        return None
