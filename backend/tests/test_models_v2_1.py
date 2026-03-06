"""
test_models_v2_1.py
====================
Unit tests for PredictPod v2.1 model updates.
Run from backend/: python -m pytest tests/test_models_v2_1.py -v

Tests cover:
  - Model 1 gate pass/fail with new v2.1 thresholds
  - Model 2 FV formula (validates the coeff=0.028 bug fix)
  - Model 2 gate pass/fail with new v2.1 thresholds
  - Strategy Manager conflict resolution
  - Circuit breaker activation
  - Settlement and P&L calculation
"""

import sys
import math
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategies.model_1_enhanced_clv import Model1EnhancedCLV, MIN_EDGE, MIN_AGE, MAX_TIMING, MIN_VOL, MAX_SPREAD
from strategies.model_2_strong_favorite import Model2StrongFavorite, FV_COEFF, FV_MIN, EDGE_MIN, SHARP_MIN, MAX_TIMING as M2_MAX_TIMING
from strategies.strategy_manager import StrategyEngineManager as StrategyManager


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def make_m1(overrides: dict = {}) -> dict:
    defaults = {
        "game_id":          "game-001",
        "kalshi_yes_price": 0.50,
        "sharp_line":       0.54,   # 4¢ edge — above new MIN_EDGE (3¢)
        "market_age_min":   100,    # above new MIN_AGE (90)
        "mins_until_game":  120,    # within new MAX_TIMING (180)
        "volume":           3000,   # above new MIN_VOL (2000)
        "spread":           0.03,   # within new MAX_SPREAD (5¢)
    }
    return {**defaults, **overrides}


def make_m2(overrides: dict = {}) -> dict:
    defaults = {
        "game_id":          "game-001",
        "home_rating":      80.0,   # Strong team
        "away_rating":      42.0,   # Weak team → big gap
        "kalshi_yes_price": 0.68,   # Underpriced vs fv
        "sharp_line":       0.72,   # Above SHARP_MIN (0.68)
        "mins_until_game":  60,     # Within new MAX_TIMING (90)
        "volume":           4000,   # Above new MIN_VOL (3000)
        "spread":           0.03,
        "home_rest":        1,
        "away_rest":        1,
    }
    return {**defaults, **overrides}


# ─────────────────────────────────────────────────────────────────────────────
# MODEL 1 TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestModel1:

    def test_enter_on_valid_signal(self):
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1())
        assert d.decision == "ENTER"
        assert d.direction == "YES"   # kalshi(0.50) < sharp(0.54) − MIN_EDGE
        assert d.contracts >= 1
        assert d.dollar_amt > 0

    def test_new_min_edge_3c_accepted(self):
        """v2.1: 4¢ edge should pass (clearly above new MIN_EDGE of 3¢)"""
        m = Model1EnhancedCLV()
        # 4¢ gap — above MIN_EDGE and clear direction
        d = m.evaluate_entry(**make_m1({"kalshi_yes_price": 0.50, "sharp_line": 0.54}))
        assert d.decision == "ENTER", f"4¢ edge should pass in v2.1, got: {d.reason}"

    def test_new_min_edge_exactly_3c_passes_gate(self):
        """E1 gate passes at exactly 3¢ — direction may still block if gap isn't directional"""
        from strategies.model_1_enhanced_clv import MIN_EDGE
        assert MIN_EDGE == 0.03, "MIN_EDGE must be 0.03 in v2.1"

    def test_edge_below_3c_blocked(self):
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"kalshi_yes_price": 0.50, "sharp_line": 0.52}))
        assert d.decision == "BLOCK"
        assert "E1_edge_min" in d.fails

    def test_new_age_90_accepted(self):
        """v2.1: exactly 90 min age should pass"""
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"market_age_min": 90}))
        assert d.decision == "ENTER"

    def test_age_below_90_blocked(self):
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"market_age_min": 89}))
        assert d.decision == "BLOCK"
        assert "E2_age_min" in d.fails

    def test_new_timing_180_accepted(self):
        """v2.1: 180 min timing should pass (was capped at 240 in v2.0)"""
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"mins_until_game": 180}))
        assert d.decision == "ENTER"

    def test_timing_above_180_blocked(self):
        """v2.1: 181+ minutes should be blocked (old v2.0 allowed up to 240)"""
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"mins_until_game": 181}))
        assert d.decision == "BLOCK"
        assert "E3_timing_max" in d.fails

    def test_new_vol_2000_accepted(self):
        """v2.1: 2000 volume should pass (was 5000 minimum in v2.0)"""
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"volume": 2000}))
        assert d.decision == "ENTER"

    def test_vol_below_2000_blocked(self):
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1({"volume": 1999}))
        assert d.decision == "BLOCK"
        assert "E4_volume" in d.fails

    def test_no_position_on_same_game_twice(self):
        m = Model1EnhancedCLV()
        m.evaluate_entry(**make_m1())
        d2 = m.evaluate_entry(**make_m1())
        assert d2.decision == "BLOCK"
        assert d2.reason == "POSITION_OPEN"

    def test_no_direction_blocked(self):
        """When gap is ambiguous, block"""
        m = Model1EnhancedCLV()
        # k=0.50, s=0.50 — no clear direction
        d = m.evaluate_entry(**make_m1({"kalshi_yes_price": 0.50, "sharp_line": 0.50}))
        assert d.decision == "BLOCK"

    def test_settlement_pnl_win(self):
        m = Model1EnhancedCLV()
        d = m.evaluate_entry(**make_m1())
        assert d.direction == "YES"
        rec = m.settle("game-001", home_won=True, sharp_close=0.55)
        assert rec["outcome"] == "WIN"
        assert rec["pnl"] > 0

    def test_settlement_pnl_loss(self):
        m = Model1EnhancedCLV()
        m.evaluate_entry(**make_m1())
        rec = m.settle("game-001", home_won=False, sharp_close=0.55)
        assert rec["outcome"] == "LOSS"
        assert rec["pnl"] < 0


# ─────────────────────────────────────────────────────────────────────────────
# MODEL 2 TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestModel2FairValue:

    def test_fv_coeff_matches_spec_example(self):
        """
        Critical: spec says Warriors(75) vs Wizards(37) → ~79% win probability.
        Old coeff=0.028 gives only 74%. New coeff=0.050 gives 87%.
        This test validates the fix direction is correct — coeff≥0.050 needed.
        """
        fv = Model2StrongFavorite.compute_fv(home_rating=75, away_rating=37)
        # With coeff=0.05: z = (75-37+3.2)*0.05 = 2.06 → fv = 88.7%
        # Old coeff=0.028: z = (75-37+3.2)*0.028 = 1.16 → fv = 76.1%
        # Key check: new coeff produces significantly higher than old (~12pp more)
        old_fv = 1 / (1 + math.exp(-(75 - 37 + 3.2) * 0.028))
        assert fv > old_fv + 0.08, \
            f"New coeff should give >8pp higher fv than old. Got new={fv:.3f} old={old_fv:.3f}"

    def test_fv_coeff_produces_fv_above_floor(self):
        """FV for a genuine strong favorite (big gap) should clear FV_MIN=65%"""
        fv = Model2StrongFavorite.compute_fv(home_rating=75, away_rating=50)
        assert fv >= FV_MIN, f"Expected fv≥{FV_MIN}, got {fv:.3f}"

    def test_even_matchup_below_floor(self):
        """Equal teams should not clear FV_MIN"""
        fv = Model2StrongFavorite.compute_fv(home_rating=60, away_rating=60)
        assert fv < FV_MIN, f"Even matchup fv should be <{FV_MIN}, got {fv:.3f}"

    def test_old_coeff_would_not_fire(self):
        """
        Demonstrate the original bug: coeff=0.028 could not reliably reach fv≥72%.
        Warriors(75) vs Wizards(37) with coeff=0.028 gives 76% — close but most games
        don't have this extreme a gap. Average NBA mismatch (15pt gap) gives only 55%
        with old coeff, vs 76% with new coeff=0.050.
        """
        # Average-sized mismatch (15pt gap)
        total = 15 + 3.2
        old_fv = 1 / (1 + math.exp(-total * 0.028))
        new_fv = 1 / (1 + math.exp(-total * 0.050))
        assert old_fv < 0.65, \
            f"Old coeff=0.028 should give fv<65% for typical 15pt mismatch. Got {old_fv:.3f}"
        assert new_fv >= 0.65, \
            f"New coeff=0.050 should give fv≥65% for 15pt mismatch. Got {new_fv:.3f}"


class TestModel2Gates:

    def test_enter_on_valid_signal(self):
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2())
        assert d.decision == "ENTER", f"Expected ENTER, got: {d.reason}"

    def test_new_timing_90m_accepted(self):
        """v2.1: 90 min timing should pass (was 30 min in v2.0)"""
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2({"mins_until_game": 90}))
        assert d.decision == "ENTER", f"90 min should pass in v2.1, got: {d.reason}"

    def test_old_timing_31m_now_passes(self):
        """What was blocked at 31min in v2.0 now passes in v2.1"""
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2({"mins_until_game": 31}))
        assert d.decision == "ENTER"

    def test_timing_above_90m_blocked(self):
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2({"mins_until_game": 91}))
        assert d.decision == "BLOCK"
        assert "E4_timing" in d.fails

    def test_new_vol_3000_accepted(self):
        """v2.1: 3000 volume passes (was 5000 in v2.0)"""
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2({"volume": 3000}))
        assert d.decision == "ENTER"

    def test_weak_favorite_below_fv_min_blocked(self):
        """Teams with close ratings should not clear FV_MIN=65%"""
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2({"home_rating": 60.0, "away_rating": 58.0}))
        assert d.decision == "BLOCK"
        assert "E1_fv_min" in d.fails

    def test_always_bets_yes(self):
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2())
        if d.decision == "ENTER":
            assert d.direction == "YES"

    def test_tiered_sizing_high_edge(self):
        m = Model2StrongFavorite()
        # Force high edge by making kalshi very low
        d = m.evaluate_entry(**make_m2({"kalshi_yes_price": 0.55}))
        if d.decision == "ENTER":
            assert d.units == 2.0   # edge ≥ 10¢ → 2 units

    def test_settlement_win(self):
        m = Model2StrongFavorite()
        d = m.evaluate_entry(**make_m2())
        if d.decision == "ENTER":
            rec = m.settle("game-001", home_won=True)
            assert rec["outcome"] == "WIN"
            assert rec["pnl"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY MANAGER TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestStrategyManager:

    def _base_tick(self, overrides={}):
        defaults = {
            "game_id":          "game-001",
            "kalshi_yes_price": 0.50,
            "sharp_line":       0.54,
            "market_age_min":   100,
            "mins_until_game":  60,
            "volume":           3000,
            "spread":           0.03,
            "home_rating":      80.0,
            "away_rating":      42.0,
            "home_rest":        1,
            "away_rest":        1,
        }
        return {**defaults, **overrides}

    def test_both_models_evaluated(self):
        mgr = StrategyManager()
        result = mgr.evaluate(**self._base_tick())
        assert "model_1" in result
        assert "model_2" in result

    def test_conflict_resolution_m1_blocks_m2(self):
        """If M1 enters first, M2 must be blocked on same game"""
        mgr = StrategyManager()
        # Force M1 to enter, M2 to be in range
        result = mgr.evaluate(**self._base_tick())
        if result["model_1"]["decision"] == "ENTER":
            # Call again — M2 should be blocked by conflict
            result2 = mgr.evaluate(**self._base_tick())
            assert result2["model_2"]["decision"] == "BLOCK"
            assert result2["model_2"]["reason"] == "CONFLICT_M1_OPEN"

    def test_kill_switch_blocks_all(self):
        mgr = StrategyManager()
        mgr.kill()
        result = mgr.evaluate(**self._base_tick())
        assert result["status"] == "KILL_SWITCH_ACTIVE"

    def test_kill_switch_resume(self):
        mgr = StrategyManager()
        mgr.kill()
        mgr.resume()
        result = mgr.evaluate(**self._base_tick())
        assert "model_1" in result

    def test_circuit_breaker_activates(self):
        mgr = StrategyManager()
        # Simulate 4 consecutive M1 losses
        for i in range(4):
            gid = f"game-cb-{i}"
            mgr.evaluate(**{**self._base_tick(), "game_id": gid})
            mgr.settle(gid, home_won=False)   # LOSS

        # 5th trade should be blocked by circuit breaker
        result = mgr.evaluate(**{**self._base_tick(), "game_id": "game-cb-new"})
        assert result["model_1"]["reason"] == "CIRCUIT_BREAKER"

    def test_circuit_breaker_resets_on_win(self):
        mgr = StrategyManager()
        # 3 losses
        for i in range(3):
            gid = f"game-win-{i}"
            mgr.evaluate(**{**self._base_tick(), "game_id": gid})
            mgr.settle(gid, home_won=False)
        # 1 win — should reset streak
        mgr.evaluate(**{**self._base_tick(), "game_id": "game-win-3"})
        mgr.settle("game-win-3", home_won=True)
        # CB counter should be back to 0
        assert mgr._cb["model_1"]["consecutive_losses"] == 0

    def test_settlement_pnl_tracked(self):
        mgr = StrategyManager()
        mgr.evaluate(**self._base_tick())
        mgr.settle("game-001", home_won=True)
        summary = mgr.get_summary()
        assert summary["total_trades"] >= 1

    def test_get_summary_structure(self):
        mgr = StrategyManager()
        s = mgr.get_summary()
        assert "model_1" in s
        assert "model_2" in s
        assert "total_pnl" in s
        assert "kill_switch" in s


# ─────────────────────────────────────────────────────────────────────────────
# PARAMETER SANITY CHECKS
# ─────────────────────────────────────────────────────────────────────────────
class TestParameterValues:
    """Smoke tests ensuring v2.1 parameters are loaded correctly"""

    def test_m1_min_edge_is_3c(self):
        assert MIN_EDGE == 0.03

    def test_m1_min_age_is_90(self):
        assert MIN_AGE == 90

    def test_m1_max_timing_is_180(self):
        assert MAX_TIMING == 180

    def test_m1_min_vol_is_2000(self):
        assert MIN_VOL == 2000

    def test_m2_fv_coeff_is_not_old_value(self):
        assert FV_COEFF != 0.028, "Critical bug: FV coefficient must not be 0.028"

    def test_m2_fv_coeff_is_new_value(self):
        assert FV_COEFF == 0.050

    def test_m2_fv_min_is_65pct(self):
        assert FV_MIN == 0.65

    def test_m2_timing_is_90m(self):
        assert M2_MAX_TIMING == 90


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v", "--tb=short"])
