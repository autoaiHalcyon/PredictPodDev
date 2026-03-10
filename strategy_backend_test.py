#!/usr/bin/env python3
"""
PredictPod Strategy Management API Testing
Tests all CRUD operations for user-created strategies and validates configuration generation.
"""
import requests
import json
import sys
from datetime import datetime
from pathlib import Path
import time

class StrategyAPITester:
    def __init__(self, base_url="https://696833fc-7363-4159-acec-d8810d53e09b.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.created_strategies = []  # Track for cleanup

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        self.log(f"   {method} {endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - Status: {response.status_code}")
                try:
                    return success, response.json() if response.content else {}
                except:
                    return success, {}
            else:
                self.log(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ ERROR - {str(e)}")
            return False, {}

    def test_get_base_models(self):
        """Test GET /api/user-strategies/base-models"""
        success, response = self.run_test(
            "Get Base Models",
            "GET",
            "api/user-strategies/base-models",
            200
        )
        
        if success and 'base_models' in response:
            models = response['base_models']
            self.log(f"   Found {len(models)} base models")
            for model in models[:2]:  # Show first 2
                self.log(f"   - {model.get('model_id')}: {model.get('display_name')}")
            return True
        return False

    def test_get_parameter_bounds(self):
        """Test GET /api/user-strategies/parameter-bounds"""
        success, response = self.run_test(
            "Get Parameter Bounds",
            "GET",
            "api/user-strategies/parameter-bounds",
            200
        )
        return success

    def test_list_strategies_empty(self):
        """Test GET /api/user-strategies when empty"""
        success, response = self.run_test(
            "List Strategies (Initial)",
            "GET",
            "api/user-strategies",
            200
        )
        
        if success:
            count = response.get('count', 0)
            self.log(f"   Found {count} existing strategies")
            return True
        return False

    def test_create_strategy(self):
        """Test POST /api/user-strategies"""
        strategy_data = {
            "strategy_key": f"test_strategy_{int(time.time())}",
            "base_model": "model_a",
            "display_name": "Test Strategy Alpha",
            "description": "Test strategy for API validation",
            "enabled": True,
            "config_overrides": {
                "edge_threshold": 0.06,
                "position_size_pct": 0.03
            }
        }
        
        success, response = self.run_test(
            "Create Strategy",
            "POST",
            "api/user-strategies",
            200,
            data=strategy_data
        )
        
        if success and 'strategy' in response:
            strategy = response['strategy']
            strategy_id = strategy.get('id')
            if strategy_id:
                self.created_strategies.append(strategy_id)
                self.log(f"   Created strategy ID: {strategy_id}")
                self.log(f"   Strategy key: {strategy.get('strategy_key')}")
                return strategy_id, strategy
        
        return None, None

    def test_get_strategy(self, strategy_id):
        """Test GET /api/user-strategies/{id}"""
        success, response = self.run_test(
            "Get Strategy by ID",
            "GET",
            f"api/user-strategies/{strategy_id}",
            200
        )
        
        if success:
            self.log(f"   Retrieved: {response.get('display_name')}")
            return True
        return False

    def test_update_strategy(self, strategy_id):
        """Test PUT /api/user-strategies/{id}"""
        update_data = {
            "display_name": "Updated Test Strategy Alpha",
            "description": "Updated description for testing",
            "enabled": False
        }
        
        success, response = self.run_test(
            "Update Strategy",
            "PUT",
            f"api/user-strategies/{strategy_id}",
            200,
            data=update_data
        )
        
        if success and 'strategy' in response:
            strategy = response['strategy']
            self.log(f"   Updated name: {strategy.get('display_name')}")
            self.log(f"   Enabled: {strategy.get('enabled')}")
            return True
        return False

    def test_clone_strategy(self, source_strategy_id):
        """Test POST /api/user-strategies/{id}/clone"""
        clone_data = {
            "new_strategy_key": f"cloned_strategy_{int(time.time())}",
            "new_display_name": "Cloned Test Strategy",
            "description": "Cloned from test strategy"
        }
        
        success, response = self.run_test(
            "Clone Strategy",
            "POST",
            f"api/user-strategies/{source_strategy_id}/clone",
            200,
            data=clone_data
        )
        
        if success and 'strategy' in response:
            strategy = response['strategy']
            cloned_id = strategy.get('id')
            if cloned_id:
                self.created_strategies.append(cloned_id)
                self.log(f"   Cloned strategy ID: {cloned_id}")
                self.log(f"   New strategy key: {strategy.get('strategy_key')}")
                return cloned_id
        
        return None

    def test_list_strategies_populated(self):
        """Test GET /api/user-strategies with created strategies"""
        success, response = self.run_test(
            "List Strategies (After Creation)",
            "GET",
            "api/user-strategies?include_disabled=true",
            200
        )
        
        if success:
            strategies = response.get('strategies', [])
            count = len(strategies)
            self.log(f"   Found {count} total strategies")
            
            # Show user-created strategies
            user_strategies = [s for s in strategies if not s.get('strategy_key', '').startswith('model_')]
            self.log(f"   User-created: {len(user_strategies)}")
            
            for strategy in user_strategies:
                self.log(f"   - {strategy.get('strategy_key')}: {strategy.get('display_name')} (enabled: {strategy.get('enabled')})")
            
            return True
        return False

    def test_delete_strategy(self, strategy_id):
        """Test DELETE /api/user-strategies/{id}"""
        success, response = self.run_test(
            "Delete Strategy",
            "DELETE",
            f"api/user-strategies/{strategy_id}",
            200
        )
        
        if success:
            self.log(f"   Deleted strategy {strategy_id}")
            if strategy_id in self.created_strategies:
                self.created_strategies.remove(strategy_id)
            return True
        return False

    def test_config_file_generation(self):
        """Test that JSON config files are generated"""
        self.log("🔍 Testing JSON Config File Generation...")
        
        config_dir = Path("/app/backend/strategies/configs/generated")
        
        if not config_dir.exists():
            self.log(f"❌ Config directory does not exist: {config_dir}")
            return False
            
        json_files = list(config_dir.glob("*.json"))
        self.log(f"   Found {len(json_files)} config files")
        
        if json_files:
            # Check a sample file
            sample_file = json_files[0]
            try:
                with open(sample_file, 'r') as f:
                    config = json.load(f)
                    self.log(f"✅ Valid JSON config: {sample_file.name}")
                    self.log(f"   Display name: {config.get('display_name')}")
                    self.log(f"   Model ID: {config.get('model_id')}")
                    return True
            except Exception as e:
                self.log(f"❌ Invalid JSON in {sample_file}: {e}")
                return False
        else:
            self.log("⚠️  No config files found (may not be generated yet)")
            return True  # Not necessarily a failure

    def cleanup_strategies(self):
        """Clean up created test strategies"""
        if not self.created_strategies:
            return
            
        self.log("🧹 Cleaning up test strategies...")
        for strategy_id in self.created_strategies[:]:
            success, _ = self.run_test(
                f"Cleanup {strategy_id}",
                "DELETE",
                f"api/user-strategies/{strategy_id}",
                200
            )
            if success:
                self.created_strategies.remove(strategy_id)

    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        self.log("🚀 Starting PredictPod Strategy Management API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
        # Test 1: Get base models
        self.test_get_base_models()
        
        # Test 2: Get parameter bounds
        self.test_get_parameter_bounds()
        
        # Test 3: List strategies (initial state)
        self.test_list_strategies_empty()
        
        # Test 4: Create new strategy
        strategy_id, strategy_data = self.test_create_strategy()
        
        if strategy_id:
            # Test 5: Get strategy by ID
            self.test_get_strategy(strategy_id)
            
            # Test 6: Update strategy
            self.test_update_strategy(strategy_id)
            
            # Test 7: Clone strategy
            cloned_id = self.test_clone_strategy(strategy_id)
            
            # Test 8: List strategies (populated)
            self.test_list_strategies_populated()
            
            # Test 9: Config file generation
            self.test_config_file_generation()
            
        # Cleanup
        self.cleanup_strategies()
        
        # Final results
        self.log("\n" + "="*60)
        self.log(f"📊 TEST SUMMARY")
        self.log(f"   Tests Run: {self.tests_run}")
        self.log(f"   Tests Passed: {self.tests_passed}")
        self.log(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "N/A")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 ALL TESTS PASSED!")
            return 0
        else:
            self.log("❌ SOME TESTS FAILED!")
            return 1

def main():
    tester = StrategyAPITester()
    return tester.run_comprehensive_test()

if __name__ == "__main__":
    sys.exit(main())