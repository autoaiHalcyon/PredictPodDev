# Model A/B/C Quick Reference - One Page

## 📋 ENTRY RULES

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Min Edge** | ≥ 5% | ≥ 3% | ≥ 7% |
| **Min Signal Score** | ≥ 60 | ≥ 45 | ≥ 75 |
| **Persistence** | 3 ticks | 2 ticks | 4 ticks |
| **Cooldown** | 180s | 60s | 300s |
| **Max Entries/Game** | 3 | 8 | 2 |
| **Momentum Req** | ✅ YES | ❌ NO | ✅ YES |
| **Risk Tier** | LOW | LOW/MED | LOW |

## 💰 EXIT RULES

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Profit Target** | 15% | 8% | 20% |
| **Stop Loss** | 10% | 6% | 8% |
| **Trailing Stop** | 5% | 3% | 4% |
| **Time Exit** | 600s | 300s | 900s |
| **Edge Exit** | 2% compress | 1% compress | 3% compress |
| **Trim Rule** | 50% @ 10% | 60% @ 5% | 70% @ 7% |

## 📊 POSITION SIZING

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Base Size** | 2% capital | 1.5% capital | 1% capital |
| **Max Position** | 5% capital | 4% capital | 3% capital |
| **Kelly Fraction** | 25% | 20% | 15% |
| **Edge Scaling** | 2x | 1.5x | 1.5x |

## ⚠️ RISK LIMITS

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Daily Loss Cap** | 5% | 8% | 3% |
| **Max Exposure** | 15% | 25% | 10% |
| **Trades/Hour** | 4 | 12 | 2 |
| **Trades/Day** | 20 | 60 | 10 |
| **Max Drawdown** | 10% | 15% | 6% |

## 🛑 CIRCUIT BREAKER

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Loss Threshold** | 3 losses | 5 losses | 2 losses |
| **Pause Duration** | 600s | 300s | 900s |
| **Resume Type** | Auto | Auto | **MANUAL** ⚠️ |

## 🎯 MARKET ELIGIBILITY

| Rule | Model A | Model B | Model C |
|------|---------|---------|---------|
| **Sports** | NBA/NCAA | Any | Any |
| **Min Progress** | 10% | 5% | 20% |
| **Max Progress** | 95% | 98% | 90% |
| **Max Spread** | 5% | 8% | 3% |
| **Min Liquidity** | 50 contracts | 30 contracts | 100 contracts |
| **Volatility** | LOW/MED | ANY | LOW only |

## 💡 MODEL PHILOSOPHIES

**Model A - Disciplined Edge Trader**
- Conservative, high-conviction trades
- Requires strong edge and momentum alignment
- Preferred by risk-averse traders
- Best for: High-quality setups, lower frequency

**Model B - High Frequency Hunter**
- Fast entries, frequent scalping
- Lower edge threshold, quick exits
- Preferred by active traders
- Best for: Volume trading, quick profits

**Model C - Institutional Risk-First**
- Premium signal quality only
- Very selective, high bar to entry
- Strict risk management
- Best for: Institutional managers, capital preservation

## ✅ FRONTEND STATUS

| Component | Status | Details |
|-----------|--------|---------|
| Trades Page | ✅ | Shows Strategy column (A/B/C) + explanations |
| Strategy Tab | ✅ | Displays all 3 model rules |
| Game Details | ✅ | Only A/B/C strategies shown |
| Portfolio | ✅ | Real-time 2-second updates |
| Navigation | ✅ | Daily Results removed |

## ⏳ BACKEND STATUS

| Component | Status | Details |
|-----------|--------|---------|
| Trade Validation | ⏳ | Must reject non-A/B/C trades |
| Position Sizing | ⏳ | Must enforce model's Kelly % |
| Circuit Breaker | ⏳ | Model C needs MANUAL RESET |
| API Responses | ⏳ | Must return strategy + reasons |
| Daily Caps | ⏳ | Must enforce loss limits |

## 🔧 FILES TO MODIFY (Backend)

1. `backend/routes/trades.py` - Add validation logic
2. `backend/services/kalshi_ingestor_v2.py` - Trade execution
3. `backend/services/auto_tuner_service.py` - Circuit breakers
4. `backend/services/capital_preview_engine.py` - Position sizing
5. `backend/models/signal.py` - Add model metadata

## 🧪 TEST CASES (Backend)

```
✓ Place Model A trade: Edge=6%, Signal=65 → Should execute
✗ Place Model A trade: Edge=4%, Signal=65 → Should reject (edge too low)
✓ Place Model B trade: Edge=3.5%, Signal=50 → Should execute
✗ Place Model C trade: Edge=6%, Signal=80 → Should reject (edge too low)
✓ Model A after 3 losses → Paused 600s
✓ Model B after 5 losses → Paused 300s
✓ Model C after 2 losses → Paused 900s (MANUAL RESET)
```

## 📞 QUICK DECISION TREE

**User has Edge = 4.5%, Signal = 65**
1. Model A: Edge 4.5% < 5% ❌
2. Model B: Edge 4.5% ≥ 3% ✅ AND Signal 65 ≥ 45 ✅
3. Model C: Edge 4.5% < 7% ❌
→ **RESULT: Model B accepted**

**User has Edge = 8%, Signal = 70**
1. Model A: Edge 8% ≥ 5% ✅ AND Signal 70 ≥ 60 ✅ (if momentum=YES)
2. Model B: Edge 8% ≥ 3% ✅ AND Signal 70 ≥ 45 ✅
3. Model C: Edge 8% ≥ 7% ✅ AND Signal 70 < 75 ❌
→ **RESULT: Prefer Model A (stricter) if momentum aligned, else Model B**

**User has Edge = 7.5%, Signal = 80**
1. Model A: Edge 7.5% ≥ 5% ✅ AND Signal 80 ≥ 60 ✅ → **MATCH**
2. Model B: Edge 7.5% ≥ 3% ✅ AND Signal 80 ≥ 45 ✅ → **MATCH**
3. Model C: Edge 7.5% ≥ 7% ✅ AND Signal 80 ≥ 75 ✅ → **MATCH**
→ **RESULT: Could use any - pick based on risk preference**
   - Conservative → Model A (5% daily cap)
   - Aggressive → Model B (8% daily cap)
   - Premium → Model C (3% daily cap, MANUAL reset)

---

**Use This As A Reference For All Model A/B/C Decisions**
