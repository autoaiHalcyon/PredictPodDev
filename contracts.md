# PredictPod - API Contracts & Integration Guide

## Overview
PredictPod is a **Probability Intelligence Terminal** for prediction markets, starting with NBA games on Kalshi.

**Current Status:** MVP Complete with Paper Trading

---

## ARCHITECTURE

### Tech Stack
- **Frontend:** React + Tailwind CSS (Terminal-style dark UI)
- **Backend:** FastAPI + Python
- **Database:** MongoDB (designed for PostgreSQL migration)
- **Real-time:** WebSocket for live updates

### Core Components
1. **ESPN Adapter** - Live NBA game data (scores, quarter, time)
2. **Mock Kalshi Adapter** - Simulated market prices and trading
3. **Probability Engine** - Calibrated logistic model for win probability
4. **Signal Engine** - Edge detection and trading signals
5. **Trade Engine** - Paper trading execution with risk checks
6. **Portfolio Service** - Position tracking and P&L

---

## HOW TO INTEGRATE REAL KALSHI API

### Step 1: Add API Keys to Backend Environment

Edit `/app/backend/.env`:

```env
KALSHI_API_KEY=your_kalshi_api_key
KALSHI_PRIVATE_KEY=your_kalshi_private_key
KALSHI_DEMO_MODE=false  # Set to false for production
KALSHI_BASE_URL=https://trading-api.kalshi.com/v1  # Production URL
```

### Step 2: Obtain Kalshi API Keys

1. Create account at https://kalshi.com
2. Complete KYC verification
3. Go to Settings → API Keys
4. Generate new API key pair
5. Save both public key and private key

### Step 3: Implement Real Kalshi Adapter

Create `/app/backend/adapters/kalshi/real_adapter.py`:

```python
"""
Real Kalshi Adapter - Replace MockKalshiAdapter
Uses Kalshi's REST API for market data and trading.
"""
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
# ... implement RSA-PSS signing as per Kalshi docs
```

### Step 4: Switch Adapter in server.py

```python
# Change from:
kalshi_adapter = MockKalshiAdapter(initial_balance=10000.0)

# To:
from adapters.kalshi import RealKalshiAdapter
kalshi_adapter = RealKalshiAdapter(
    api_key=settings.kalshi_api_key,
    private_key=settings.kalshi_private_key
)
```

---

## API ENDPOINTS

### Games
| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/games` | GET | Get all NBA games with probabilities |
| `GET /api/games/{game_id}` | GET | Get detailed game data |

### Markets
| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/markets/{market_id}` | GET | Get market with orderbook |

### Trading
| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/trades` | POST | Place a trade |
| `POST /api/trades/execute-signal` | POST | Execute based on signal |
| `POST /api/trades/flatten-all` | POST | Emergency close all |
| `GET /api/trades` | GET | Get trade history |

### Portfolio
| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/portfolio` | GET | Portfolio summary |
| `GET /api/portfolio/positions` | GET | Open positions |
| `GET /api/portfolio/performance` | GET | Performance metrics |

### Risk
| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/risk/status` | GET | Current risk utilization |
| `GET /api/risk/limits` | GET | Risk limits |
| `PUT /api/risk/limits` | PUT | Update risk limits |

---

## SIGNAL TYPES

| Signal | Edge | Action |
|--------|------|--------|
| STRONG_BUY | ≥ +5% | Buy YES aggressively |
| BUY | ≥ +3% | Buy YES |
| HOLD | -3% to +3% | No action |
| SELL | ≤ 0% | Buy NO or sell YES |
| STRONG_SELL | ≤ -5% | Buy NO aggressively |
| SELL_INTO_STRENGTH | Late game + large lead | Exit winning position |

---

## PROBABILITY MODEL

### Version 1: Calibrated Logistic Regression

**Inputs:**
- Score differential (home - away)
- Time remaining (seconds)
- Quarter

**Formula:**
```
time_weight = 0.5 + 0.5 * (elapsed / total_game_seconds)
effective_coef = 0.17 * time_weight
logit = score_diff * effective_coef
probability = 1 / (1 + exp(-logit))
```

**Notes:**
- Calibrated on historical NBA data patterns
- Late-game leads are weighted more heavily
- Lookup table for very late game scenarios (Q4 < 2 min)

---

## DATABASE SCHEMA

### Games Collection
```javascript
{
  id: "nba_401810630",
  espn_id: "401810630",
  home_team: { id, name, abbreviation },
  away_team: { id, name, abbreviation },
  status: "live|scheduled|final",
  home_score: 110,
  away_score: 105,
  quarter: 4,
  time_remaining: "2:45",
  time_remaining_seconds: 165
}
```

### Markets Collection
```javascript
{
  id: "mock_nba_401810630_home",
  game_id: "nba_401810630",
  outcome: "home",
  yes_price: 0.72,
  yes_bid: 0.71,
  yes_ask: 0.73,
  volume: 15420
}
```

### Probability Ticks (Time-series)
```javascript
{
  game_id: "nba_401810630",
  timestamp: ISODate(),
  market_prob: 0.72,
  fair_prob: 0.78,
  edge: 0.06,
  score_diff: 5,
  quarter: 4,
  time_remaining_seconds: 165,
  signal: "STRONG_BUY"
}
```

### Trades Collection
```javascript
{
  id: "trade_uuid",
  game_id: "nba_401810630",
  market_id: "mock_nba_401810630_home",
  side: "yes",
  direction: "buy",
  quantity: 10,
  price: 0.72,
  status: "filled",
  is_paper: true,
  signal_type: "STRONG_BUY",
  edge_at_entry: 0.06
}
```

---

## RISK LIMITS

| Limit | Default | Description |
|-------|---------|-------------|
| max_position_size | $100 | Max per position |
| max_trade_size | $50 | Max per trade |
| max_open_exposure | $1000 | Total exposure |
| max_daily_loss | $500 | Before lockout |
| max_trades_per_day | 50 | Daily limit |
| max_trades_per_hour | 10 | Rate limit |

---

## FUTURE ROADMAP

1. **Real Kalshi Integration** - Replace mock adapter
2. **PostgreSQL Migration** - Time-series optimization
3. **ML Probability Model** - Train on collected tick data
4. **Additional Markets** - NFL, NCAA, Political
5. **Mobile App** - React Native
6. **Notifications** - Email/SMS alerts for signals
