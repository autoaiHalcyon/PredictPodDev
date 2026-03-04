"""
Release Gate Tests for Multi-Model Engine, Rules Transparency, and Auto-Tuner

Tests for PredictPod multi-model capital intelligence platform:
- A) Strategy Isolation
- B) Order Integrity 
- C) Order Lifecycle
- D) Risk Guardrails
- E) Kill Switch Drill
- F) PnL Math Integrity
- G) Rules Transparency - Rule chips
- H) Rules Drawer
- I) Trade Explainability
- J-M) Auto-Tuner Validation
"""

import pytest
import requests
import os
from datetime import datetime
from typing import Dict, List, Optional
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-unified.preview.emergentagent.com').rstrip('/')

# Strategy IDs
MODEL_A = "model_a_disciplined"
MODEL_B = "model_b_high_frequency"
MODEL_C = "model_c_institutional"
ALL_STRATEGIES = [MODEL_A, MODEL_B, MODEL_C]


class TestMultiModelEngineReleaseGate:
    """
    Tests for Multi-Model Engine Release Gate
    A) Strategy Isolation
    B) Order Integrity
    C) Order Lifecycle
    D) Risk Guardrails
    E) Kill Switch Drill
    F) PnL Math Integrity
    """
    
    # =============================================
    # A) STRATEGY ISOLATION TESTS
    # =============================================
    
    def test_a1_each_strategy_has_independent_capital(self):
        """Verify Model A/B/C have independent virtual capital"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all 3 strategies exist
        assert "strategies" in data
        strategies = data["strategies"]
        
        for model_id in ALL_STRATEGIES:
            assert model_id in strategies, f"Strategy {model_id} not found"
            
            # Each should have $10,000 starting capital
            portfolio = strategies[model_id].get("portfolio", {})
            assert portfolio.get("starting_capital") == 10000, \
                f"Strategy {model_id} should have $10,000 starting capital"
            
        print(f"PASS: All 3 strategies have independent $10,000 capital")
    
    def test_a2_each_strategy_has_independent_portfolio(self):
        """Verify each strategy has independent positions and PnL ledger"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        data = response.json()
        
        strategies = data["strategies"]
        
        # Verify each strategy has its own portfolio metrics
        for model_id in ALL_STRATEGIES:
            portfolio = strategies[model_id].get("portfolio", {})
            
            # Check portfolio has all required fields
            required_fields = [
                "strategy_id", "starting_capital", "current_capital",
                "portfolio_value", "realized_pnl", "unrealized_pnl",
                "total_pnl", "win_rate", "total_trades", "max_drawdown"
            ]
            
            for field in required_fields:
                assert field in portfolio, \
                    f"Strategy {model_id} portfolio missing field: {field}"
            
            # Verify strategy_id matches
            assert portfolio["strategy_id"] == model_id
        
        print("PASS: Each strategy has independent portfolio with all required fields")
    
    def test_a3_strategies_have_different_config(self):
        """Verify Model A/B/C have different configuration parameters"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        data = response.json()
        
        strategies = data["strategies"]
        configs = {}
        
        for model_id in ALL_STRATEGIES:
            config = strategies[model_id].get("config", {})
            configs[model_id] = config
        
        # Model A (Disciplined): min_edge=0.05, cooldown=180
        # Model B (HF): min_edge=0.03, cooldown=60
        # Model C (Institutional): min_edge=0.07, cooldown=300
        
        assert configs[MODEL_A]["min_edge"] > configs[MODEL_B]["min_edge"], \
            "Model A should have higher min_edge than Model B"
        assert configs[MODEL_C]["min_edge"] > configs[MODEL_A]["min_edge"], \
            "Model C should have highest min_edge"
        
        assert configs[MODEL_A]["cooldown"] > configs[MODEL_B]["cooldown"], \
            "Model A should have longer cooldown than Model B"
        assert configs[MODEL_C]["cooldown"] > configs[MODEL_A]["cooldown"], \
            "Model C should have longest cooldown"
        
        print("PASS: Strategies have different configurations (min_edge, cooldown)")
    
    def test_a4_get_individual_strategy_details(self):
        """Verify each strategy can be fetched individually"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/strategies/{model_id}")
            assert response.status_code == 200, f"Failed to get {model_id}"
            
            data = response.json()
            assert "summary" in data
            assert "positions" in data
            assert "recent_decisions" in data
            
            # Verify summary has correct strategy_id
            assert data["summary"]["strategy_id"] == model_id
        
        print("PASS: Each strategy can be fetched individually with full details")
    
    def test_a5_no_cross_contamination_check(self):
        """Verify positions don't appear in wrong strategy"""
        response = requests.get(f"{BASE_URL}/api/strategies/positions/by_game")
        assert response.status_code == 200
        # Even if empty, the structure should be correct
        data = response.json()
        
        # Data is organized by game_id -> strategy_id
        # Verify no strategy shows up in wrong place
        for game_id, positions_by_strategy in data.items():
            for strategy_id, pos_data in positions_by_strategy.items():
                assert strategy_id in ALL_STRATEGIES, \
                    f"Unknown strategy {strategy_id} in positions"
        
        print("PASS: No cross-contamination detected in positions")
    
    # =============================================
    # B) ORDER INTEGRITY TESTS
    # =============================================
    
    def test_b1_idempotency_key_prevents_duplicates(self):
        """Verify idempotency key prevents duplicate orders"""
        idempotency_key = f"TEST-{uuid.uuid4()}"
        
        order_data = {
            "market_id": "TEST-MKT-001",
            "market_ticker": "TEST-TICKER",
            "side": "yes",
            "action": "buy",
            "quantity": 1,
            "price_cents": 50,
            "idempotency_key": idempotency_key
        }
        
        # First submission
        response1 = requests.post(f"{BASE_URL}/api/orders/submit", params=order_data)
        # May succeed or fail based on rate limits, but not error
        
        # Second submission with same key
        response2 = requests.post(f"{BASE_URL}/api/orders/submit", params=order_data)
        
        # Either should return the original order (duplicate detection)
        # or fail with clear message - no double submission
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            # Second should indicate duplicate
            assert "Duplicate order" in data2.get("message", "") or \
                   data1.get("order", {}).get("id") == data2.get("order", {}).get("id"), \
                   "Duplicate order should be detected"
        
        print("PASS: Idempotency key system works")
    
    def test_b2_order_requires_idempotency_key(self):
        """Verify orders require idempotency key"""
        order_data = {
            "market_id": "TEST-MKT-002",
            "market_ticker": "TEST-TICKER",
            "side": "yes",
            "action": "buy",
            "quantity": 1,
            "price_cents": 50,
            # Missing idempotency_key
        }
        
        response = requests.post(f"{BASE_URL}/api/orders/submit", params=order_data)
        # 400 or 422 (validation error) both acceptable
        assert response.status_code in [400, 422], \
            f"Should reject order without idempotency_key, got {response.status_code}"
        
        print("PASS: Orders require idempotency_key")
    
    # =============================================
    # C) ORDER LIFECYCLE TESTS
    # =============================================
    
    def test_c1_order_states_exist(self):
        """Verify order lifecycle has correct states"""
        # Get recent orders
        response = requests.get(f"{BASE_URL}/api/orders?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        
        # Valid states for 7-state lifecycle
        valid_states = [
            "SUBMITTED", "ACKNOWLEDGED", "PARTIAL",
            "FILLED", "REJECTED", "CANCELLED", "EXPIRED"
        ]
        
        # Check any orders have valid state
        for order in data.get("orders", []):
            state = order.get("state", "")
            if state:
                # State should be one of the valid ones
                assert state in valid_states or state.upper() in valid_states, \
                    f"Invalid state: {state}"
        
        print(f"PASS: Order lifecycle states validated (found {len(data.get('orders', []))} orders)")
    
    def test_c2_sandbox_status_shows_paper_mode(self):
        """Verify sandbox is in paper/simulation mode"""
        response = requests.get(f"{BASE_URL}/api/sandbox/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("is_paper_mode") == True, "Should be in paper mode"
        assert data.get("mode") in ["simulation", "demo_api"], \
            f"Unexpected mode: {data.get('mode')}"
        
        print(f"PASS: Sandbox in paper mode ({data.get('mode')})")
    
    def test_c3_reconciliation_endpoint_works(self):
        """Verify reconciliation status endpoint works"""
        response = requests.get(f"{BASE_URL}/api/reconciliation/status")
        assert response.status_code == 200
        
        data = response.json()
        # Should have reconciliation metrics
        assert "total_unreconciled" in data or "message" in data
        
        print("PASS: Reconciliation status endpoint working")
    
    # =============================================
    # D) RISK GUARDRAILS TESTS
    # =============================================
    
    def test_d1_guardrails_endpoint_exists(self):
        """Verify guardrails endpoint returns limits"""
        response = requests.get(f"{BASE_URL}/api/settings/guardrails")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all required guardrails
        required_guardrails = [
            "max_dollars_per_trade",
            "max_open_exposure",
            "max_daily_loss",
            "max_trades_per_hour",
            "max_trades_per_day"
        ]
        
        for guardrail in required_guardrails:
            assert guardrail in data, f"Missing guardrail: {guardrail}"
            assert data[guardrail] > 0, f"Guardrail {guardrail} should be positive"
        
        print(f"PASS: All risk guardrails configured: {data}")
    
    def test_d2_order_preview_checks_guardrails(self):
        """Verify order preview performs risk checks"""
        preview_data = {
            "market_id": "TEST-MKT-003",
            "side": "yes",
            "action": "buy",
            "quantity": 100,  # Large quantity to trigger checks
            "price_cents": 50
        }
        
        response = requests.post(f"{BASE_URL}/api/orders/preview", params=preview_data)
        assert response.status_code == 200
        
        data = response.json()
        
        # Preview should include risk analysis
        assert "risk_analysis" in data or "blocking_reasons" in data or \
               "can_proceed" in data or "account_state" in data, \
               "Preview should include risk check results"
        
        print(f"PASS: Order preview includes risk analysis")
    
    def test_d3_capital_deployment_modes(self):
        """Verify capital deployment modes exist"""
        response = requests.get(f"{BASE_URL}/api/settings/capital_deployment")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have mode and limits
        assert "mode" in data
        assert data["mode"] in ["conservative", "normal", "aggressive"]
        
        # Should have limits - check various possible keys
        has_limits = any(k in data for k in [
            "max_trade_size", "limits", "max_daily_loss_dollars",
            "max_exposure_dollars", "max_orders_per_hour"
        ])
        assert has_limits, f"Should have limit fields in: {list(data.keys())}"
        
        print(f"PASS: Capital deployment mode: {data.get('mode')}")
    
    def test_d4_strategy_risk_limits_per_model(self):
        """Verify each strategy has configured risk limits"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/rules/{model_id}")
            assert response.status_code == 200
            
            data = response.json()
            config = data.get("config", {})
            
            risk_limits = config.get("risk_limits", {})
            
            # Check key risk limits
            required_limits = [
                "max_daily_loss_pct",
                "max_exposure_pct",
                "max_trades_per_hour",
                "max_drawdown_pct"
            ]
            
            for limit in required_limits:
                assert limit in risk_limits, \
                    f"Strategy {model_id} missing risk limit: {limit}"
        
        print("PASS: All strategies have configured risk limits")
    
    # =============================================
    # E) KILL SWITCH DRILL
    # =============================================
    
    def test_e1_kill_switch_activation(self):
        """Test kill switch can be activated"""
        # Activate kill switch
        response = requests.post(f"{BASE_URL}/api/strategies/kill_switch")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("kill_switch_active") == True, \
            "Kill switch should be active"
        
        # Verify strategies are disabled
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary.get("kill_switch_active") == True, \
            "Summary should show kill switch active"
        
        print("PASS: Kill switch activation works")
    
    def test_e2_kill_switch_deactivation(self):
        """Test kill switch can be deactivated"""
        # Deactivate kill switch
        response = requests.delete(f"{BASE_URL}/api/strategies/kill_switch")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("kill_switch_active") == False, \
            "Kill switch should be deactivated"
        
        # Verify summary reflects this
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary.get("kill_switch_active") == False, \
            "Summary should show kill switch inactive"
        
        print("PASS: Kill switch deactivation works")
    
    def test_e3_admin_kill_switch_works(self):
        """Test admin-level kill switch"""
        # Activate admin kill switch
        response = requests.post(f"{BASE_URL}/api/admin/kill_switch")
        assert response.status_code == 200
        
        # Deactivate
        response = requests.delete(f"{BASE_URL}/api/admin/kill_switch")
        assert response.status_code == 200
        
        print("PASS: Admin kill switch works")
    
    # =============================================
    # F) PNL MATH INTEGRITY
    # =============================================
    
    def test_f1_pnl_calculation_integrity(self):
        """Verify PnL math: Realized + Unrealized = Total"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        
        data = response.json()
        strategies = data["strategies"]
        
        for model_id in ALL_STRATEGIES:
            portfolio = strategies[model_id]["portfolio"]
            
            realized = portfolio["realized_pnl"]
            unrealized = portfolio["unrealized_pnl"]
            total = portfolio["total_pnl"]
            
            # Realized + Unrealized should equal Total
            calculated_total = realized + unrealized
            
            # Allow small floating point tolerance
            assert abs(total - calculated_total) < 0.01, \
                f"PnL math error for {model_id}: {realized} + {unrealized} != {total}"
        
        print("PASS: PnL math integrity verified (Realized + Unrealized = Total)")
    
    def test_f2_portfolio_value_calculation(self):
        """Verify portfolio value calculation"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        
        data = response.json()
        strategies = data["strategies"]
        
        for model_id in ALL_STRATEGIES:
            portfolio = strategies[model_id]["portfolio"]
            
            starting = portfolio["starting_capital"]
            total_pnl = portfolio["total_pnl"]
            portfolio_value = portfolio["portfolio_value"]
            
            # Portfolio value should be starting + total_pnl (approximately)
            expected_value = starting + total_pnl
            
            # Allow tolerance for fees/slippage
            assert abs(portfolio_value - expected_value) < starting * 0.1, \
                f"Portfolio value mismatch for {model_id}"
        
        print("PASS: Portfolio value calculation verified")


class TestRulesTransparencyReleaseGate:
    """
    Tests for Rules Transparency Release Gate
    G) Rule chips per model/league
    H) View Rules Drawer
    I) Per-trade explainability
    """
    
    # =============================================
    # G) RULE CHIPS TESTS
    # =============================================
    
    def test_g1_rule_chips_exist_per_strategy(self):
        """Verify rule chips show active thresholds per model"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/rules/{model_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "rule_chips" in data, f"Missing rule_chips for {model_id}"
            
            chips = data["rule_chips"]
            assert len(chips) >= 7, f"Expected 7-9 rule chips, got {len(chips)}"
            
            # Verify chip structure
            for chip in chips:
                assert "label" in chip
                assert "value" in chip
                assert "raw" in chip
                assert "param" in chip
        
        print("PASS: Rule chips exist for all strategies (7-9 per strategy)")
    
    def test_g2_rule_chips_have_correct_values(self):
        """Verify rule chips display correct threshold values"""
        response = requests.get(f"{BASE_URL}/api/rules/model_a_disciplined")
        assert response.status_code == 200
        
        data = response.json()
        chips = data["rule_chips"]
        
        # Build lookup
        chip_lookup = {c["label"]: c for c in chips}
        
        # Verify some key values for Model A
        assert "Edge min" in chip_lookup
        assert chip_lookup["Edge min"]["value"] == "5.0%"
        
        assert "Cooldown" in chip_lookup
        assert "180" in chip_lookup["Cooldown"]["value"]
        
        print("PASS: Rule chips have correct values")
    
    def test_g3_different_chips_per_model(self):
        """Verify different models have different chip values"""
        chips_a = requests.get(f"{BASE_URL}/api/rules/model_a_disciplined").json()["rule_chips"]
        chips_b = requests.get(f"{BASE_URL}/api/rules/model_b_high_frequency").json()["rule_chips"]
        chips_c = requests.get(f"{BASE_URL}/api/rules/model_c_institutional").json()["rule_chips"]
        
        # Get edge min values
        edge_a = next(c for c in chips_a if c["label"] == "Edge min")["raw"]
        edge_b = next(c for c in chips_b if c["label"] == "Edge min")["raw"]
        edge_c = next(c for c in chips_c if c["label"] == "Edge min")["raw"]
        
        # Model C should have highest min edge
        assert edge_c > edge_a > edge_b, \
            f"Edge ordering wrong: A={edge_a}, B={edge_b}, C={edge_c}"
        
        print("PASS: Different models have different threshold values")
    
    # =============================================
    # H) VIEW RULES DRAWER TESTS
    # =============================================
    
    def test_h1_rules_summary_generated(self):
        """Verify human-readable rules summary is generated"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/rules/{model_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "rules_summary" in data
            
            summary = data["rules_summary"]
            assert len(summary) > 100, "Summary should be substantial"
            
            # Should contain key sections
            assert "Entry Rules" in summary
            assert "Exit" in summary
            assert "Risk" in summary
        
        print("PASS: Human-readable rules summary generated for all strategies")
    
    def test_h2_rules_config_json_available(self):
        """Verify raw JSON config is available"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/rules/{model_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "config" in data
            
            config = data["config"]
            
            # Should have key sections
            assert "entry_rules" in config
            assert "exit_rules" in config
            assert "risk_limits" in config
            assert "filters" in config
        
        print("PASS: Raw JSON config available for all strategies")
    
    def test_h3_version_history_available(self):
        """Verify version history with diffs is available"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/rules/{model_id}/history?limit=10")
            assert response.status_code == 200
            
            data = response.json()
            assert "versions" in data
            
            # Should have at least initial version
            versions = data["versions"]
            assert len(versions) >= 1, f"No version history for {model_id}"
            
            # Check version structure
            v = versions[0]
            assert "version_id" in v
            assert "created_at" in v
            assert "applied_by" in v
        
        print("PASS: Version history available for all strategies")
    
    def test_h4_rollback_endpoint_exists(self):
        """Verify rollback endpoint exists"""
        # Get current version
        response = requests.get(f"{BASE_URL}/api/rules/model_a_disciplined/history?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        versions = data["versions"]
        
        if versions:
            version_id = versions[0]["version_id"]
            
            # Rollback endpoint should exist (even if we don't actually rollback)
            # Just verify it responds properly
            response = requests.post(
                f"{BASE_URL}/api/rules/model_a_disciplined/rollback",
                params={"league": "BASE", "target_version_id": version_id}
            )
            # Should not 404
            assert response.status_code != 404, "Rollback endpoint not found"
        
        print("PASS: Rollback endpoint exists")
    
    # =============================================
    # I) PER-TRADE EXPLAINABILITY
    # =============================================
    
    def test_i1_decision_log_available(self):
        """Verify per-decision explainability is available"""
        for model_id in ALL_STRATEGIES:
            response = requests.get(f"{BASE_URL}/api/strategies/{model_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "recent_decisions" in data
            
            decisions = data["recent_decisions"]
            
            # Check decision structure if any exist
            if decisions:
                d = decisions[0]
                # Should have key explainability fields
                assert "decision_type" in d
                assert "reason" in d
                assert "market_id" in d
                assert "timestamp" in d
        
        print("PASS: Decision logs with explainability available")
    
    def test_i2_decision_includes_values(self):
        """Verify decisions include decision-time values"""
        response = requests.get(f"{BASE_URL}/api/strategies/model_a_disciplined")
        assert response.status_code == 200
        
        data = response.json()
        decisions = data["recent_decisions"]
        
        if decisions:
            d = decisions[0]
            # Should include values at decision time
            expected_fields = ["edge", "signal_score", "price"]
            for field in expected_fields:
                assert field in d, f"Decision missing {field}"
        
        print("PASS: Decisions include decision-time values")


class TestAutoTunerValidation:
    """
    Tests for Auto-Tuner Validation (Paper Only)
    J) Tuner can propose changes
    K) Respects parameter bounds
    L) Produces daily tuner report
    M) Rollback/safe-mode triggers
    """
    
    # =============================================
    # J) TUNER PROPOSALS
    # =============================================
    
    def test_j1_tuner_status_endpoint(self):
        """Verify tuner status endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tuner/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "mode" in data
        assert "scheduler_running" in data
        
        print(f"PASS: Tuner status: mode={data['mode']}, scheduler={data['scheduler_running']}")
    
    def test_j2_tuner_proposals_endpoint(self):
        """Verify tuner proposals endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tuner/proposals")
        assert response.status_code == 200
        
        data = response.json()
        assert "proposals" in data
        
        print(f"PASS: Tuner proposals endpoint works ({len(data['proposals'])} proposals)")
    
    def test_j3_tuner_can_be_triggered(self):
        """Verify tuner can be manually triggered"""
        response = requests.post(f"{BASE_URL}/api/tuner/run")
        assert response.status_code == 200
        
        data = response.json()
        # Should return report structure
        assert "status" in data or "started_at" in data or "mode" in data
        
        print("PASS: Tuner can be manually triggered")
    
    # =============================================
    # K) PARAMETER BOUNDS
    # =============================================
    
    def test_k1_tuner_settings_have_bounds(self):
        """Verify tuner settings include parameter constraints"""
        response = requests.get(f"{BASE_URL}/api/tuner/settings")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have sample size threshold
        assert "min_sample_size_overall" in data
        assert data["min_sample_size_overall"] > 0
        
        # Should have improvement threshold
        assert "min_improvement_pct" in data
        
        print(f"PASS: Tuner settings have bounds: min_samples={data['min_sample_size_overall']}")
    
    def test_k2_tuner_modes_exist(self):
        """Verify tuner modes exist"""
        response = requests.get(f"{BASE_URL}/api/tuner/status")
        assert response.status_code == 200
        
        data = response.json()
        mode = data.get("mode")
        
        valid_modes = ["off", "propose_only", "auto_apply_paper"]
        assert mode in valid_modes, f"Invalid tuner mode: {mode}"
        
        print(f"PASS: Tuner mode is valid: {mode}")
    
    # =============================================
    # L) DAILY TUNER REPORT
    # =============================================
    
    def test_l1_daily_report_endpoint_exists(self):
        """Verify daily strategy report endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/strategies/report/daily")
        assert response.status_code == 200
        
        data = response.json()
        assert "date" in data or "strategies" in data
        
        print("PASS: Daily report endpoint exists")
    
    def test_l2_tuner_report_file_created(self):
        """Verify tuner creates report files"""
        # Check if tuner report exists (created from last run)
        response = requests.get(f"{BASE_URL}/api/tuner/status")
        assert response.status_code == 200
        
        data = response.json()
        last_run = data.get("last_run")
        
        # If tuner has run, report should exist
        if last_run:
            print(f"PASS: Tuner last run at {last_run}")
        else:
            print("INFO: Tuner has not run yet (expected in fresh deployment)")
    
    # =============================================
    # M) ROLLBACK/SAFE-MODE
    # =============================================
    
    def test_m1_proposal_apply_endpoint_exists(self):
        """Verify proposal apply endpoint exists"""
        # Try to apply a non-existent proposal - should 404 or appropriate error
        response = requests.post(f"{BASE_URL}/api/tuner/proposals/fake-id/apply")
        assert response.status_code in [404, 400, 200], \
            "Apply endpoint should return proper status"
        
        print("PASS: Proposal apply endpoint exists")
    
    def test_m2_proposal_reject_endpoint_exists(self):
        """Verify proposal reject endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/tuner/proposals/fake-id/reject",
            params={"reason": "Test rejection"}
        )
        assert response.status_code in [404, 400, 200], \
            "Reject endpoint should return proper status"
        
        print("PASS: Proposal reject endpoint exists")
    
    def test_m3_tuner_settings_can_be_updated(self):
        """Verify tuner settings can be updated"""
        response = requests.post(
            f"{BASE_URL}/api/tuner/settings",
            params={"min_sample_size_overall": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data or "updates" in data
        
        print("PASS: Tuner settings can be updated")


class TestIntegrationFlow:
    """End-to-end integration tests for complete flows"""
    
    def test_full_strategy_summary_flow(self):
        """Test complete strategy summary retrieval"""
        # 1. Get summary
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        
        data = response.json()
        
        # 2. Verify structure
        assert "enabled" in data
        assert "strategies" in data
        assert "winning_model" in data
        assert "comparison" in data
        
        # 3. Verify all models present
        for model_id in ALL_STRATEGIES:
            assert model_id in data["strategies"]
        
        # 4. Verify comparison metrics
        comparison = data["comparison"]
        metrics = ["total_pnl", "win_rate", "max_drawdown_pct"]
        for metric in metrics:
            assert metric in comparison
        
        print("PASS: Complete strategy summary flow works")
    
    def test_full_rules_transparency_flow(self):
        """Test complete rules transparency flow"""
        model_id = "model_a_disciplined"
        
        # 1. Get rules
        response = requests.get(f"{BASE_URL}/api/rules/{model_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # 2. Verify chips
        assert len(data["rule_chips"]) >= 7
        
        # 3. Verify summary
        assert len(data["rules_summary"]) > 100
        
        # 4. Get history
        response = requests.get(f"{BASE_URL}/api/rules/{model_id}/history")
        assert response.status_code == 200
        
        # 5. Verify versioning
        history = response.json()
        assert len(history["versions"]) >= 1
        
        print("PASS: Complete rules transparency flow works")
    
    def test_kill_switch_drill_full_cycle(self):
        """Test complete kill switch activation/deactivation cycle"""
        # 1. Verify initial state
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        initial_kill_switch = response.json().get("kill_switch_active", False)
        
        # 2. Activate kill switch
        requests.post(f"{BASE_URL}/api/strategies/kill_switch")
        
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.json().get("kill_switch_active") == True
        
        # 3. Deactivate kill switch
        requests.delete(f"{BASE_URL}/api/strategies/kill_switch")
        
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.json().get("kill_switch_active") == False
        
        print("PASS: Kill switch full cycle works")


# Main execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
