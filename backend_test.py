#!/usr/bin/env python3
"""
PredictPod Backend API Test Suite
Tests all major endpoints of the Probability Intelligence Terminal
"""

import requests
import json
import sys
import time
from typing import Dict, Any, Optional, List

# Backend URL from frontend .env
BASE_URL = "https://predict-strategy-hub.preview.emergentagent.com/api"

class PredictPodAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.test_results = []
        self.game_data = None
        
    def log_result(self, test_name: str, success: bool, details: str = "", data: Any = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "data": data if data else {}
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        
    def make_request(self, method: str, endpoint: str, **kwargs) -> tuple[bool, Any, str]:
        """Make HTTP request and handle errors"""
        try:
            url = f"{self.base_url}{endpoint}"
            print(f"\n🔍 Testing {method} {url}")
            
            response = self.session.request(method, url, timeout=10, **kwargs)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code >= 400:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
            try:
                data = response.json()
                return True, data, "Success"
            except json.JSONDecodeError:
                return False, None, f"Invalid JSON response: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return False, None, "Connection failed - server may be down"
        except requests.exceptions.Timeout:
            return False, None, "Request timeout"
        except Exception as e:
            return False, None, f"Request failed: {str(e)}"
    
    def test_health_check(self):
        """Test 1: Health Check"""
        success, data, message = self.make_request("GET", "/health")
        
        if success and data:
            # Check required fields
            required_fields = ["status", "db_connected", "espn_connected", "kalshi_connected"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("Health Check", False, f"Missing fields: {missing_fields}", data)
            elif data.get("status") == "healthy":
                self.log_result("Health Check", True, "Service is healthy", data)
            else:
                self.log_result("Health Check", False, f"Status not healthy: {data.get('status')}", data)
        else:
            self.log_result("Health Check", False, message)
    
    def test_get_games(self):
        """Test 2: Get Games List"""
        success, data, message = self.make_request("GET", "/games")
        
        if success and data:
            games = data.get("games", [])
            count = data.get("count", 0)
            
            if count > 0 and len(games) > 0:
                # Store first game for later tests
                self.game_data = games[0]
                game_info = self.game_data.get("game", {})
                
                # Verify game structure
                required_fields = ["fair_prob_home", "fair_prob_away", "markets", "signal"]
                missing_fields = [field for field in required_fields if field not in self.game_data]
                
                if missing_fields:
                    self.log_result("Get Games", False, f"Missing fields in game: {missing_fields}", data)
                else:
                    markets = self.game_data.get("markets", [])
                    home_team = game_info.get("home_team", {}).get("name", "Unknown")
                    away_team = game_info.get("away_team", {}).get("name", "Unknown")
                    
                    self.log_result("Get Games", True, 
                        f"Found {count} games. Sample: {home_team} vs {away_team}, Markets: {len(markets)}", 
                        {"game_count": count, "sample_game_id": game_info.get("id")})
            else:
                self.log_result("Get Games", False, f"No games found. Count: {count}", data)
        else:
            self.log_result("Get Games", False, message)
    
    def test_get_single_game(self):
        """Test 3: Get Single Game Details"""
        if not self.game_data:
            self.log_result("Get Single Game", False, "No game data from previous test")
            return
            
        game_id = self.game_data.get("game", {}).get("id")
        if not game_id:
            self.log_result("Get Single Game", False, "No game ID available")
            return
            
        success, data, message = self.make_request("GET", f"/games/{game_id}")
        
        if success and data:
            # Verify detailed game structure
            required_fields = ["game", "fair_prob_home", "fair_prob_away", "markets", "probability_history", "positions"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("Get Single Game", False, f"Missing fields: {missing_fields}", data)
            else:
                prob_history_count = len(data.get("probability_history", []))
                positions_count = len(data.get("positions", []))
                
                self.log_result("Get Single Game", True, 
                    f"Game details loaded. History: {prob_history_count} ticks, Positions: {positions_count}", 
                    {"game_id": game_id})
        else:
            self.log_result("Get Single Game", False, message)
    
    def test_portfolio(self):
        """Test 4: Portfolio Summary"""
        success, data, message = self.make_request("GET", "/portfolio")
        
        if success and data:
            # Check for portfolio fields
            expected_fields = ["balance", "portfolio_value", "total_pnl"]
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                self.log_result("Portfolio", False, f"Missing portfolio fields: {missing_fields}", data)
            else:
                balance = data.get("balance", 0)
                portfolio_value = data.get("portfolio_value", 0)
                pnl = data.get("total_pnl", 0)
                
                self.log_result("Portfolio", True, 
                    f"Balance: ${balance:,.2f}, Portfolio Value: ${portfolio_value:,.2f}, P&L: ${pnl:,.2f}", 
                    data)
        else:
            self.log_result("Portfolio", False, message)
    
    def test_risk_status(self):
        """Test 5: Risk Status"""
        success, data, message = self.make_request("GET", "/risk/status")
        
        if success and data:
            # Check for actual risk fields from the API
            key_fields = ["current_exposure", "trades_today", "exposure_utilization", "can_trade"]
            present_fields = [field for field in key_fields if field in data]
            
            if len(present_fields) >= 2:
                exposure = data.get("current_exposure", "N/A")
                trades = data.get("trades_today", "N/A")
                utilization = data.get("exposure_utilization", "N/A")
                can_trade = data.get("can_trade", "N/A")
                
                self.log_result("Risk Status", True, 
                    f"Exposure: {exposure}, Daily Trades: {trades}, Utilization: {utilization}%, Can Trade: {can_trade}", 
                    data)
            else:
                self.log_result("Risk Status", False, f"Missing key risk fields. Got: {list(data.keys())}", data)
        else:
            self.log_result("Risk Status", False, message)
    
    def test_place_trade(self):
        """Test 6: Place Paper Trade"""
        if not self.game_data:
            self.log_result("Place Trade", False, "No game data available for trade")
            return
            
        game_id = self.game_data.get("game", {}).get("id")
        markets = self.game_data.get("markets", [])
        
        if not game_id or not markets:
            self.log_result("Place Trade", False, "Missing game_id or markets for trade")
            return
            
        # Find home market
        home_market = next((m for m in markets if m.get("outcome") == "home"), None)
        if not home_market:
            self.log_result("Place Trade", False, "No home market found")
            return
            
        market_id = home_market.get("id")
        if not market_id:
            self.log_result("Place Trade", False, "No market_id found")
            return
        
        # Place trade using query parameters
        params = {
            "game_id": game_id,
            "market_id": market_id,
            "side": "yes",
            "direction": "buy",
            "quantity": 5
        }
        
        success, data, message = self.make_request("POST", "/trades", params=params)
        
        if success and data:
            trade = data.get("trade", {})
            if trade:
                trade_id = trade.get("id", "Unknown")
                quantity = trade.get("quantity", 0)
                side = trade.get("side", "Unknown")
                
                self.log_result("Place Trade", True, 
                    f"Trade executed: ID={trade_id}, Qty={quantity}, Side={side}", 
                    {"trade_id": trade_id, "game_id": game_id, "market_id": market_id})
            else:
                self.log_result("Place Trade", False, "No trade data in response", data)
        else:
            self.log_result("Place Trade", False, message)
    
    def test_get_positions(self):
        """Test 7: Get Portfolio Positions"""
        success, data, message = self.make_request("GET", "/portfolio/positions")
        
        if success and data:
            positions = data.get("positions", [])
            count = data.get("count", 0)
            
            if count > 0:
                # Check first position structure
                first_pos = positions[0]
                expected_fields = ["game_id", "market_id", "quantity", "side"]
                present_fields = [field for field in expected_fields if field in first_pos]
                
                self.log_result("Get Positions", True, 
                    f"Found {count} positions. Fields present: {len(present_fields)}/{len(expected_fields)}", 
                    {"position_count": count, "sample_position": first_pos})
            else:
                self.log_result("Get Positions", True, "No positions found (normal for new account)", data)
        else:
            self.log_result("Get Positions", False, message)
    
    def test_risk_limits(self):
        """Test 8: Risk Limits"""
        success, data, message = self.make_request("GET", "/risk/limits")
        
        if success and data:
            # Check for risk limit fields
            expected_fields = ["max_position_size", "max_trade_size", "max_open_exposure"]
            present_fields = [field for field in expected_fields if field in data]
            
            if len(present_fields) > 0:
                max_pos = data.get("max_position_size", "N/A")
                max_trade = data.get("max_trade_size", "N/A")
                max_exposure = data.get("max_open_exposure", "N/A")
                
                self.log_result("Risk Limits", True, 
                    f"Max Position: {max_pos}, Max Trade: {max_trade}, Max Exposure: {max_exposure}", 
                    data)
            else:
                self.log_result("Risk Limits", False, f"No expected limit fields found. Got: {list(data.keys())}", data)
        else:
            self.log_result("Risk Limits", False, message)
    
    def run_all_tests(self):
        """Run all test cases"""
        print("=" * 60)
        print("🚀 PredictPod Backend API Test Suite")
        print("=" * 60)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Get Games", self.test_get_games),
            ("Get Single Game", self.test_get_single_game),
            ("Portfolio", self.test_portfolio),
            ("Risk Status", self.test_risk_status),
            ("Place Trade", self.test_place_trade),
            ("Get Positions", self.test_get_positions),
            ("Risk Limits", self.test_risk_limits),
        ]
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                test_func()
            except Exception as e:
                self.log_result(test_name, False, f"Test execution error: {str(e)}")
            time.sleep(0.5)  # Brief pause between tests
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"\n✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        
        if total - passed > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['details']}")
        
        print(f"\n🎯 Success Rate: {(passed/total)*100:.1f}%")
        
        return passed == total

if __name__ == "__main__":
    print(f"Testing backend at: {BASE_URL}")
    
    tester = PredictPodAPITester()
    all_passed = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)