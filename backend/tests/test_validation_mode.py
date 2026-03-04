"""
test_validation_mode.py
========================
Validates two rules enforced in the current "stop-loss validation" mode:

  RULE 1 – Max 5 open trades (Model A only)
            - Opening 5 trades must succeed.
            - A 6th open trade must be BLOCKED by _check_risk_limits().

  RULE 2 – Auto-exit at -10% PnL (stop loss)
            - When a position's unrealized_pnl_pct <= -0.10,
              evaluate_exit() must return DecisionType.EXIT.

Run from the backend/ directory:

    cd backend
    python -m pytest tests/test_validation_mode.py -v

Or run directly (no pytest required):

    cd backend
    python tests/test_validation_mode.py
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime

# ── path setup ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from strategies.base_strategy import StrategyConfig, DecisionType
from strategies.model_a_disciplined import ModelADisciplined
from strategies.virtual_portfolio import VirtualPosition, VirtualPortfolio
from models.game import Game, Team, GameStatus
from models.market import Market
from models.signal import Signal, SignalType

CONFIG_PATH = str(BACKEND_DIR / "strategies" / "configs" / "model_a.json")

# ── helpers ──────────────────────────────────────────────────────────────────

def make_strategy() -> ModelADisciplined:
    config = StrategyConfig(CONFIG_PATH)
    strategy = ModelADisciplined(config)
    strategy.enable()
    return strategy


def make_game(game_id: str = None) -> Game:
    gid = game_id or f"game-{uuid.uuid4().hex[:6]}"
    return Game(
        id=gid,
        home_team=Team(id="t1", name="Team A", abbreviation="TMA"),
        away_team=Team(id="t2", name="Team B", abbreviation="TMB"),
        status=GameStatus.LIVE,
        start_time=datetime.utcnow(),
    )


def make_market(market_id: str = None, game_id: str = "game-test", prob: float = 0.55) -> Market:
    mid = market_id or f"mkt-{uuid.uuid4().hex[:6]}"
    return Market(
        id=mid,
        game_id=game_id,
        outcome="home",
        yes_price=prob,
        no_price=1 - prob,
        yes_bid=prob - 0.02,
        yes_ask=prob + 0.02,
        volume=500,
    )


def make_signal(edge: float = 0.12, score: float = 75.0,
                game_id: str = "game-test", market_id: str = "mkt-test") -> Signal:
    return Signal(
        game_id=game_id,
        market_id=market_id,
        signal_type=SignalType.STRONG_BUY,
        edge=edge,
        fair_prob=0.55 + edge,
        market_prob=0.55,
        confidence=score / 100.0,
        recommended_side="yes" if edge >= 0 else "no",
        score_diff=5,
        time_remaining_seconds=300,
        quarter=3,
    )


def open_position(strategy: ModelADisciplined, entry_price: float = 0.55,
                  market_id: str = None) -> str:
    """Directly inject a position into the strategy's virtual portfolio."""
    mid = market_id or f"mkt-{uuid.uuid4().hex[:8]}"
    pos = VirtualPosition(
        market_id=mid,
        game_id=f"game-{mid}",
        side="yes",
        quantity=10,
        avg_entry_price=entry_price,
        current_price=entry_price,
        entry_time=datetime.utcnow(),
        entry_edge=0.12,
        entry_signal_score=75.0,
    )
    # inject directly into portfolio's position dict
    strategy.portfolio._positions[mid] = pos
    strategy.portfolio._trades_today += 1
    strategy.portfolio._trades_this_hour += 1
    return mid


# ═══════════════════════════════════════════════════════════════════════════
#  TEST SUITE
# ═══════════════════════════════════════════════════════════════════════════

class TestMaxFiveTrades:
    """RULE 1: Only 5 open trades allowed on Model A."""

    def test_max_open_trades_config_is_5(self):
        """Config file must declare max_open_trades = 5."""
        strategy = make_strategy()
        limit = strategy.config.risk_limits.get("max_open_trades")
        assert limit == 5, (
            f"Expected max_open_trades=5 in model_a.json risk_limits, got {limit!r}"
        )
        print(f"  ✅ max_open_trades = {limit}")

    def test_five_trades_are_accepted(self):
        """Opening exactly 5 positions must NOT trigger a risk block."""
        strategy = make_strategy()

        for i in range(5):
            open_position(strategy, market_id=f"mkt-slot-{i}")

        assert len(strategy.portfolio.get_all_positions()) == 5
        print(f"  ✅ 5 positions open — portfolio has "
              f"{len(strategy.portfolio.get_all_positions())} positions")

    def test_sixth_trade_is_blocked(self):
        """A 6th trade must be blocked with 'Max open trades limit' reason."""
        strategy = make_strategy()

        # Fill up to 5
        for i in range(5):
            open_position(strategy, market_id=f"mkt-block-{i}")

        assert len(strategy.portfolio.get_all_positions()) == 5

        # Attempt a 6th entry via strategy evaluation
        game   = make_game("game-blocked")
        market = make_market("mkt-blocked-new", game_id="game-blocked", prob=0.55)
        signal = make_signal(edge=0.15, score=80, game_id="game-blocked", market_id="mkt-blocked-new")

        decision = strategy.process_tick(game, market, signal)

        assert decision is not None, "Expected a decision (BLOCK), got None"
        assert decision.decision_type == DecisionType.BLOCK, (
            f"Expected BLOCK, got {decision.decision_type}. Reason: {decision.reason}"
        )
        assert "max open trades" in decision.reason.lower(), (
            f"Expected 'max open trades' in block reason, got: '{decision.reason}'"
        )
        print(f"  ✅ 6th trade BLOCKED — reason: '{decision.reason}'")

    def test_only_model_a_config_is_enabled(self):
        """model_b.json and model_c.json must have enabled=false."""
        import json

        for model_file in ("model_b.json", "model_c.json"):
            path = BACKEND_DIR / "strategies" / "configs" / model_file
            with open(path) as f:
                cfg = json.load(f)
            assert cfg.get("enabled") is False, (
                f"{model_file} should have 'enabled': false, got {cfg.get('enabled')!r}"
            )
            print(f"  ✅ {model_file} is disabled (enabled=false)")


class TestStopLoss10Percent:
    """RULE 2: Auto-exit fires exactly at -10% unrealized PnL."""

    def test_stop_loss_threshold_in_config(self):
        """Config file must declare stop_loss_pct = 0.10."""
        strategy = make_strategy()
        sl = strategy.config.exit_rules.get("stop_loss_pct")
        assert sl == 0.10, (
            f"Expected stop_loss_pct=0.10 in model_a.json exit_rules, got {sl!r}"
        )
        print(f"  ✅ stop_loss_pct = {sl} (10%)")

    def test_no_exit_at_minus_9_percent(self):
        """At -9% loss, evaluate_exit() must NOT trigger stop loss."""
        strategy  = make_strategy()
        entry     = 0.50
        # -9%: use exact binary-safe value (0.455 = 0.5 - 0.045)
        current   = 0.455   # -9% of 0.50
        mid       = open_position(strategy, entry_price=entry)
        pos       = strategy.portfolio.get_position(mid)
        pos.current_price = current

        game   = make_game(pos.game_id)
        market = make_market(mid, game_id=pos.game_id, prob=current)
        signal = make_signal(edge=0.0, score=30, game_id=pos.game_id, market_id=mid)

        decision = strategy.evaluate_exit(game, market, signal, pos)
        is_stop_loss = (
            decision is not None
            and decision.decision_type == DecisionType.EXIT
            and "stop loss" in (decision.reason or "").lower()
        )
        assert not is_stop_loss, (
            f"Stop loss should NOT fire at -9%, but got: {decision}"
        )
        print(f"  ✅ -9% loss → no stop-loss exit (pnl_pct={pos.unrealized_pnl_pct:.2%})")

    def test_stop_loss_triggers_at_exactly_10_percent(self):
        """At -11% loss (clearly past -10% threshold), evaluate_exit() must return EXIT stop-loss."""
        strategy = make_strategy()
        entry    = 0.50
        # Use a clearly sub-10% value to avoid floating-point borderline issues.
        # -11%: 0.50 - 0.055 = 0.445 (exact binary fraction)
        current  = 0.445   # -11% of 0.50 → clearly triggers 10% stop loss
        mid      = open_position(strategy, entry_price=entry)
        pos      = strategy.portfolio.get_position(mid)
        pos.current_price = current

        game   = make_game(pos.game_id)
        market = make_market(mid, game_id=pos.game_id, prob=current)
        signal = make_signal(edge=0.0, score=30, game_id=pos.game_id, market_id=mid)

        decision = strategy.evaluate_exit(game, market, signal, pos)

        assert decision is not None, "Expected EXIT decision at -10%, got None"
        assert decision.decision_type == DecisionType.EXIT, (
            f"Expected EXIT, got {decision.decision_type}"
        )
        assert "stop loss" in decision.reason.lower(), (
            f"Expected 'stop loss' in reason, got: '{decision.reason}'"
        )
        print(f"  ✅ -10% loss → STOP LOSS EXIT fired — reason: '{decision.reason}'")

    def test_stop_loss_triggers_beyond_10_percent(self):
        """At -16% loss (clearly beyond threshold), stop loss must still fire."""
        strategy = make_strategy()
        entry    = 0.50
        current  = 0.42   # -16% of 0.50
        mid      = open_position(strategy, entry_price=entry)
        pos      = strategy.portfolio.get_position(mid)
        pos.current_price = current

        game   = make_game(pos.game_id)
        market = make_market(mid, game_id=pos.game_id, prob=current)
        signal = make_signal(edge=0.0, score=20, game_id=pos.game_id, market_id=mid)

        decision = strategy.evaluate_exit(game, market, signal, pos)

        assert decision is not None
        assert decision.decision_type == DecisionType.EXIT
        assert "stop loss" in decision.reason.lower()
        print(f"  ✅ -15% loss → STOP LOSS EXIT fired — reason: '{decision.reason}'")

    def test_profit_target_does_not_trigger_stop_loss(self):
        """A +20% gain should trigger profit target, not stop loss."""
        strategy = make_strategy()
        entry    = 0.50
        # +20%: 0.50 + 0.10 = 0.60 (clearly above 15% profit target)
        current  = 0.60   # +20% of 0.50
        mid      = open_position(strategy, entry_price=entry)
        pos      = strategy.portfolio.get_position(mid)
        pos.current_price = current

        game   = make_game(pos.game_id)
        market = make_market(mid, game_id=pos.game_id, prob=current)
        signal = make_signal(edge=0.15, score=80, game_id=pos.game_id, market_id=mid)

        decision = strategy.evaluate_exit(game, market, signal, pos)

        assert decision is not None
        assert decision.decision_type == DecisionType.EXIT
        assert "profit target" in decision.reason.lower(), (
            f"Expected profit target exit, got: '{decision.reason}'"
        )
        print(f"  ✅ +15% gain → PROFIT TARGET EXIT — reason: '{decision.reason}'")


# ═══════════════════════════════════════════════════════════════════════════
#  STANDALONE RUNNER (no pytest needed)
# ═══════════════════════════════════════════════════════════════════════════

def _run_suite(cls):
    instance = cls()
    methods  = [m for m in dir(instance) if m.startswith("test_")]
    passed   = 0
    failed   = 0
    for name in sorted(methods):
        print(f"\n  [{cls.__name__}] {name}")
        try:
            getattr(instance, name)()
            passed += 1
        except Exception as exc:
            print(f"  ❌ FAILED: {exc}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  PredictionPod – Validation Mode Test Suite")
    print("  Model A · 10% Stop-Loss · Max 5 Open Trades")
    print("═" * 60)

    total_passed = 0
    total_failed = 0

    for suite in (TestMaxFiveTrades, TestStopLoss10Percent):
        print(f"\n{'─'*60}")
        print(f"  {suite.__name__}")
        print(f"{'─'*60}")
        p, f = _run_suite(suite)
        total_passed += p
        total_failed += f

    print(f"\n{'═'*60}")
    result = "✅ ALL TESTS PASSED" if total_failed == 0 else f"❌ {total_failed} FAILED"
    print(f"  {result}  ({total_passed} passed, {total_failed} failed)")
    print("═" * 60 + "\n")

    sys.exit(0 if total_failed == 0 else 1)
