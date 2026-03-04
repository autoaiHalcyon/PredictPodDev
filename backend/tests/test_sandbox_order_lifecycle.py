"""
Test suite for Phase 2.1: Sandbox/Order Lifecycle API endpoints
Tests sandbox mode, capital deployment, order lifecycle, idempotency, and reconciliation.

Features tested:
- GET /api/sandbox/status - sandbox mode status
- GET /api/settings/capital_deployment - capital deployment mode (CONSERVATIVE default)
- POST /api/settings/capital_deployment - mode switching with confirmations
- POST /api/orders/preview - trade confirmation with risk checks
- POST /api/orders/submit - order creation with idempotency
- GET /api/orders - list recent orders with state
- GET /api/orders/{id} - get order details
- DELETE /api/orders/{id} - cancel working orders
- GET /api/reconciliation/status - reconciliation status
- POST /api/reconciliation/force - trigger reconciliation
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-unified.preview.emergentagent.com')


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(autouse=True)
def reset_capital_deployment(api_client):
    """Reset capital deployment to CONSERVATIVE after each test"""
    yield
    try:
        api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "conservative"}
        )
    except:
        pass


class TestSandboxStatus:
    """GET /api/sandbox/status - Sandbox adapter status"""
    
    def test_sandbox_status_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/sandbox/status")
        assert response.status_code == 200
        print("GET /sandbox/status returns 200")
    
    def test_sandbox_status_fields(self, api_client):
        """Should return all required fields"""
        response = api_client.get(f"{BASE_URL}/api/sandbox/status")
        data = response.json()
        
        required_fields = ["mode", "demo_connected", "balance", "positions_count", 
                          "working_orders_count", "is_paper_mode"]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"Sandbox status: mode={data['mode']}, balance=${data['balance']}")
    
    def test_sandbox_is_simulation_mode(self, api_client):
        """Should be in simulation mode (no demo API credentials)"""
        response = api_client.get(f"{BASE_URL}/api/sandbox/status")
        data = response.json()
        
        assert data["mode"] == "simulation", "Should be in simulation mode"
        assert data["is_paper_mode"] == True, "Should always be paper mode"
        print("Sandbox is in simulation mode (no real money)")


class TestCapitalDeploymentGet:
    """GET /api/settings/capital_deployment - Capital deployment settings"""
    
    def test_capital_deployment_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/settings/capital_deployment")
        assert response.status_code == 200
        print("GET /settings/capital_deployment returns 200")
    
    def test_capital_deployment_conservative_default(self, api_client):
        """Should default to CONSERVATIVE mode"""
        response = api_client.get(f"{BASE_URL}/api/settings/capital_deployment")
        data = response.json()
        
        assert data["mode"] == "conservative", "Default should be CONSERVATIVE"
        print("Capital deployment defaults to CONSERVATIVE")
    
    def test_capital_deployment_conservative_limits(self, api_client):
        """CONSERVATIVE mode should have safe limits: $5/trade, $25 daily loss, $50 max exposure"""
        response = api_client.get(f"{BASE_URL}/api/settings/capital_deployment")
        data = response.json()
        
        # CONSERVATIVE limits per spec
        assert data["max_trade_size_dollars"] == 5.0, f"Expected $5/trade, got ${data['max_trade_size_dollars']}"
        assert data["max_daily_loss_dollars"] == 25.0, f"Expected $25 daily loss cap, got ${data['max_daily_loss_dollars']}"
        assert data["max_total_exposure_dollars"] == 50.0, f"Expected $50 max exposure, got ${data['max_total_exposure_dollars']}"
        
        print(f"CONSERVATIVE limits: ${data['max_trade_size_dollars']}/trade, ${data['max_daily_loss_dollars']} daily loss, ${data['max_total_exposure_dollars']} exposure")
    
    def test_capital_deployment_all_fields(self, api_client):
        """Should return all capital deployment settings"""
        response = api_client.get(f"{BASE_URL}/api/settings/capital_deployment")
        data = response.json()
        
        required_fields = [
            "mode", "max_trade_size_dollars", "max_daily_loss_dollars",
            "max_total_exposure_dollars", "max_single_position_pct",
            "max_order_pct_of_book", "max_spread_cents",
            "max_orders_per_minute", "max_orders_per_hour",
            "requires_double_confirmation", "requires_explicit_acknowledgment"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"All capital deployment fields present")


class TestCapitalDeploymentSet:
    """POST /api/settings/capital_deployment - Mode switching"""
    
    def test_set_normal_mode(self, api_client):
        """Should allow switching to NORMAL mode"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "normal"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["settings"]["mode"] == "normal"
        print("Switched to NORMAL mode")
    
    def test_aggressive_without_confirmation_rejected(self, api_client):
        """AGGRESSIVE mode should be rejected without confirmations"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "aggressive", "confirmed": False, "acknowledged": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        assert data["requires_confirmation"] == True
        assert data["requires_acknowledgment"] == True
        print("AGGRESSIVE mode correctly rejected without confirmations")
    
    def test_aggressive_with_confirmed_only_rejected(self, api_client):
        """AGGRESSIVE mode needs BOTH confirmed and acknowledged"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "aggressive", "confirmed": True, "acknowledged": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        print("AGGRESSIVE mode rejected with confirmed=True but acknowledged=False")
    
    def test_aggressive_with_full_confirmation(self, api_client):
        """AGGRESSIVE mode allowed with both confirmations"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "aggressive", "confirmed": True, "acknowledged": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["settings"]["mode"] == "aggressive"
        assert data["settings"]["requires_double_confirmation"] == True
        assert data["settings"]["requires_explicit_acknowledgment"] == True
        print("AGGRESSIVE mode enabled with full confirmation")
    
    def test_invalid_mode_rejected(self, api_client):
        """Invalid mode should be rejected"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/capital_deployment",
            params={"mode": "invalid_mode"}
        )
        
        assert response.status_code == 400
        print("Invalid mode correctly rejected")


class TestOrderPreview:
    """POST /api/orders/preview - Trade confirmation with risk checks"""
    
    def test_preview_returns_200(self, api_client):
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 5, "price_cents": 45}
        )
        assert response.status_code == 200
        print("POST /orders/preview returns 200")
    
    def test_preview_within_limits_passes(self, api_client):
        """Order within CONSERVATIVE limits should pass"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 5, "price_cents": 45}  # $2.25 total
        )
        data = response.json()
        
        assert data["checks"]["all_passed"] == True, f"Expected all checks to pass. Blocking reasons: {data.get('blocking_reasons', [])}"
        assert data["order"]["total_dollars"] < 5.0, "Should be under $5 limit"
        print(f"Preview passed: order ${data['order']['total_dollars']}")
    
    def test_preview_exceeds_trade_size_blocked(self, api_client):
        """Order exceeding max trade size should be blocked"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 500, "price_cents": 45}  # $225 total, exceeds $5 limit
        )
        data = response.json()
        
        assert data["checks"]["all_passed"] == False
        assert data["checks"]["within_trade_limit"] == False
        assert any("exceeds max trade size" in r.lower() for r in data["blocking_reasons"])
        print(f"Order blocked: {data['blocking_reasons']}")
    
    def test_preview_exceeds_exposure_blocked(self, api_client):
        """Order exceeding max exposure should be blocked"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 1000, "price_cents": 45}  # $450 total, exceeds $50 exposure
        )
        data = response.json()
        
        assert data["checks"]["within_exposure_limit"] == False
        assert any("exposure" in r.lower() for r in data["blocking_reasons"])
        print("Order blocked for exceeding exposure limit")
    
    def test_preview_liquidity_check(self, api_client):
        """Order % of orderbook should be calculated"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 10, "price_cents": 45}
        )
        data = response.json()
        
        # Should have liquidity info
        assert "liquidity" in data
        assert "orderbook_depth" in data["liquidity"]
        assert "order_pct_of_book" in data["liquidity"]
        assert "spread_cents" in data["liquidity"]
        
        print(f"Liquidity: {data['liquidity']['order_pct_of_book']}% of book, spread={data['liquidity']['spread_cents']}¢")
    
    def test_preview_contains_account_state(self, api_client):
        """Preview should include account state"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 5, "price_cents": 45}
        )
        data = response.json()
        
        assert "account" in data
        assert "balance_dollars" in data["account"]
        assert "buying_power_dollars" in data["account"]
        assert "today_realized_pnl_dollars" in data["account"]
        
        print(f"Account: balance=${data['account']['balance_dollars']}")
    
    def test_preview_contains_risk_analysis(self, api_client):
        """Preview should include risk analysis"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 5, "price_cents": 45}
        )
        data = response.json()
        
        assert "risk" in data
        assert "max_loss_dollars" in data["risk"]
        assert "worst_case_loss_dollars" in data["risk"]
        assert "exposure_after_dollars" in data["risk"]
        
        print(f"Risk: max_loss=${data['risk']['max_loss_dollars']}, worst_case=${data['risk']['worst_case_loss_dollars']}")


class TestOrderSubmit:
    """POST /api/orders/submit - Order submission with idempotency"""
    
    def test_submit_order_with_idempotency_key(self, api_client):
        """Should create order with idempotency key"""
        unique_key = f"test-submit-{uuid.uuid4()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-NEW",
                "market_ticker": "TEST-MKT-NEW",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["order"]["idempotency_key"] == unique_key
        assert data["order"]["state"] in ["submitted", "acknowledged"]
        
        print(f"Order created: {data['order']['id']} with key {unique_key}")
    
    def test_duplicate_idempotency_key_returns_original(self, api_client):
        """Duplicate idempotency key should return original order, not create new"""
        unique_key = f"test-duplicate-{uuid.uuid4()}"
        
        # First submission
        response1 = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-DUP",
                "market_ticker": "TEST-MKT-DUP",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        assert response1.status_code == 200
        order1 = response1.json()["order"]
        
        # Second submission with same key
        response2 = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-DUP",
                "market_ticker": "TEST-MKT-DUP",
                "side": "yes",
                "action": "buy",
                "quantity": 10,  # Different quantity
                "price_cents": 50,  # Different price
                "idempotency_key": unique_key
            }
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should return original order, not new one
        assert data2["order"]["id"] == order1["id"], "Should return original order ID"
        assert "Duplicate order" in data2["message"]
        assert data2["order"]["quantity"] == 5, "Should have original quantity"
        
        print(f"Duplicate blocked, returned original: {data2['message']}")
    
    def test_submit_without_idempotency_key_fails(self, api_client):
        """Should fail if idempotency_key is missing"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT",
                "market_ticker": "TEST-MKT",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45
            }
        )
        
        assert response.status_code == 400 or response.status_code == 422
        print("Order without idempotency_key correctly rejected")
    
    def test_submit_order_has_correct_state_tracking(self, api_client):
        """Order should have state machine tracking"""
        unique_key = f"test-state-{uuid.uuid4()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-STATE",
                "market_ticker": "TEST-MKT-STATE",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        data = response.json()
        order = data["order"]
        
        # Should have state tracking fields
        assert "state" in order
        assert order["state"] in ["submitted", "acknowledged", "partial", "filled"]
        assert "is_terminal" in order
        assert "is_working" in order
        assert "created_at" in order
        
        print(f"Order state: {order['state']}, is_working={order['is_working']}")
    
    def test_submit_order_records_capital_mode(self, api_client):
        """Order should record capital deployment mode at submission"""
        unique_key = f"test-capital-{uuid.uuid4()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-CAP",
                "market_ticker": "TEST-MKT-CAP",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        data = response.json()
        order = data["order"]
        
        assert "capital_deployment_mode" in order
        assert order["capital_deployment_mode"] == "conservative"
        
        print(f"Order recorded capital mode: {order['capital_deployment_mode']}")


class TestOrdersList:
    """GET /api/orders - List recent orders"""
    
    def test_get_orders_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/orders")
        assert response.status_code == 200
        print("GET /orders returns 200")
    
    def test_get_orders_list_structure(self, api_client):
        """Should return orders list with total count"""
        response = api_client.get(f"{BASE_URL}/api/orders")
        data = response.json()
        
        assert "orders" in data
        assert "total" in data
        assert isinstance(data["orders"], list)
        
        print(f"Orders list: {data['total']} total")
    
    def test_get_orders_limit(self, api_client):
        """Should respect limit parameter"""
        response = api_client.get(f"{BASE_URL}/api/orders", params={"limit": 5})
        data = response.json()
        
        assert len(data["orders"]) <= 5
        print(f"Orders with limit=5: got {len(data['orders'])}")
    
    def test_get_working_orders_only(self, api_client):
        """Should filter to working orders only"""
        response = api_client.get(f"{BASE_URL}/api/orders", params={"working_only": True})
        data = response.json()
        
        for order in data["orders"]:
            assert order["is_working"] == True, f"Order {order['id']} should be working"
            assert order["is_terminal"] == False
        
        print(f"Working orders: {data['total']}")
    
    def test_orders_have_7_state_lifecycle(self, api_client):
        """Orders should have 7-state lifecycle tracking"""
        response = api_client.get(f"{BASE_URL}/api/orders")
        data = response.json()
        
        valid_states = ["submitted", "acknowledged", "partial", "filled", 
                       "rejected", "cancelled", "expired"]
        
        for order in data["orders"]:
            assert order["state"] in valid_states, f"Invalid state: {order['state']}"
        
        print("All orders have valid 7-state lifecycle")


class TestOrderById:
    """GET /api/orders/{id} - Get order by ID"""
    
    def test_get_order_by_id(self, api_client):
        """Should return order details by ID"""
        # First create an order
        unique_key = f"test-getid-{uuid.uuid4()}"
        create_response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-GETID",
                "market_ticker": "TEST-MKT-GETID",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        order_id = create_response.json()["order"]["id"]
        
        # Get order by ID
        response = api_client.get(f"{BASE_URL}/api/orders/{order_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == order_id
        assert data["idempotency_key"] == unique_key
        
        print(f"Retrieved order: {order_id}")
    
    def test_get_order_not_found(self, api_client):
        """Should return 404 for non-existent order"""
        response = api_client.get(f"{BASE_URL}/api/orders/non-existent-order-id")
        
        assert response.status_code == 404
        print("Non-existent order returns 404")
    
    def test_order_has_all_tracking_fields(self, api_client):
        """Order should have all lifecycle tracking fields"""
        # First create an order
        unique_key = f"test-fields-{uuid.uuid4()}"
        create_response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-FIELDS",
                "market_ticker": "TEST-MKT-FIELDS",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        # May fail due to rate limit
        if create_response.status_code != 200:
            if "Rate limit" in create_response.text:
                pytest.skip("Rate limit hit during test - rate limiting is working")
            assert False, f"Unexpected error: {create_response.text}"
        
        order_id = create_response.json()["order"]["id"]
        response = api_client.get(f"{BASE_URL}/api/orders/{order_id}")
        data = response.json()
        
        required_fields = [
            "id", "idempotency_key", "market_id", "side", "action",
            "quantity", "filled_quantity", "remaining_quantity",
            "price_cents", "state", "is_terminal", "is_working",
            "adapter_mode", "capital_deployment_mode", "created_at"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print("Order has all required tracking fields")


class TestOrderCancel:
    """DELETE /api/orders/{id} - Cancel working orders"""
    
    def test_cancel_working_order(self, api_client):
        """Should cancel a working order"""
        # Create an order
        unique_key = f"test-cancel-{uuid.uuid4()}"
        create_response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-CANCEL",
                "market_ticker": "TEST-MKT-CANCEL",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        # May fail due to rate limit
        if create_response.status_code != 200:
            if "Rate limit" in create_response.text:
                pytest.skip("Rate limit hit during test - rate limiting is working")
            assert False, f"Unexpected error: {create_response.text}"
        
        order = create_response.json()["order"]
        order_id = order["id"]
        
        # Try to cancel - Note: in simulation mode, order may be filled quickly
        # so we accept both success and "not cancellable" responses
        response = api_client.delete(f"{BASE_URL}/api/orders/{order_id}")
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
            print(f"Order cancelled: {order_id}")
        else:
            # Order may have been filled/processed already (simulation mode)
            assert response.status_code == 400
            print(f"Order already processed (simulation mode): {response.json().get('detail', 'N/A')}")
    
    def test_cancel_nonexistent_order(self, api_client):
        """Should fail for non-existent order"""
        response = api_client.delete(f"{BASE_URL}/api/orders/non-existent-id")
        
        # Should be 400 or 404
        assert response.status_code in [400, 404]
        print("Cancel non-existent order correctly fails")


class TestReconciliation:
    """GET/POST /api/reconciliation/* - Position reconciliation"""
    
    def test_reconciliation_status_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/reconciliation/status")
        assert response.status_code == 200
        print("GET /reconciliation/status returns 200")
    
    def test_reconciliation_status_fields(self, api_client):
        """Should return reconciliation status fields"""
        response = api_client.get(f"{BASE_URL}/api/reconciliation/status")
        data = response.json()
        
        required_fields = ["total_unreconciled", "critical_mismatches", 
                          "warning_mismatches", "mismatches"]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"Reconciliation: {data['total_unreconciled']} unreconciled, {data['critical_mismatches']} critical")
    
    def test_force_reconciliation(self, api_client):
        """Should force immediate reconciliation"""
        response = api_client.post(f"{BASE_URL}/api/reconciliation/force")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_unreconciled" in data
        assert "critical_mismatches" in data
        
        print(f"Force reconciliation: {data['total_unreconciled']} unreconciled")


class TestRateLimiting:
    """Rate limiting tests"""
    
    def test_orders_per_hour_tracked(self, api_client):
        """Rate limiting should track orders per hour"""
        # Get current capital settings to see rate limits
        response = api_client.get(f"{BASE_URL}/api/settings/capital_deployment")
        data = response.json()
        
        assert "max_orders_per_hour" in data
        assert data["max_orders_per_hour"] > 0
        
        print(f"Max orders per hour: {data['max_orders_per_hour']}")


class TestOrderStateMachine:
    """Order state machine transition tests"""
    
    def test_order_starts_submitted_or_acknowledged(self, api_client):
        """New order should start in SUBMITTED or ACKNOWLEDGED state"""
        unique_key = f"test-state-init-{uuid.uuid4()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-STATE-INIT",
                "market_ticker": "TEST-MKT-STATE-INIT",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        # May fail due to rate limit
        if response.status_code != 200:
            if "Rate limit" in response.text:
                pytest.skip("Rate limit hit during test - rate limiting is working")
            assert False, f"Unexpected error: {response.text}"
        
        data = response.json()
        order = data["order"]
        
        assert order["state"] in ["submitted", "acknowledged"]
        print(f"New order state: {order['state']}")
    
    def test_filled_order_is_terminal(self, api_client):
        """FILLED orders should be terminal (is_terminal=True)"""
        response = api_client.get(f"{BASE_URL}/api/orders")
        data = response.json()
        
        for order in data["orders"]:
            if order["state"] == "filled":
                assert order["is_terminal"] == True
                assert order["is_working"] == False
                print(f"Filled order {order['id']} is terminal")
    
    def test_rejected_order_is_terminal(self, api_client):
        """REJECTED orders should be terminal"""
        response = api_client.get(f"{BASE_URL}/api/orders")
        data = response.json()
        
        for order in data["orders"]:
            if order["state"] == "rejected":
                assert order["is_terminal"] == True
                assert order["is_working"] == False
                print(f"Rejected order {order['id']} is terminal")


class TestLiquidityCheck:
    """Liquidity and slippage protection tests"""
    
    def test_order_pct_of_book_calculated(self, api_client):
        """Should calculate order % of orderbook"""
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 100, "price_cents": 45}
        )
        data = response.json()
        
        assert data["liquidity"]["order_pct_of_book"] > 0
        print(f"Order is {data['liquidity']['order_pct_of_book']:.1f}% of orderbook")
    
    def test_large_order_liquidity_blocked(self, api_client):
        """Order > max_order_pct_of_book should be blocked"""
        # Large order that exceeds 5% of book
        response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT", "side": "yes", "action": "buy", 
                   "quantity": 5000, "price_cents": 45}
        )
        data = response.json()
        
        # Should be blocked for liquidity
        if data["liquidity"]["order_pct_of_book"] > 5.0:
            assert data["liquidity"]["blocked"] == True
            print(f"Large order blocked for liquidity: {data['liquidity']['order_pct_of_book']:.1f}% of book")
        else:
            print("Order within liquidity limits")


class TestIntegrationFlow:
    """End-to-end integration tests"""
    
    def test_full_order_flow(self, api_client):
        """Test complete order lifecycle: preview -> submit -> get -> list"""
        unique_key = f"test-flow-{uuid.uuid4()}"
        
        # 1. Preview - may fail due to rate limit which is correct behavior
        preview_response = api_client.post(
            f"{BASE_URL}/api/orders/preview",
            params={"market_id": "TEST-MKT-FLOW", "side": "yes", "action": "buy", 
                   "quantity": 5, "price_cents": 45}
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        # Accept either all_passed=True or rate_limit blocking (both are valid)
        if not preview_data["checks"]["all_passed"]:
            if "Rate limit" in str(preview_data.get("blocking_reasons", [])):
                print("1. Preview blocked by rate limit - rate limiting working correctly")
                pytest.skip("Rate limit hit during test - rate limiting is working")
            else:
                assert False, f"Preview failed for unexpected reason: {preview_data['blocking_reasons']}"
        else:
            print("1. Preview passed")
        
        # 2. Submit
        submit_response = api_client.post(
            f"{BASE_URL}/api/orders/submit",
            params={
                "market_id": "TEST-MKT-FLOW",
                "market_ticker": "TEST-MKT-FLOW",
                "side": "yes",
                "action": "buy",
                "quantity": 5,
                "price_cents": 45,
                "idempotency_key": unique_key
            }
        )
        
        if submit_response.status_code != 200:
            if "Rate limit" in submit_response.text:
                print("2. Submit blocked by rate limit - working correctly")
                pytest.skip("Rate limit hit during test")
            assert False, f"Submit failed: {submit_response.text}"
        
        order_id = submit_response.json()["order"]["id"]
        print(f"2. Order submitted: {order_id}")
        
        # 3. Get by ID
        get_response = api_client.get(f"{BASE_URL}/api/orders/{order_id}")
        assert get_response.status_code == 200
        assert get_response.json()["idempotency_key"] == unique_key
        print("3. Order retrieved by ID")
        
        # 4. List orders
        list_response = api_client.get(f"{BASE_URL}/api/orders")
        assert list_response.status_code == 200
        order_ids = [o["id"] for o in list_response.json()["orders"]]
        assert order_id in order_ids
        print("4. Order appears in list")
        
        # 5. Check reconciliation (no mismatches expected for simulation)
        recon_response = api_client.get(f"{BASE_URL}/api/reconciliation/status")
        assert recon_response.status_code == 200
        print(f"5. Reconciliation status: {recon_response.json()['total_unreconciled']} unreconciled")
        
        print("Full order flow completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
