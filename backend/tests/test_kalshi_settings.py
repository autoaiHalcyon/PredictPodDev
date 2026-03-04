"""
Test suite for Kalshi Settings API endpoints - Live Trading Integration
Tests credential management, trading mode switching, guardrails, kill switch
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-unified.preview.emergentagent.com')


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(autouse=True)
def cleanup_credentials(api_client):
    """Cleanup test credentials after each test"""
    yield
    # Ensure credentials are deleted and kill switch is off after tests
    try:
        api_client.delete(f"{BASE_URL}/api/settings/kalshi_keys")
        api_client.delete(f"{BASE_URL}/api/admin/kill_switch")
    except:
        pass


class TestSettingsEndpoint:
    """GET /api/settings - System settings with Kalshi integration status"""
    
    def test_get_settings_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        print("GET /settings returns 200")
    
    def test_get_settings_includes_kalshi_section(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/settings")
        data = response.json()
        
        assert "kalshi" in data
        kalshi = data["kalshi"]
        
        # Verify kalshi section has all required fields
        assert "has_credentials" in kalshi
        assert "trading_mode" in kalshi
        assert "is_live_trading_active" in kalshi
        assert "kill_switch_active" in kalshi
        assert "server_live_trading_enabled" in kalshi
        assert "user_live_trading_enabled" in kalshi
        print("GET /settings includes kalshi section with all fields")
    
    def test_get_settings_paper_trading_default(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/settings")
        data = response.json()
        
        # By default should be paper trading mode
        assert data["kalshi"]["trading_mode"] == "paper"
        assert data["kalshi"]["is_live_trading_active"] == False
        print("Default trading mode is paper")


class TestKalshiKeysEndpoint:
    """GET/POST/DELETE /api/settings/kalshi_keys - Credential management"""
    
    def test_get_kalshi_keys_no_credentials(self, api_client):
        """When no credentials, should return empty status"""
        response = api_client.get(f"{BASE_URL}/api/settings/kalshi_keys")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_credentials"] == False
        assert data["credentials_info"] is None
        assert data["trading_mode"] == "paper"
        assert data["is_live_trading_active"] == False
        print("GET /kalshi_keys returns correct empty state")
    
    def test_save_kalshi_keys(self, api_client):
        """POST credentials should save and return masked key"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={
                "api_key": "TEST_API_KEY_12345",
                "private_key": "TEST_PRIVATE_KEY"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "Credentials saved" in data["message"]
        assert "2345" in data["masked_key"]  # Last 4 chars
        assert data["validation_status"] == "not_validated"
        print("POST /kalshi_keys saves credentials correctly")
    
    def test_save_kalshi_keys_empty_fails(self, api_client):
        """Should fail when api_key or private_key is empty"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "", "private_key": "test"}
        )
        
        assert response.status_code == 400
        print("POST /kalshi_keys rejects empty credentials")
    
    def test_get_kalshi_keys_after_save(self, api_client):
        """After saving, should return credential status"""
        # First save
        api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "TEST_KEY_ABCD", "private_key": "TEST_PRIVATE"}
        )
        
        # Then get
        response = api_client.get(f"{BASE_URL}/api/settings/kalshi_keys")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_credentials"] == True
        assert data["credentials_info"]["has_credentials"] == True
        assert "ABCD" in data["credentials_info"]["masked_key_last4"]
        assert data["credentials_info"]["validation_status"] == "not_validated"
        print("GET /kalshi_keys shows saved credentials")
    
    def test_delete_kalshi_keys(self, api_client):
        """DELETE should remove credentials"""
        # First save
        api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "TO_DELETE_KEY", "private_key": "TO_DELETE_PRIVATE"}
        )
        
        # Delete
        response = api_client.delete(f"{BASE_URL}/api/settings/kalshi_keys")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "deleted" in data["message"].lower()
        
        # Verify deleted
        verify_response = api_client.get(f"{BASE_URL}/api/settings/kalshi_keys")
        verify_data = verify_response.json()
        assert verify_data["has_credentials"] == False
        print("DELETE /kalshi_keys removes credentials")


class TestKalshiValidation:
    """POST /api/settings/kalshi_keys/validate - Credential validation"""
    
    def test_validate_no_credentials(self, api_client):
        """Should fail when no credentials stored"""
        # Ensure no credentials
        api_client.delete(f"{BASE_URL}/api/settings/kalshi_keys")
        
        response = api_client.post(f"{BASE_URL}/api/settings/kalshi_keys/validate")
        assert response.status_code == 200  # Returns 200 with error in body
        
        data = response.json()
        assert data["valid"] == False
        assert "No credentials" in data["message"]
        print("Validate fails when no credentials")
    
    def test_validate_invalid_credentials(self, api_client):
        """Should return invalid for fake credentials"""
        # Save fake credentials
        api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "FAKE_KEY", "private_key": "FAKE_PRIVATE"}
        )
        
        response = api_client.post(f"{BASE_URL}/api/settings/kalshi_keys/validate")
        assert response.status_code == 200
        
        data = response.json()
        assert data["valid"] == False
        # Should get error from Kalshi API (invalid credentials or connection error)
        print(f"Validate returns invalid with message: {data['message']}")


class TestGuardrailsEndpoint:
    """GET/PUT /api/settings/guardrails - Trading guardrails"""
    
    def test_get_guardrails(self, api_client):
        """Should return default guardrails"""
        response = api_client.get(f"{BASE_URL}/api/settings/guardrails")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all guardrail fields present
        assert "max_dollars_per_trade" in data
        assert "max_open_exposure" in data
        assert "max_daily_loss" in data
        assert "max_trades_per_hour" in data
        assert "max_trades_per_day" in data
        assert "guardrails_enabled" in data
        
        # Verify default values are reasonable
        assert data["max_dollars_per_trade"] > 0
        assert data["max_open_exposure"] > 0
        assert data["guardrails_enabled"] == True
        print("GET /guardrails returns all fields with defaults")
    
    def test_update_guardrails(self, api_client):
        """Should update guardrails"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/guardrails",
            params={
                "max_dollars_per_trade": 25,
                "max_daily_loss": 75,
                "max_trades_per_hour": 15
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["guardrails"]["max_dollars_per_trade"] == 25
        assert data["guardrails"]["max_daily_loss"] == 75
        assert data["guardrails"]["max_trades_per_hour"] == 15
        print("PUT /guardrails updates values correctly")
    
    def test_get_guardrails_after_update(self, api_client):
        """Updated guardrails should persist"""
        # Update
        api_client.put(
            f"{BASE_URL}/api/settings/guardrails",
            params={"max_dollars_per_trade": 30}
        )
        
        # Verify persisted
        response = api_client.get(f"{BASE_URL}/api/settings/guardrails")
        data = response.json()
        
        assert data["max_dollars_per_trade"] == 30
        print("Guardrails persist after update")


class TestKillSwitch:
    """POST/DELETE /api/admin/kill_switch - Emergency kill switch"""
    
    def test_activate_kill_switch(self, api_client):
        """Should activate kill switch"""
        response = api_client.post(f"{BASE_URL}/api/admin/kill_switch")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "KILL SWITCH ACTIVATED" in data["message"]
        assert data["trading_mode"] == "paper"
        print("POST /admin/kill_switch activates")
    
    def test_kill_switch_blocks_live_trading(self, api_client):
        """Kill switch should prevent live trading"""
        # Activate kill switch
        api_client.post(f"{BASE_URL}/api/admin/kill_switch")
        
        # Check settings
        response = api_client.get(f"{BASE_URL}/api/settings")
        data = response.json()
        
        assert data["kalshi"]["kill_switch_active"] == True
        assert data["kalshi"]["is_live_trading_active"] == False
        print("Kill switch blocks live trading")
    
    def test_deactivate_kill_switch(self, api_client):
        """Should deactivate kill switch"""
        # Activate first
        api_client.post(f"{BASE_URL}/api/admin/kill_switch")
        
        # Deactivate
        response = api_client.delete(f"{BASE_URL}/api/admin/kill_switch")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "deactivated" in data["message"].lower()
        
        # Verify deactivated
        settings = api_client.get(f"{BASE_URL}/api/settings").json()
        assert settings["kalshi"]["kill_switch_active"] == False
        print("DELETE /admin/kill_switch deactivates")


class TestLiveTradingControl:
    """POST /api/settings/live_trading/enable and /disable"""
    
    def test_enable_live_trading_without_confirmation(self, api_client):
        """Should fail without risk acknowledgment"""
        response = api_client.post(
            f"{BASE_URL}/api/settings/live_trading/enable",
            params={"confirmed_risk": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        assert "acknowledge" in data["message"].lower() or "must" in data["message"].lower()
        print("Enable live trading fails without confirmation")
    
    def test_enable_live_trading_no_credentials(self, api_client):
        """Should fail when no credentials"""
        # Ensure no credentials
        api_client.delete(f"{BASE_URL}/api/settings/kalshi_keys")
        
        response = api_client.post(
            f"{BASE_URL}/api/settings/live_trading/enable",
            params={"confirmed_risk": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        assert "credential" in data["message"].lower()
        print("Enable live trading fails without credentials")
    
    def test_enable_live_trading_invalid_credentials(self, api_client):
        """Should fail when credentials not validated"""
        # Save unvalidated credentials
        api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "UNVALIDATED_KEY", "private_key": "UNVALIDATED_PRIVATE"}
        )
        
        response = api_client.post(
            f"{BASE_URL}/api/settings/live_trading/enable",
            params={"confirmed_risk": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == False
        assert "validate" in data["message"].lower()
        print("Enable live trading fails with unvalidated credentials")
    
    def test_disable_live_trading(self, api_client):
        """Should successfully disable live trading"""
        response = api_client.post(f"{BASE_URL}/api/settings/live_trading/disable")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["trading_mode"] == "paper"
        assert "paper" in data["message"].lower() or "disabled" in data["message"].lower()
        print("Disable live trading works")


class TestAuditLog:
    """GET /api/admin/audit_log - Trading audit log"""
    
    def test_get_audit_log(self, api_client):
        """Should return audit log entries"""
        # Generate some audit events
        api_client.post(f"{BASE_URL}/api/admin/kill_switch")
        api_client.delete(f"{BASE_URL}/api/admin/kill_switch")
        
        response = api_client.get(f"{BASE_URL}/api/admin/audit_log", params={"limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            event = data[0]
            assert "event_type" in event
            assert "timestamp" in event
            assert "details" in event
        print(f"GET /admin/audit_log returns {len(data)} events")
    
    def test_audit_log_records_events(self, api_client):
        """Audit log should record credential and trading events"""
        # Perform actions that should be logged
        api_client.post(
            f"{BASE_URL}/api/settings/kalshi_keys",
            params={"api_key": "AUDIT_TEST_KEY", "private_key": "AUDIT_TEST_PRIVATE"}
        )
        
        time.sleep(0.5)  # Wait for DB write
        
        response = api_client.get(f"{BASE_URL}/api/admin/audit_log", params={"limit": 5})
        data = response.json()
        
        # Should have CREDENTIALS_SAVED event
        event_types = [e["event_type"] for e in data]
        assert "CREDENTIALS_SAVED" in event_types
        print("Audit log records credential events")


class TestRootEndpointTradingMode:
    """GET /api/ - Root endpoint should show trading mode"""
    
    def test_root_shows_paper_mode(self, api_client):
        """Root endpoint should indicate paper mode"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "paper_mode" in data
        assert "kalshi_mode" in data
        assert data["paper_mode"] == True
        assert data["kalshi_mode"] == "MOCKED"
        print("Root endpoint shows paper mode")


class TestHealthEndpointKalshi:
    """GET /api/health - Health check should include Kalshi integration status"""
    
    def test_health_includes_kalshi_integration(self, api_client):
        """Health check should show Kalshi integration status"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "components" in data
        assert "kalshi_integration" in data["components"]
        
        kalshi = data["components"]["kalshi_integration"]
        assert "has_credentials" in kalshi
        assert "kill_switch_active" in kalshi
        print("Health endpoint includes Kalshi integration status")
    
    def test_health_shows_paper_trading_metrics(self, api_client):
        """Health check should show paper trading in metrics"""
        response = api_client.get(f"{BASE_URL}/api/health")
        data = response.json()
        
        assert "metrics" in data
        assert "paper_trading_mode" in data["metrics"]
        assert "live_trading_enabled" in data["metrics"]
        print("Health endpoint shows trading mode in metrics")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
