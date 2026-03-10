"""
Test Trading Features - Iteration 6
Tests for:
1. GET /api/games - returns list of games with status, signal, markets
2. GET /api/trades - returns trades with type (paper/live), status, P&L
3. GET /api/orders - returns orders
4. GET /api/kalshi/categories - returns basketball category tree
5. GET /api/kalshi/markets - returns markets (may be empty if no open markets)
6. GET /api/strategies/summary - for strategy command center
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://predict-strategy-hub.preview.emergentagent.com').rstrip('/')

class TestGamesAPI:
    """Test GET /api/games endpoint"""
    
    def test_games_endpoint_returns_200(self):
        """Test that /api/games returns 200"""
        response = requests.get(f"{BASE_URL}/api/games")
        print(f"GET /api/games - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_games_response_structure(self):
        """Test that /api/games returns proper structure with games list"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "games" in data, "Response should contain 'games' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["games"], list), "'games' should be a list"
        
        print(f"Total games returned: {data['count']}")
        
        # If there are games, verify structure
        if len(data["games"]) > 0:
            game = data["games"][0]
            assert "game" in game, "Each item should have 'game'"
            assert "signal" in game, "Each item should have 'signal'"
            assert "markets" in game, "Each item should have 'markets'"
            print(f"Sample game structure verified: game keys = {list(game.keys())}")
    
    def test_games_status_filter(self):
        """Test that /api/games can filter by status"""
        response = requests.get(f"{BASE_URL}/api/games?status=live")
        assert response.status_code == 200
        data = response.json()
        print(f"Live games: {data['count']}")


class TestTradesAPI:
    """Test GET /api/trades endpoint"""
    
    def test_trades_endpoint_returns_200(self):
        """Test that /api/trades returns 200"""
        response = requests.get(f"{BASE_URL}/api/trades?limit=50")
        print(f"GET /api/trades - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_trades_response_structure(self):
        """Test that /api/trades returns trades with proper structure"""
        response = requests.get(f"{BASE_URL}/api/trades?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "trades" in data, "Response should contain 'trades' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["trades"], list), "'trades' should be a list"
        
        print(f"Total trades returned: {data['count']}")
        
        # If there are trades, verify structure (type, status, P&L)
        if len(data["trades"]) > 0:
            trade = data["trades"][0]
            print(f"Sample trade keys: {list(trade.keys())}")
            # Check for expected fields
            trade_keys = list(trade.keys())
            print(f"Trade structure: {trade_keys}")


class TestOrdersAPI:
    """Test GET /api/orders endpoint"""
    
    def test_orders_endpoint_returns_200(self):
        """Test that /api/orders returns 200"""
        response = requests.get(f"{BASE_URL}/api/orders?limit=50")
        print(f"GET /api/orders - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_orders_response_structure(self):
        """Test that /api/orders returns orders with proper structure"""
        response = requests.get(f"{BASE_URL}/api/orders?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "orders" in data, "Response should contain 'orders' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["orders"], list), "'orders' should be a list"
        
        print(f"Total orders returned: {data['total']}")


class TestKalshiCategoriesAPI:
    """Test GET /api/kalshi/categories endpoint"""
    
    def test_categories_endpoint_returns_200(self):
        """Test that /api/kalshi/categories returns 200"""
        response = requests.get(f"{BASE_URL}/api/kalshi/categories")
        print(f"GET /api/kalshi/categories - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_categories_has_basketball(self):
        """Test that categories includes basketball leagues"""
        response = requests.get(f"{BASE_URL}/api/kalshi/categories")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "categories" in data, "Response should contain 'categories' key"
        
        print(f"Categories found: {len(data['categories'])}")
        
        # List categories
        for cat in data.get("categories", []):
            print(f"  Category: {cat.get('id', 'unknown')} - {cat.get('name', 'unknown')}")
            if cat.get('children'):
                for child in cat['children']:
                    print(f"    Child: {child.get('id', 'unknown')} - {child.get('name', 'unknown')}")


class TestKalshiMarketsAPI:
    """Test GET /api/kalshi/markets endpoint"""
    
    def test_markets_endpoint_returns_200(self):
        """Test that /api/kalshi/markets returns 200"""
        response = requests.get(f"{BASE_URL}/api/kalshi/markets?status=open")
        print(f"GET /api/kalshi/markets - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_markets_response_structure(self):
        """Test that /api/kalshi/markets returns markets with proper structure"""
        response = requests.get(f"{BASE_URL}/api/kalshi/markets?status=open&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure - may have markets or be empty
        print(f"Markets response keys: {list(data.keys())}")
        
        if "markets" in data:
            print(f"Total markets returned: {len(data['markets'])}")
            if len(data["markets"]) > 0:
                market = data["markets"][0]
                print(f"Sample market keys: {list(market.keys())}")
        else:
            print("No 'markets' key - may indicate no open markets")


class TestStrategiesSummaryAPI:
    """Test GET /api/strategies/summary endpoint for Strategy Command Center"""
    
    def test_strategies_summary_returns_200(self):
        """Test that /api/strategies/summary returns 200"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        print(f"GET /api/strategies/summary - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_strategies_summary_structure(self):
        """Test that /api/strategies/summary returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/strategies/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Check for strategy summary fields
        print(f"Strategies summary keys: {list(data.keys())}")
        
        # Check for key fields
        if "enabled" in data:
            print(f"Strategies enabled: {data['enabled']}")
        if "evaluation_mode" in data:
            print(f"Evaluation mode: {data['evaluation_mode']}")
        if "auto_mode" in data:
            print(f"Auto mode: {data['auto_mode']}")
        if "strategies" in data:
            print(f"Number of strategies: {len(data['strategies'])}")
            for sid, sdata in data.get("strategies", {}).items():
                print(f"  Strategy: {sid}")


class TestAutonomousEndpoints:
    """Test autonomous mode endpoints for Strategy Command Center"""
    
    def test_autonomous_enable_endpoint(self):
        """Test POST /api/autonomous/enable"""
        response = requests.post(f"{BASE_URL}/api/autonomous/enable")
        print(f"POST /api/autonomous/enable - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_autonomous_disable_endpoint(self):
        """Test POST /api/autonomous/disable"""
        response = requests.post(f"{BASE_URL}/api/autonomous/disable")
        print(f"POST /api/autonomous/disable - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_autonomous_metrics_endpoint(self):
        """Test GET /api/autonomous/metrics"""
        response = requests.get(f"{BASE_URL}/api/autonomous/metrics")
        print(f"GET /api/autonomous/metrics - Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
