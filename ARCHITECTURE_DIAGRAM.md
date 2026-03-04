# Complete Model A/B/C Trading System Architecture

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND APPLICATION                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │   Game Details       │  │  Trades Center   │  │ Strategy Tab    │  │
│  │                      │  │                  │  │                 │  │
│  │ - Model A rules ✅   │  │ - Strategy col   │  │ - All 3 rules   │  │
│  │ - Model B rules ✅   │  │ - Entry explain  │  │ - Model A (em)  │  │
│  │ - Model C rules ✅   │  │ - Exit explain   │  │ - Model B (bl)  │  │
│  │                      │  │ - MODEL_RULES    │  │ - Model C (pu)  │  │
│  │ Only A/B/C allowed   │  │ - 50 per page    │  │                 │  │
│  │                      │  │ - Smart paginate │  │                 │  │
│  │ 🟩 Emerald (A)       │  │                  │  │                 │  │
│  │ 🟦 Blue (B)          │  │                  │  │                 │  │
│  │🟪 Purple (C)         │  │                  │  │                 │  │
│  └──────────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │   Portfolio          │  │   Navigation     │  │   All Games     │  │
│  │   (Real-time)        │  │                  │  │                 │  │
│  │                      │  │ - Terminal       │  │ - Game list     │  │
│  │ - 2s polling ⚡      │  │ - All Games      │  │ - Market data   │  │
│  │ - Live P&L           │  │ - Strategy Center│  │ - Edge display  │  │
│  │ - Exposure track     │  │ - Trades ✨      │  │                 │  │
│  │ - Model breakdown    │  │ - Portfolio      │  │                 │  │
│  │                      │  │ - Settings       │  │                 │  │
│  │                      │  │                  │  │                 │  │
│  │ (Daily Results ✂️)   │  │ (Daily Results ✂️) │                 │  │
│  └──────────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
              ⬇️ API Calls (Must Validate A/B/C)
┌─────────────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICES (⏳ IN PROGRESS)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              Trade Validation Engine (CRITICAL)                  │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │                                                                  │  │
│  │  Input: Signal(edge, signal_score, momentum, risk_tier)         │  │
│  │                                                                  │  │
│  │  ✓ Model A Check:  edge≥5% && signal≥60 && momentum && risk=L   │  │
│  │  ✓ Model B Check:  edge≥3% && signal≥45 && (risk=L or M)        │  │
│  │  ✓ Model C Check:  edge≥7% && signal≥75 && momentum && risk=L   │  │
│  │                                                                  │  │
│  │  IF matched model:     ACCEPT trade                             │  │
│  │  IF no model matched:  REJECT trade (400 error)                 │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │ Position Sizing    │  │ Circuit Breaker  │  │ Risk Limits     │   │
│  │                    │  │                  │  │                 │   │
│  │ Model A: 2% base   │  │ A: 3-loss→600s   │  │ A: 5% daily cap │   │
│  │   5% max, 25% Kelly│  │   auto-resume    │  │ B: 8% daily cap │   │
│  │                    │  │                  │  │ C: 3% daily cap │   │
│  │ Model B: 1.5% base │  │ B: 5-loss→300s   │  │                 │   │
│  │   4% max, 20% Kelly│  │   auto-resume    │  │ A: 4/hr, 20/day │   │
│  │                    │  │                  │  │ B: 12/hr, 60/day│   │
│  │ Model C: 1% base   │  │ C: 2-loss→900s   │  │ C: 2/hr, 10/day │   │
│  │   3% max, 15% Kelly│  │   MANUAL RESET⚠️ │  │                 │   │
│  └────────────────────┘  └──────────────────┘  └─────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │        API Response (Add to Trade Objects)                      │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │                                                                 │  │
│  │ {                                                               │  │
│  │   "id": "trade_123",                                            │  │
│  │   "strategy": "Model A",     ← REQUIRED for frontend display   │  │
│  │   "entry_signal_score": 72,  ← For explanation display         │  │
│  │   "entry_edge": 0.0625,      ← For explanation display         │  │
│  │   "entry_rules_satisfied": [                                   │  │
│  │     "edge_5pct",                                                │  │
│  │     "signal_60",                                                │  │
│  │     "momentum_yes",                                             │  │
│  │     "risk_low"                                                  │  │
│  │   ],                                                            │  │
│  │   "exit_reason": "profit_target_hit",  ← For exit explanation  │  │
│  │   "exit_rules_triggered": ["15pct_target"]                     │  │
│  │ }                                                               │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
              ⬇️ Database Persistence
┌─────────────────────────────────────────────────────────────────────────┐
│                          MONGODB                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ • trades collection (with strategy, entry_reason, exit_reason)         │
│ • circuit_breakers collection (loss counts per model)                  │
│ • portfolio collection (daily P&L, loss tracking)                      │
│ • signals collection (edge, signal_score, momentum scores)             │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Trade Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TRADE ENTRY LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────────┘

1. USER ACTION (Frontend)
   ├─ Opens Game Details
   ├─ Sees live signals + analytics
   └─ Clicks "Place Trade" button → Request sent to backend

2. SIGNAL GENERATION (Backend)
   ├─ Calculate edge (current_price vs fair_value)
   ├─ Calculate signal_score (momentum, trend, technicals)
   ├─ Determine momentum_aligned (yes/no)
   └─ Set risk_tier (low/medium/high)

3. MODEL VALIDATION (Backend - NEW LOGIC)
   ├─ Check Model A: edge≥5% && signal≥60 && momentum && risk=L
   ├─ Check Model B: edge≥3% && signal≥45 && (risk=L or M)
   ├─ Check Model C: edge≥7% && signal≥75 && momentum && risk=L
   │
   ├─ IF NO MATCH → Return 400 error "Trade must match Model A/B/C"
   └─ IF MATCH → Proceed with selected model

4. POSITION SIZING (Backend - Model-Specific)
   ├─ IF Model A selected → base = 2% * capital, max = 5%, Kelly = 25%
   ├─ IF Model B selected → base = 1.5% * capital, max = 4%, Kelly = 20%
   └─ IF Model C selected → base = 1% * capital, max = 3%, Kelly = 15%

5. RISK CHECKS (Backend - Before Execution)
   ├─ Check daily loss cap (A: 5%, B: 8%, C: 3%)
   ├─ Check max exposure (A: 15%, B: 25%, C: 10%)
   ├─ Check trades/hour limit (A: 4, B: 12, C: 2)
   ├─ Check trades/day limit (A: 20, B: 60, C: 10)
   ├─ Check circuit breaker status (manual for C!)
   │
   ├─ IF ANY limit exceeded → Return 400 error
   └─ IF ALL checks pass → Proceed

6. TRADE EXECUTION (Backend)
   ├─ Place order on Kalshi API/Paper Trading
   ├─ Record trade in database
   │  └─ strategy: "Model A" | "Model B" | "Model C"
   │  └─ entry_signal_score: 72
   │  └─ entry_edge: 0.0625
   │  └─ entry_rules_satisfied: [...]
   └─ Return 200 success to frontend

7. FRONTEND UPDATE
   ├─ Receives trade confirmation
   ├─ Shows on Trades page with strategy column
   ├─ Updates Portfolio in real-time (2s polling)
   └─ Display can show: "Model A: Edge 6.25% > 5% ✓, Signal 72 > 60 ✓"


┌─────────────────────────────────────────────────────────────────────────┐
│                          TRADE EXIT LIFECYCLE                           │
└─────────────────────────────────────────────────────────────────────────┘

1. CONTINUOUS MONITORING (Backend)
   ├─ Check profit level vs model's profit target
   ├─ Check loss level vs model's stop loss
   ├─ Check edge compression vs model's threshold
   ├─ Check time elapsed vs model's time exit
   └─ Check trailing stop level

2. EXIT TRIGGER (Backend)
   ├─ Model A: 15% profit target hit
   │  └─ exit_reason: "profit_target_hit"
   │
   ├─ Model B: 8% profit target hit
   │  └─ exit_reason: "profit_target_hit"
   │
   ├─ Model C: 20% profit target hit
   │  └─ exit_reason: "profit_target_hit"
   │
   ├─ ANY MODEL: Stop loss hit
   │  └─ exit_reason: "stop_loss_hit"

3. UPDATE DATABASE
   ├─ Record exit_price, exit_reason, P&L
   ├─ Update daily loss tracking
   └─ Check if circuit breaker triggered
      ├─ Model A: If 3 losses → Pause 600s, auto-resume
      ├─ Model B: If 5 losses → Pause 300s, auto-resume
      └─ Model C: If 2 losses → Pause 900s, MANUAL RESET NEEDED

4. FRONTEND UPDATE
   ├─ Shows trade in closed position
   ├─ Displays exit_reason in trade details
   ├─ Portfolio reflects P&L immediately (2s polling)
   └─ If Model C paused: Show "Model C PAUSED (manual reset needed)"
```

## 📊 Model Selection Decision Tree

```
                    ┌─────────────────────┐
                    │ Signal Received     │
                    │ •Edge, Signal, Risk │
                    │ •Momentum, League   │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴──────────┐
                 │ Check Model Criteria  │
                 └─────────────┬──────────┘
                               │
                ┌──────────────┬──────────────┐
                │              │              │
         ┌──────▼─────────┐  │  ┌──────▼──────────┐  │  ┌──────▼──────────┐
         │ Model A Check  │  │  │ Model B Check  │  │  │ Model C Check  │
         ├────────────────┤  │  ├────────────────┤  │  ├────────────────┤
         │ Edge ≥ 5% ?    │  │  │ Edge ≥ 3% ?    │  │  │ Edge ≥ 7% ?    │
         │ Score ≥ 60 ?   │  │  │ Score ≥ 45 ?   │  │  │ Score ≥ 75 ?   │
         │ Momentum ?     │  │  │ Risk L/M ?     │  │  │ Momentum ?     │
         │ Risk = LOW ?   │  │  │                │  │  │ Risk = LOW ?   │
         └──────┬─────────┘  │  └──────┬──────────┘  │  └──────┬──────────┘
                │            │         │            │         │
         ✓YES   │      ✓YES  │         │      ✓YES  │         │
              ╲ │        ╱   │    ╲    │        ╱   │    ╱    │
                ▼        ▼   │     ▼   │       ▼    │   ▼     ▼
             [MATCH] ──┐     │    [MATCH]──┐       │ [MATCH]──┐
                       │     │             │       │          │
                       └─────┼─────────────┼───────┼──────────┘
                             │
                    ┌────────▼────────┐
                    │ Select Model    │
                    │ (Prefer A > B>C)│
                    └────────┬────────┘
                             │
                    NO MATCH?│
                             │
                    ┌────────▼───────┐
                    │ ⚠️ WARNING      │
                    │ No Strategy    │
                    │ Matched        │
                    │ Reject Trade   │
                    └────────────────┘
```

## 🎯 Frontend Display Examples

### Example 1: Trades Page

```
┌─────────────────────────────────────────────────────────────────┐
│ Trades                                                    🔄 ⚙️  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ID      | Pair  | Side  | Qty | Price | Strategy | P&L   | ⋮  │
├─────────────────────────────────────────────────────────────────┤
│ 1001    | NBA1  | YES   | 5   | 52¢   | Model A  | +7.5% | ▼  │
│ 1002    | BBall | NO    | 8   | 48¢   | Model B  | +3.2% | ▼  │
│ 1003    | NFL   | YES   | 3   | 65¢   | Model C  | +12%  | ▼  │
│ 1004    | NBA2  | YES   | 4   | 45¢   | Model B  | -2.1% | ▼  │
│                                                                 │
├─ CLICK TO EXPAND MODEL B TRADE ►────────────────────────────────┤
│                                                                 │
│ Trade ID: 1002 | BBall | NO Side | 8 qty @ 48¢                │
│                                                                 │
│ 📊 ENTRY EXPLANATION                                           │
│ ├─ Model: Model B (High Frequency Hunter) 🟦                   │
│ ├─ Edge at entry: 3.8% (> 3% minimum ✓)                        │
│ ├─ Signal Score: 52 (> 45 minimum ✓)                           │
│ ├─ Risk Tier: MEDIUM (L/M allowed ✓)                           │
│ └─ Result: ALL CONDITIONS MET → Trade accepted ✅               │
│                                                                 │
│ 📈 EXIT EXPLANATION                                            │
│ ├─ Model: Model B                                              │
│ ├─ Exit Trigger: Profit target 8% hit                          │
│ ├─ Final Price: 51.8¢                                          │
│ ├─ Profit: +7.9% (target: 8%)                                  │
│ └─ Result: Position closed at profit target ✅                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Example 2: Game Details Page

```
┌─────────────────────────────────────────────────────────────────┐
│ NBA Game: BOS vs LAL | 45% Complete                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 📊 Market Data:  YES: 52¢ | NO: 48¢                            │
│ 📈 Probability:  YES: 52% | NO: 48%                            │
│ ⚡ Edge:         +6.2%                                          │
│ 🎯 Signal:       68 (strong)                                   │
│ 🔄 Momentum:     Aligned                                       │
│ ⚠️  Risk Tier:   LOW                                            │
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ ✅ STRATEGY MATCH                                         │  │
│ ├───────────────────────────────────────────────────────────┤  │
│ │                                                           │  │
│ │ Recommended Models:                                       │  │
│ │                                                           │  │
│ │ 🟩 Model A (Disciplined Edge Trader)                     │  │
│ │    ├─ Edge 6.2% ≥ 5% ✓                                   │  │
│ │    ├─ Signal 68 ≥ 60 ✓                                   │  │
│ │    ├─ Momentum aligned ✓                                 │  │
│ │    ├─ Risk LOW ✓                                         │  │
│ │    └─ STATUS: ✅ ELIGIBLE                                │  │
│ │                                                           │  │
│ │ 🟦 Model B (High Frequency Hunter)                       │  │
│ │    ├─ Edge 6.2% ≥ 3% ✓                                   │  │
│ │    ├─ Signal 68 ≥ 45 ✓                                   │  │
│ │    ├─ Risk LOW (L/M allowed) ✓                           │  │
│ │    └─ STATUS: ✅ ELIGIBLE                                │  │
│ │                                                           │  │
│ │ 🟪 Model C (Institutional Risk-First)                    │  │
│ │    ├─ Edge 6.2% < 7% ✗                                   │  │
│ │    └─ STATUS: ❌ NOT ELIGIBLE                            │  │
│ │                                                           │  │
│ │ 💡 Recommended: Model A (stricter criteria = lower risk)  │  │
│ │    Size: 2% × capital = $2,000                           │  │
│ │    Max P&L: $300 (15% target) / -$200 (10% stop)        │  │
│ │                                                           │  │
│ │ ┌─ [Place Trade] ─ [Clear] ────────────────────────────┐ │  │
│ │ │ Choose Model: [Modal A ▼]                          │ │  │
│ │ └──────────────────────────────────────────────────────┘ │  │
│ │                                                           │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Example 3: No Strategy Matched

```
┌─────────────────────────────────────────────────────────────────┐
│ NBA Game: BOS vs LAL | 45% Complete                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 📊 Market Data:  YES: 48¢ | NO: 52¢                            │
│ 📈 Probability:  YES: 48% | NO: 52%                            │
│ ⚡ Edge:         -2.1%                                          │
│ 🎯 Signal:       35 (low)                                      │
│ 🔄 Momentum:     Neutral                                       │
│ ⚠️  Risk Tier:   MEDIUM                                        │
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ ⚠️ NO STRATEGY MATCHED                                    │  │
│ ├───────────────────────────────────────────────────────────┤  │
│ │                                                           │  │
│ │ Current conditions do not satisfy any strategy rules.     │  │
│ │ Proceeding will execute a paper trade AT YOUR OWN RISK.  │  │
│ │                                                           │  │
│ │ Why no match?                                            │  │
│ │                                                           │  │
│ │ 🟩 Model A: Signal 35 < 60 ✗                             │  │
│ │ 🟦 Model B: Signal 35 < 45 ✗                             │  │
│ │ 🟪 Model C: Edge negative ✗                              │  │
│ │                                                           │  │
│ │ 💡 Recommendation: Wait for better signal development    │  │
│ │                                                           │  │
│ │ ┌─ [Place Trade Anyway] ─ [Cancel] ─────────────────────┐ │  │
│ │ │ ⚠️ Confirm: Place risky trade?                       │ │  │
│ │ └──────────────────────────────────────────────────────┘ │  │
│ │                                                           │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Status

**Frontend**: ✅ COMPLETE
- TradesCenter.js - No errors
- StrategyCommandCenter.js - No errors
- GameDetail.jsx - No errors
- Portfolio.jsx - No errors
- TopNavbar.js - No errors

**Backend**: ⏳ IN PROGRESS
- Trade validation needed
- Model selection needed
- Circuit breakers needed
- API responses need strategy metadata

---

*This architecture ensures all trades are Model A/B/C compliant with strict risk management.*
