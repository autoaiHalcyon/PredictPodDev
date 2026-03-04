"""
Model: In-Game Edge Trader
==========================
Consolidated replacement for the redundant Model A (Disciplined),
Model B (High Frequency), and Model C (Institutional) strategies.

Those three models shared the same signal pipeline, same probability engine,
and same entry/exit logic — differing only in threshold numbers. Running them
in parallel produced correlated positions and inflated trade counts with no
real diversification benefit.

This single model takes the best-calibrated thresholds from all three:
- Edge threshold: 5¢ (Model A's disciplined level — B at 3¢ was too noisy)
- Signal score: 55 (between A's 60 and B's 45 — captures more setups without noise)
- Persistence: 3 ticks (A's level — B's 2 was too reactive)
- Cooldown: 120s (tighter than A's 180s, looser than B's 60s)
- Profit target: 15% (A's level)
- Stop loss: 8% (C's tighter level — A/B were too loose)
- Hard adverse move stop: 5% in 120s (from C's adverse_move_protection)
- Volatility filter: low + medium (A's level — B allowing "high" was reckless)
- Liquidity: 50 contracts min (A's level)

This model is a PLACEHOLDER until the Master Rules 5-model system is implemented.
It trades in-game only. The spec's pre-game models (B, D, E) do not exist yet.
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal, SignalType
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.virtual_portfolio import VirtualPosition

logger = logging.getLogger(__name__)


class InGameEdgeTrader(BaseStrategy):
    """
    Single consolidated in-game edge trading model.

    Entry: edge ≥5¢, signal score ≥55, 3-tick persistence, 120s cooldown,
           low/medium volatility, ≥50 contracts liquidity, game 10%-95% complete.

    Exit: stop loss 8%, profit target 15%, edge compressed <2¢,
          hard adverse move 5% in 120s, time limit 10 min.

    Sizing: half-Kelly based on edge, capped at 5% of capital per position.
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        # Track position entry prices for adverse-move hard stop
        self._entry_prices: Dict[str, float] = {}
        self._entry_timestamps: Dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # ENTRY
    # ------------------------------------------------------------------

    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None,
    ) -> Optional[StrategyDecision]:

        entry_rules = self.config.entry_rules

        # 1. Market / game filters
        passes, reason = self.check_filters(game, market, orderbook)
        if not passes:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Filter: {reason}",
                market_id=market.id,
                game_id=game.id,
            )

        # 2. Cooldown
        if not self.check_cooldown(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Cooldown active",
                market_id=market.id,
                game_id=game.id,
            )

        # 3. Max entries per game
        if not self.check_max_entries(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Max entries per game reached",
                market_id=market.id,
                game_id=game.id,
            )

        # 4. Edge threshold
        min_edge = entry_rules.get("min_edge_threshold", 0.05)
        if abs(signal.edge) < min_edge:
            return None  # Silent skip — not actionable

        # 5. Signal score
        min_score = entry_rules.get("min_signal_score", 55)
        signal_score = getattr(signal, "_signal_score", signal.confidence * 100)
        if signal_score < min_score:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Signal score {signal_score:.0f} < {min_score}",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score,
            )

        # 6. Edge persistence (3 ticks)
        min_ticks = entry_rules.get("min_persistence_ticks", 3)
        if not self.check_edge_persistence(market.id, min_ticks, min_edge):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Edge not persistent ({min_ticks} ticks required)",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score,
            )

        # 7. Volatility regime
        volatility_allowed = entry_rules.get("volatility_regime_allowed", ["low", "medium"])
        regime = getattr(signal, "_volatility_regime", "low")
        if hasattr(regime, "value"):
            regime = regime.value
        if regime not in volatility_allowed:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Volatility regime '{regime}' not allowed",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
            )

        # All checks passed — enter
        side = "yes" if signal.edge > 0 else "no"
        size = self.calculate_size(signal, self.portfolio.available_capital)

        if size <= 0:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Calculated size is 0",
                market_id=market.id,
                game_id=game.id,
            )

        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=f"Edge {signal.edge:.2%} | Score {signal_score:.0f} | {regime} vol",
            market_id=market.id,
            game_id=game.id,
            side=side,
            quantity=size,
            price=market.implied_probability,
            edge=signal.edge,
            signal_score=signal_score,
        )

    # ------------------------------------------------------------------
    # EXIT
    # ------------------------------------------------------------------

    def evaluate_exit(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        position: VirtualPosition,
        orderbook: Optional[Dict] = None,
    ) -> Optional[StrategyDecision]:

        exit_rules = self.config.exit_rules

        def make_exit(reason: str) -> StrategyDecision:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=reason,
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge,
            )

        # 1. Hard adverse-move stop (5% against entry within 120s)
        hard_stop_pct = exit_rules.get("hard_adverse_stop_pct", 0.05)
        hard_stop_window = exit_rules.get("hard_adverse_stop_seconds", 120)
        if (
            position.unrealized_pnl_pct <= -hard_stop_pct
            and position.hold_time_seconds <= hard_stop_window
        ):
            return make_exit(
                f"Hard adverse move stop: {position.unrealized_pnl_pct:.1%} "
                f"within {position.hold_time_seconds:.0f}s"
            )

        # 2. Standard stop loss (8%)
        stop_loss_pct = exit_rules.get("stop_loss_pct", 0.08)
        if position.unrealized_pnl_pct <= -stop_loss_pct:
            return make_exit(f"Stop loss: {position.unrealized_pnl_pct:.1%}")

        # 3. Profit target (15%)
        profit_target_pct = exit_rules.get("profit_target_pct", 0.15)
        if position.unrealized_pnl_pct >= profit_target_pct:
            return make_exit(f"Profit target: {position.unrealized_pnl_pct:.1%}")

        # 4. Edge compression (<2¢)
        exit_threshold = exit_rules.get("edge_compression_exit_threshold", 0.02)
        edge_flipped = (
            (position.side == "yes" and signal.edge < exit_threshold) or
            (position.side == "no" and signal.edge > -exit_threshold)
        )
        if edge_flipped:
            return make_exit(f"Edge compressed to {signal.edge:.2%}")

        # 5. Time-based exit (10 min)
        max_hold_seconds = exit_rules.get("time_based_exit_seconds", 600)
        if position.hold_time_seconds > max_hold_seconds:
            return make_exit(f"Max hold time {max_hold_seconds}s exceeded")

        return None

    # ------------------------------------------------------------------
    # SIZING — half-Kelly, capped at 5% of capital
    # ------------------------------------------------------------------

    def calculate_size(self, signal: Signal, available_capital: float) -> int:
        sizing = self.config.position_sizing

        # Kelly fraction of edge
        # Full Kelly = edge / (1 - entry_price), use half-Kelly
        entry_price = signal.market_prob if signal.market_prob > 0.05 else 0.50
        full_kelly = abs(signal.edge) / max(entry_price, 0.01)
        half_kelly_fraction = full_kelly * 0.5

        kelly_fraction = sizing.get("kelly_fraction", 0.5)
        amount = available_capital * half_kelly_fraction * kelly_fraction

        # Cap at max_position_pct of starting capital
        max_pct = sizing.get("max_position_pct", 0.05)
        max_amount = self.portfolio.starting_capital * max_pct
        final_amount = min(amount, max_amount)

        # Convert to contracts
        contracts = int(final_amount / max(entry_price, 0.01))
        return max(1, min(contracts, 100))
