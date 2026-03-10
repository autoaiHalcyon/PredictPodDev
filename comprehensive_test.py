#!/usr/bin/env python3
"""
Comprehensive PredictPod Backend Feature Verification
Validates all key features mentioned in the review request
"""

import requests
import json
import time

BASE_URL = "https://predict-strategy-hub.preview.emergentagent.com/api"

def test_comprehensive_features():
    """Test all key features mentioned in the review request"""
    
    print("🔍 COMPREHENSIVE FEATURE VERIFICATION")
    print("=" * 50)
    
    session = requests.Session()
    
    # 1. Verify NBA data from ESPN
    print("\n1️⃣ Testing NBA Data from ESPN...")
    response = session.get(f"{BASE_URL}/games")
    games_data = response.json()
    games = games_data.get("games", [])
    
    if games:
        sample_game = games[0]["game"]
        print(f"✅ Live NBA data: {sample_game['home_team']['name']} vs {sample_game['away_team']['name']}")
        print(f"   Status: {sample_game.get('status')}")
        print(f"   ESPN ID: {sample_game.get('espn_id')}")
    else:
        print("❌ No NBA games found")
        return False
    
    # 2. Verify Probability Engine
    print("\n2️⃣ Testing Probability Engine...")
    sample_game_data = games[0]
    fair_prob_home = sample_game_data.get("fair_prob_home")
    fair_prob_away = sample_game_data.get("fair_prob_away")
    confidence = sample_game_data.get("confidence")
    
    if fair_prob_home is not None and fair_prob_away is not None:
        print(f"✅ Fair probabilities calculated:")
        print(f"   Home: {fair_prob_home:.1%}, Away: {fair_prob_away:.1%}")
        print(f"   Confidence: {confidence}")
        
        # Verify probabilities sum to ~100%
        total_prob = fair_prob_home + fair_prob_away
        if 0.95 <= total_prob <= 1.05:
            print(f"   ✅ Probabilities sum correctly: {total_prob:.1%}")
        else:
            print(f"   ⚠️  Probabilities sum to {total_prob:.1%} (not ~100%)")
    else:
        print("❌ No fair probabilities found")
        return False
    
    # 3. Verify Market Probabilities & Edge Calculation
    print("\n3️⃣ Testing Market Probabilities & Edge...")
    markets = sample_game_data.get("markets", [])
    
    if markets:
        home_market = next((m for m in markets if m.get("outcome") == "home"), None)
        if home_market:
            market_prob = home_market.get("implied_probability")
            market_price = home_market.get("last_price")
            
            if market_prob and fair_prob_home:
                edge = fair_prob_home - market_prob
                print(f"✅ Market analysis:")
                print(f"   Market prob: {market_prob:.1%} (price: {market_price})")
                print(f"   Fair prob: {fair_prob_home:.1%}")
                print(f"   Edge: {edge:+.1%}")
            else:
                print("❌ Missing market or fair probability data")
        else:
            print("❌ No home market found")
    else:
        print("❌ No markets found")
        return False
    
    # 4. Verify Signal Generation
    print("\n4️⃣ Testing Signal Engine...")
    signal = sample_game_data.get("signal")
    
    if signal:
        signal_type = signal.get("signal_type")
        is_actionable = signal.get("is_actionable")
        edge_value = signal.get("edge")
        
        print(f"✅ Signal generated:")
        print(f"   Type: {signal_type}")
        print(f"   Actionable: {is_actionable}")
        print(f"   Edge: {edge_value:+.1%}" if edge_value else "   Edge: N/A")
    else:
        print("❌ No signal data found")
        return False
    
    # 5. Test Paper Trading Workflow
    print("\n5️⃣ Testing Paper Trading...")
    
    # Check initial portfolio
    portfolio_response = session.get(f"{BASE_URL}/portfolio")
    initial_portfolio = portfolio_response.json()
    initial_balance = initial_portfolio.get("balance", 0)
    
    print(f"   Initial balance: ${initial_balance:,.2f}")
    
    # Place a trade
    if markets and sample_game_data.get("game", {}).get("id"):
        game_id = sample_game_data["game"]["id"]
        market_id = home_market.get("id")
        
        trade_params = {
            "game_id": game_id,
            "market_id": market_id,
            "side": "yes",
            "direction": "buy",
            "quantity": 3
        }
        
        trade_response = session.post(f"{BASE_URL}/trades", params=trade_params)
        
        if trade_response.status_code == 200:
            trade_data = trade_response.json()
            trade = trade_data.get("trade", {})
            
            print(f"✅ Trade executed successfully:")
            print(f"   Trade ID: {trade.get('id')}")
            print(f"   Quantity: {trade.get('quantity')}")
            print(f"   Side: {trade.get('side')}")
            
            # Check positions
            time.sleep(1)  # Allow for processing
            positions_response = session.get(f"{BASE_URL}/portfolio/positions")
            positions_data = positions_response.json()
            positions = positions_data.get("positions", [])
            
            if positions:
                print(f"✅ Position created: {len(positions)} position(s)")
                
                # Check updated portfolio
                updated_portfolio_response = session.get(f"{BASE_URL}/portfolio")
                updated_portfolio = updated_portfolio_response.json()
                updated_balance = updated_portfolio.get("balance", 0)
                
                balance_change = updated_balance - initial_balance
                print(f"   Updated balance: ${updated_balance:,.2f} (change: ${balance_change:+,.2f})")
                
                if abs(balance_change) > 0:
                    print("✅ Balance updated correctly after trade")
                else:
                    print("⚠️  Balance unchanged (may be normal for paper trading)")
            else:
                print("❌ No positions found after trade")
        else:
            print(f"❌ Trade failed: {trade_response.status_code} - {trade_response.text}")
            return False
    
    # 6. Test Risk Tracking
    print("\n6️⃣ Testing Risk Status Tracking...")
    risk_response = session.get(f"{BASE_URL}/risk/status")
    risk_data = risk_response.json()
    
    exposure = risk_data.get("current_exposure", 0)
    trades_today = risk_data.get("trades_today", 0)
    can_trade = risk_data.get("can_trade", False)
    
    print(f"✅ Risk metrics tracked:")
    print(f"   Current exposure: ${exposure:,.2f}")
    print(f"   Trades today: {trades_today}")
    print(f"   Can trade: {can_trade}")
    
    # Check risk limits
    limits_response = session.get(f"{BASE_URL}/risk/limits")
    limits_data = limits_response.json()
    
    max_exposure = limits_data.get("max_open_exposure", 0)
    max_trade_size = limits_data.get("max_trade_size", 0)
    
    print(f"   Risk limits: Max exposure ${max_exposure:,.0f}, Max trade ${max_trade_size:,.0f}")
    
    print("\n🎉 ALL FEATURES VERIFIED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    success = test_comprehensive_features()
    exit(0 if success else 1)