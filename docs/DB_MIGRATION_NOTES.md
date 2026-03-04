# PredictPod Database Migration & Index Notes

**Version:** predictpod-v0.9-paper
**Date:** 2026-02-12

---

## Current Database

- **Database Name:** `test_database` (from `DB_NAME` in `.env`)
- **MongoDB Version:** 7.x
- **Total Collections:** 20

---

## Collections Overview

| Collection | Documents | Description |
|------------|-----------|-------------|
| kalshi_events | 1,629 | Ingested Kalshi basketball events |
| kalshi_markets | 27,829 | Ingested Kalshi basketball markets |
| probability_ticks | 26,542 | Probability engine tick history |
| position_reconciliations | 4,458 | Position sync records |
| trading_audit_log | 94 | Trade execution audit trail |
| live_orders | 80 | Active order tracking |
| markets | 34 | Local market cache |
| config_versions | 17 | Strategy config versioning |
| games | 17 | ESPN game data |
| autonomous_audit_log | 9 | Autonomous mode events |
| trades | 10 | Executed trades |
| kalshi_categories | 7 | Kalshi category cache |
| positions | 2 | Current positions |
| metrics_snapshots | 1+ | Hourly metric snapshots |
| Other support tables | - | Settings, guardrails, etc. |

---

## Required Indexes

### kalshi_events
```javascript
db.kalshi_events.createIndex({ ticker: 1 })        // Unique event lookup
db.kalshi_events.createIndex({ series_ticker: 1 }) // Series grouping
db.kalshi_events.createIndex({ league: 1 })        // League filter
db.kalshi_events.createIndex({ status: 1 })        // Status filter
db.kalshi_events.createIndex({ updated_at: 1 })    // Recent updates
```

### kalshi_markets
```javascript
db.kalshi_markets.createIndex({ ticker: 1 })       // Unique market lookup
db.kalshi_markets.createIndex({ event_ticker: 1 }) // Event->Markets lookup
db.kalshi_markets.createIndex({ series_ticker: 1 })// Series grouping
db.kalshi_markets.createIndex({ league: 1 })       // League filter
db.kalshi_markets.createIndex({ status: 1 })       // Status filter
db.kalshi_markets.createIndex({ updated_at: 1 })   // Recent updates
```

### metrics_snapshots (NEW)
```javascript
db.metrics_snapshots.createIndex({ timestamp: 1 }) // Time-series queries
db.metrics_snapshots.createIndex({ hour_number: 1 })// Hour lookup
```

---

## Migration Steps (if deploying fresh)

1. **No schema migration required** - MongoDB is schema-less
2. **Indexes are auto-created** by the application on startup via KalshiBasketballIngestorV2
3. **Run initial data sync:**
   ```bash
   curl -X POST http://localhost:8001/api/kalshi/v2/sync
   ```

---

## Backup Recommendation

Before any production deployment:
```bash
mongodump --db=predictpod --out=/backup/$(date +%Y%m%d)
```

---

## Notes

- All collections use `_id` as primary key (MongoDB default)
- Kalshi data is upserted using `ticker` as unique identifier
- Metrics snapshots accumulate over time (cleanup policy TBD)
- No foreign key constraints (document-based design)
