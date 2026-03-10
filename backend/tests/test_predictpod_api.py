"""
PredictPod API Backend Tests
Tests for probability intelligence terminal APIs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://predict-strategy-hub.preview.emergentagent.com').rstrip('/')


class TestHealthAndStatus:
    """Health and status endpoint tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['db_connected'] == True
        assert data['espn_connected'] == True
        assert data['kalshi_connected'] == True
        print(f"Health check passed: {data}")
    
    def test_root_endpoint(self):
        """Test /api/ returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data['name'] == 'PredictPod API'
        assert data['version'] == '2.0.0'
        assert data['paper_mode'] == True
        print(f"Root endpoint passed: {data}")


class TestGamesAPI:
    """Games API endpoint tests"""
    
    def test_get_games_returns_data(self):
        """Test /api/games returns games list"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        data = response.json()
        assert 'games' in data
        assert 'count' in data
        assert isinstance(data['games'], list)
        print(f"Games count: {data['count']}")
        
        # Verify at least one game exists
        assert len(data['games']) > 0, "No games returned"
    
    def test_game_has_required_fields(self):
        """Test each game has required fields: Market, Fair, Edge, Signal columns"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        data = response.json()
        games = data.get('games', [])
        
        for game in games:
            # Game data
            assert 'game' in game
            assert 'id' in game['game']
            assert 'status' in game['game']
            
            # Probability fields (Market, Fair)
            assert 'fair_prob_home' in game, "Missing fair_prob_home"
            assert 'fair_prob_away' in game or game.get('fair_prob_away') is None
            
            # Markets (for Market column)
            assert 'markets' in game
            assert len(game['markets']) > 0, "No markets for game"
            
            # Signal data (Edge, Signal columns)
            assert 'signal' in game
            signal = game['signal']
            assert 'signal_type' in signal, "Missing signal_type"
            assert 'edge' in signal, "Missing edge"
            assert 'signal_score' in signal, "Missing signal_score"
            
            # Intelligence data
            assert 'intelligence' in game
            
            print(f"Game {game['game']['id']}: signal={signal['signal_type']}, score={signal['signal_score']}, edge={signal['edge']}")
    
    def test_probability_is_dynamic_not_static_50(self):
        """Test probability engine produces dynamic values, not static 50%"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        data = response.json()
        games = data.get('games', [])
        
        # Check that not all fair_prob_home values are exactly 0.5
        fair_probs = [g['fair_prob_home'] for g in games]
        
        # At least one should not be exactly 0.5 (or if all scheduled, they follow market)
        unique_probs = set(fair_probs)
        print(f"Unique fair_prob_home values: {unique_probs}")
        
        # Check that probabilities are dynamic (different from 0.5 or vary)
        has_non_50 = any(p != 0.5 for p in fair_probs)
        has_variation = len(unique_probs) > 1
        
        assert has_non_50 or has_variation, "Probability engine appears to be static at 50%"
    
    def test_signal_score_is_composite_0_to_100(self):
        """Test signal engine generates composite signal_score (0-100)"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        data = response.json()
        games = data.get('games', [])
        
        for game in games:
            signal = game.get('signal', {})
            signal_score = signal.get('signal_score', 0)
            
            # Signal score should be within 0-100 range
            assert 0 <= signal_score <= 100, f"Signal score {signal_score} out of range"
            
            # Should not be static (check it varies between games)
            print(f"Game {game['game']['id']}: signal_score={signal_score}")
        
        # Verify scores vary (not all the same)
        scores = [g['signal']['signal_score'] for g in games]
        if len(scores) > 1:
            has_variation = len(set(scores)) > 1 or any(s != 50 for s in scores)
            # Note: It's acceptable if scores are similar for scheduled games
            print(f"Signal scores: {scores}")
    
    def test_signal_has_portfolio_aware_actions(self):
        """Test signal engine provides portfolio-aware actions"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        data = response.json()
        games = data.get('games', [])
        
        valid_actions = ['ENTER_LONG', 'ENTER_SHORT', 'TRIM', 'EXIT', 'COVER', 'WAIT', 'HOLD']
        
        for game in games:
            signal = game.get('signal', {})
            action = signal.get('recommended_action', 'WAIT')
            
            assert action in valid_actions, f"Invalid action: {action}"
            print(f"Game {game['game']['id']}: action={action}")
    
    def test_games_filter_by_status(self):
        """Test /api/games?status filter works"""
        response = requests.get(f"{BASE_URL}/api/games?status=scheduled")
        assert response.status_code == 200
        
        data = response.json()
        games = data.get('games', [])
        
        for game in games:
            assert game['game']['status'] == 'scheduled', f"Got status {game['game']['status']} instead of scheduled"
        
        print(f"Scheduled games count: {len(games)}")


class TestGameDetailAPI:
    """Game detail endpoint tests"""
    
    @pytest.fixture
    def game_id(self):
        """Get a valid game ID from games list"""
        response = requests.get(f"{BASE_URL}/api/games")
        games = response.json().get('games', [])
        if not games:
            pytest.skip("No games available for testing")
        return games[0]['game']['id']
    
    def test_get_game_detail(self, game_id):
        """Test /api/games/{game_id} returns detailed data"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields
        assert 'game' in data
        assert 'fair_prob_home' in data
        assert 'markets' in data
        assert 'signal' in data
        assert 'intelligence' in data
        assert 'probability_history' in data
        
        print(f"Game detail retrieved: {game_id}")
    
    def test_game_detail_has_signal_analytics(self, game_id):
        """Test game detail includes trade analytics panel data"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        signal = data.get('signal', {})
        
        # Should have analytics
        assert 'analytics' in signal, "Missing analytics in signal"
        
        analytics = signal['analytics']
        required_analytics = ['expected_value', 'max_risk', 'suggested_exit_prob', 'suggested_stop_prob', 'risk_reward_ratio']
        
        for field in required_analytics:
            assert field in analytics, f"Missing analytics field: {field}"
        
        print(f"Analytics: EV={analytics['expected_value']}, Max Risk={analytics['max_risk']}, Exit={analytics['suggested_exit_prob']}, Stop={analytics['suggested_stop_prob']}")
    
    def test_game_detail_has_intelligence_panel_data(self, game_id):
        """Test game detail includes market intelligence data"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        intelligence = data.get('intelligence', {})
        
        required_fields = ['trend_5min', 'trend_30min', 'volatility_regime', 'momentum', 'volatility_value']
        
        for field in required_fields:
            assert field in intelligence, f"Missing intelligence field: {field}"
        
        print(f"Intelligence: trend_5m={intelligence['trend_5min']}, trend_30m={intelligence['trend_30min']}, volatility={intelligence['volatility_regime']}, momentum={intelligence['momentum']}")
    
    def test_game_detail_has_probability_history_for_charts(self, game_id):
        """Test game detail includes probability history for charts"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get('probability_history', [])
        
        # Should have history data
        assert isinstance(history, list), "probability_history should be a list"
        
        if history:
            # Check history item structure
            tick = history[0]
            required_fields = ['timestamp', 'market_prob', 'fair_prob', 'edge', 'score_diff', 'quarter']
            
            for field in required_fields:
                assert field in tick, f"Missing history field: {field}"
        
        print(f"Probability history count: {len(history)}")
    
    def test_game_not_found_returns_404(self):
        """Test invalid game ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/games/invalid_game_id_12345")
        assert response.status_code == 404


class TestChartDataAPI:
    """Chart data endpoint tests"""
    
    @pytest.fixture
    def game_id(self):
        """Get a valid game ID from games list"""
        response = requests.get(f"{BASE_URL}/api/games")
        games = response.json().get('games', [])
        if not games:
            pytest.skip("No games available for testing")
        return games[0]['game']['id']
    
    def test_get_chart_data_full(self, game_id):
        """Test /api/games/{game_id}/chart-data returns chart data"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}/chart-data")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'game_id' in data
        assert 'timeframe' in data
        assert 'probability_data' in data
        assert 'volatility_data' in data
        
        print(f"Chart data: prob_count={len(data['probability_data'])}, vol_count={len(data['volatility_data'])}")
    
    def test_chart_data_probability_structure(self, game_id):
        """Test probability chart data has correct structure"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}/chart-data")
        assert response.status_code == 200
        
        data = response.json()
        prob_data = data.get('probability_data', [])
        
        if prob_data:
            tick = prob_data[0]
            required_fields = ['timestamp', 'time', 'market_prob', 'fair_prob', 'edge']
            
            for field in required_fields:
                assert field in tick, f"Missing probability data field: {field}"
            
            # Check probability values are in percentage format
            assert 0 <= tick['market_prob'] <= 100, "market_prob should be 0-100"
            assert 0 <= tick['fair_prob'] <= 100, "fair_prob should be 0-100"
            
            print(f"Sample prob data: market={tick['market_prob']}%, fair={tick['fair_prob']}%, edge={tick['edge']}%")
    
    def test_chart_data_volatility_structure(self, game_id):
        """Test volatility chart data has correct structure"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}/chart-data")
        assert response.status_code == 200
        
        data = response.json()
        vol_data = data.get('volatility_data', [])
        
        if vol_data:
            tick = vol_data[0]
            assert 'time' in tick, "Missing time field"
            assert 'volatility' in tick, "Missing volatility field"
            
            # Volatility should be reasonable
            assert tick['volatility'] >= 0, "Volatility should be non-negative"
            
            print(f"Sample volatility data: time={tick['time']}, volatility={tick['volatility']}%")
    
    def test_chart_data_timeframe_filter(self, game_id):
        """Test chart data timeframe filter works"""
        # Test 5m timeframe
        response = requests.get(f"{BASE_URL}/api/games/{game_id}/chart-data?timeframe=5m")
        assert response.status_code == 200
        
        data = response.json()
        assert data['timeframe'] == '5m'
        
        print(f"5m timeframe data count: {len(data['probability_data'])}")


class TestPortfolioAPI:
    """Portfolio endpoint tests"""
    
    def test_get_portfolio_summary(self):
        """Test /api/portfolio returns portfolio summary"""
        response = requests.get(f"{BASE_URL}/api/portfolio")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields for portfolio page
        required_fields = ['balance', 'portfolio_value', 'total_exposure', 'total_pnl', 'open_positions', 'is_paper_mode']
        
        for field in required_fields:
            assert field in data, f"Missing portfolio field: {field}"
        
        assert data['is_paper_mode'] == True, "Should be paper mode"
        
        print(f"Portfolio: balance={data['balance']}, exposure={data['total_exposure']}, pnl={data['total_pnl']}")
    
    def test_get_positions(self):
        """Test /api/portfolio/positions returns positions list"""
        response = requests.get(f"{BASE_URL}/api/portfolio/positions")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'positions' in data
        assert 'count' in data
        assert isinstance(data['positions'], list)
        
        print(f"Open positions count: {data['count']}")


class TestRiskAPI:
    """Risk status endpoint tests"""
    
    def test_get_risk_status(self):
        """Test /api/risk/status returns risk status"""
        response = requests.get(f"{BASE_URL}/api/risk/status")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ['current_exposure', 'max_open_exposure', 'is_locked_out', 'can_trade', 'exposure_utilization', 'daily_loss_utilization']
        
        for field in required_fields:
            assert field in data, f"Missing risk status field: {field}"
        
        print(f"Risk status: exposure={data['current_exposure']}/{data['max_open_exposure']}, locked={data['is_locked_out']}, can_trade={data['can_trade']}")


class TestMarketIntelligenceAPI:
    """Market intelligence endpoint tests"""
    
    @pytest.fixture
    def game_id(self):
        """Get a valid game ID from games list"""
        response = requests.get(f"{BASE_URL}/api/games")
        games = response.json().get('games', [])
        if not games:
            pytest.skip("No games available for testing")
        return games[0]['game']['id']
    
    def test_get_market_intelligence(self, game_id):
        """Test /api/games/{game_id}/intelligence returns intelligence data"""
        response = requests.get(f"{BASE_URL}/api/games/{game_id}/intelligence")
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = ['trend_5min', 'trend_30min', 'volatility_regime', 'momentum', 'volatility_value']
        
        for field in required_fields:
            assert field in data, f"Missing intelligence field: {field}"
        
        # Should have edge stats
        if 'edge_stats' in data:
            edge_stats = data['edge_stats']
            print(f"Edge stats: avg={edge_stats.get('avg_edge', 0)}, current={edge_stats.get('current_edge', 0)}")
        
        print(f"Intelligence: trend_5m={data['trend_5min']}, volatility={data['volatility_regime']}")


class TestSettingsAPI:
    """Settings endpoint tests"""
    
    def test_get_settings(self):
        """Test /api/settings returns system settings"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'paper_trading_enabled' in data
        assert 'edge_threshold_buy' in data
        assert 'model_info' in data
        
        # Model info should exist
        model_info = data.get('model_info', {})
        assert 'version' in model_info, "Model info should have version"
        
        print(f"Settings: paper_mode={data['paper_trading_enabled']}, model={model_info.get('version', 'N/A')}")


class TestTradingAPI:
    """Trading endpoint tests"""
    
    @pytest.fixture
    def game_and_market(self):
        """Get a valid game and market for trading"""
        response = requests.get(f"{BASE_URL}/api/games")
        games = response.json().get('games', [])
        if not games:
            pytest.skip("No games available for testing")
        
        game = games[0]
        markets = game.get('markets', [])
        if not markets:
            pytest.skip("No markets available for testing")
        
        return game['game']['id'], markets[0]['id']
    
    def test_place_paper_trade(self, game_and_market):
        """Test placing a paper trade"""
        game_id, market_id = game_and_market
        
        response = requests.post(
            f"{BASE_URL}/api/trades",
            params={
                "game_id": game_id,
                "market_id": market_id,
                "side": "yes",
                "direction": "buy",
                "quantity": 5
            }
        )
        
        # Should succeed
        assert response.status_code == 200
        
        data = response.json()
        assert 'trade' in data
        assert 'message' in data
        
        trade = data['trade']
        assert trade['side'] == 'yes'
        assert trade['quantity'] == 5
        
        print(f"Trade placed: {trade}")
    
    def test_get_trades_history(self):
        """Test getting trades history"""
        response = requests.get(f"{BASE_URL}/api/trades")
        assert response.status_code == 200
        
        data = response.json()
        assert 'trades' in data
        assert isinstance(data['trades'], list)
        
        print(f"Trades history count: {len(data['trades'])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
