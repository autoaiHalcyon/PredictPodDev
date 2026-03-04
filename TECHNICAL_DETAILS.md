# Technical Implementation Details

## Backend Changes

### New HTTP Endpoint
**File**: `backend/server.py` (Added at line ~1569)

```python
@api_router.post("/rules/{strategy_id}/update")
async def update_strategy_rules(strategy_id: str, league: str = "BASE", 
                                config: Dict = None, change_summary: str = ""):
    """Update rules for a strategy and save new version."""
```

**Request Format**:
```json
{
  "config": {
    "entry_rules": {
      "min_edge_threshold": 0.02,
      "min_signal_score": 50,
      "min_persistence_ticks": 2,
      "cooldown_seconds": 120,
      "max_entries_per_game": 3
    },
    "exit_rules": {
      "profit_target_pct": 0.12,
      "stop_loss_pct": 0.08,
      "edge_compression_exit_threshold": 0.015,
      "time_based_exit_seconds": 480,
      "trailing_stop_pct": 0.04
    },
    "filters": {
      "max_spread_pct": 0.04,
      "min_liquidity_contracts": 75,
      "allowed_leagues": ["NBA", "NCAA_M"],
      "volatility_regime_allowed": ["low", "medium", "high"]
    },
    "risk_limits": {
      "max_daily_loss_pct": 0.03,
      "max_exposure_pct": 0.12,
      "max_trades_per_hour": 15,
      "max_trades_per_day": 60
    },
    "position_sizing": {
      "base_size_pct": 0.025,
      "max_position_pct": 0.06,
      "kelly_fraction": 0.25
    },
    "circuit_breakers": {
      "pause_on_consecutive_losses": 4,
      "pause_duration_seconds": 300,
      "pause_on_drawdown_pct": 0.04
    }
  },
  "change_summary": "Tightened risk controls and increased edge threshold"
}
```

**Response**:
```json
{
  "success": true,
  "new_version_id": "MODEL_A_NBA_v0023",
  "version_number": 23,
  "message": "Rules updated successfully"
}
```

**Database Operations**:
- Creates new ConfigVersion in MongoDB
- Calculates diff from previous version
- Marks new version as active
- Automatically reloads strategies

---

## Frontend Architecture

### 1. DailyResults Component
**File**: `frontend/src/pages/DailyResults.js`

**State Management**:
```javascript
- dailyReport: Daily performance summary
- rulesData: Rules for each strategy
- trades: Today's trade execution list
- loading: Loading state
- date: Selected date for viewing
- error: Error messages
```

**Key Components**:
- `DailyStatsCard`: Summary card per strategy
- `RulesEditor`: Inline rule parameter editor
- `TradeExecutionSummary`: Table of daily trades

**Data Flow**:
```
useEffect (on mount)
  ↓
fetch /api/strategies/report/daily
  ↓
fetch /api/rules/{strategy_id} × 3
  ↓
fetch /api/trades?limit=100
  ↓
Filter today's trades
  ↓
Render components
```

### 2. RulesEditor Component (Embedded in DailyStatsCard)
**Features**:
- Nested object value updates using dot notation
- Real-time validation
- Change tracking with summary
- Loading state during save
- Error handling with user feedback

**Editable Parameters**:
```javascript
const editableParams = [
  "entry_rules.min_edge_threshold",
  "entry_rules.min_signal_score",
  "entry_rules.min_persistence_ticks",
  "exit_rules.profit_target_pct",
  "exit_rules.stop_loss_pct",
  "filters.max_spread_pct"
];
```

### 3. TradesCenter Pagination
**File**: `frontend/src/pages/TradesCenter.js`

**New State Variables**:
```javascript
const [currentPage, setCurrentPage] = useState(1);
const [pageSize, setPageSize] = useState(25);
```

**Pagination Logic**:
```javascript
const totalPages = Math.ceil(filtered.length / pageSize);
const startIdx = (currentPage - 1) * pageSize;
const endIdx = startIdx + pageSize;
const paginatedTrades = filtered.slice(startIdx, endIdx);

// Reset to page 1 when filters change
useEffect(() => {
  setCurrentPage(1);
}, [typeFilter, statusFilter, sideFilter, search, dateRange]);
```

**UI Elements**:
- Page size selector (10/25/50/100)
- Previous/Next buttons
- Direct page number selection
- Current page indicator

---

## Database Schema

### ConfigVersion (MongoDB)
```javascript
{
  _id: ObjectId,
  id: String,           // UUID
  model_id: String,     // model_a_disciplined, model_b_high_frequency, model_c_institutional
  league: String,       // BASE, NBA, NCAA_M, NCAA_W
  version_number: Int,  // 1, 2, 3, ...
  version_id: String,   // MODEL_A_NBA_v0023
  
  config: {             // Full configuration object
    entry_rules: {...},
    exit_rules: {...},
    filters: {...},
    risk_limits: {...},
    position_sizing: {...},
    circuit_breakers: {...}
  },
  
  created_at: DateTime,
  applied_at: DateTime,
  applied_by: String,   // MANUAL, AUTO_TUNER, ROLLBACK, INITIAL
  
  diff_from_previous: [
    {
      parameter: String,
      old_value: Any,
      new_value: Any,
      league: String
    }
  ],
  
  change_summary: String,
  is_active: Boolean,
  is_proposed: Boolean,
  
  tuner_score: Float,
  tuner_metrics: {...}
}
```

---

## API Integration

### Fetch & Update Pattern
```javascript
// Read current rules
const rulesRes = await fetch(
  `${API_BASE}/api/rules/${strategyId}?league=BASE`
);
const rules = await rulesRes.json();

// Update rules
const saveRes = await fetch(
  `${API_BASE}/api/rules/${strategyId}/update?league=BASE`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      config: updatedConfig,
      change_summary: "User-provided summary"
    })
  }
);

const result = await saveRes.json();
// result.new_version_id = "MODEL_A_NBA_v0024"
```

---

## Performance Considerations

### TradesCenter Pagination
- **Trades per page**: Configurable 10-100
- **Filter strategy**: Client-side (O(n) filtering + pagination)
- **Sort strategy**: In-memory array sort
- **Memory usage**: ~500KB for 500 trades in memory

### DailyResults
- **API calls**: 1 report + 3 rules + 1 trades = 5 concurrent fetches
- **Data refresh**: On component mount and manual refresh
- **Caching**: None (fresh data each load)

---

## Error Handling

### RulesEditor
```javascript
try {
  const res = await fetch(`${API_BASE}/api/rules/${strategyId}/update...`);
  if (!res.ok) throw new Error("Failed to save");
  alert("Rules saved successfully!");
  onSave(); // Trigger parent reload
} catch (err) {
  console.error("Error:", err);
  alert("Error saving rules");
} finally {
  setSaving(false);
}
```

### DailyResults
```javascript
try {
  // Parallel fetches
  const [reportRes, positionsRes] = await Promise.all([
    fetch(`${API_BASE}/api/strategies/report/daily...`),
    fetch(`${API_BASE}/api/strategies/positions/by_game`)
  ]);
  
  if (reportRes.ok) {
    // Process report
  }
  setError(null);
} catch (err) {
  setError(err.message); // Display to user
}
```

---

## Testing Endpoints

### cURL Examples

**Get daily report**:
```bash
curl http://localhost:8000/api/strategies/report/daily?date=2026-02-20
```

**Get rules**:
```bash
curl http://localhost:8000/api/rules/model_a_disciplined?league=BASE
```

**Update rules**:
```bash
curl -X POST http://localhost:8000/api/rules/model_a_disciplined/update?league=BASE \
  -H "Content-Type: application/json" \
  -d '{
    "config": { "entry_rules": { "min_edge_threshold": 0.03 } },
    "change_summary": "Tested increase"
  }'
```

---

## File Structure Summary

```
frontend/
  src/
    pages/
      DailyResults.js        ⭐ NEW - Daily results & rules editor
      TradesCenter.js        ✏️ MODIFIED - Added pagination
    components/
      TopNavbar.js           ✏️ MODIFIED - Added Daily Results link
    App.js                   ✏️ MODIFIED - Added route

backend/
  server.py                  ✏️ MODIFIED - Added POST rules endpoint
  services/
    config_version_service.py  (Used by new endpoint)
  repositories/
    config_version_repository.py (Database operations)

docs/
  DAILY_RESULTS_GUIDE.md     ⭐ NEW - User guide
  QUICK_START.md             ⭐ NEW - Quick reference
```

---

## Next Steps for Enhancement

1. **Add Graph Visualization**
   - Port daily P&L over time
   - Win rate trend
   - Rule parameter impact analysis

2. **A/B Testing Framework**
   - Run two rule versions in parallel
   - Compare performance
   - Auto-select winner

3. **Rule Suggestions**
   - ML-based parameter recommendations
   - Backtest alternative rules
   - Show expected win rate impact

4. **Export & Sharing**
   - JSON export of rule configs
   - Email reports
   - Slack integration

---

Generated: 2026-02-20
