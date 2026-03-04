# Backend Restart & Verification Guide

## Critical Updates Applied

The following fixes have been applied to resolve CORS and rate limiting issues:

### ✅ Configuration Changes (backend/config.py)
- **Rate limit increased**: 100 → 500 requests/60 seconds (5x more headroom)
- Allows StrategyCommandCenter polling + other traffic without hitting limits
- Removed duplicate limit window definition

### ✅ Middleware Fixes (backend/server.py)
1. **Removed duplicate `check_rate_limit` function** (was defined at lines 348 and 352)
2. **Added CORS preflight exemption**:
   - OPTIONS requests now bypass rate limiting
   - CORS middleware runs before rate limiting middleware
3. **Improved error messages**:
   - Now shows new 500 req/min threshold in 429 responses

### ✅ Frontend Polling Optimization
1. **StrategyCommandCenter**: Polling reduced 2s → 5s intervals
2. **Better error handling**: Shows CORS, rate limit, and network errors clearly
3. **Error display**: Shows troubleshooting instructions in UI

---

## Step 1: Stop the Current Backend Server

**If running in VS Code terminal:**
```bash
# In the terminal running uvicorn, press:
Ctrl + C
```

Wait for the process to exit. You should see:
```
INFO: Shutdown complete
```

---

## Step 2: Start the Backend with New Config

**From the `backend/` directory:**

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

**Expected startup output:**
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
INFO: Waiting for code changes...
```

✅ If you see these messages, configuration has loaded successfully.

---

## Step 3: Verify Frontend Loads

**Open the frontend in your browser:**
- URL: http://localhost:3000
- Check these pages:
  1. **Dashboard** (Auto Refresh, should not show errors)
  2. **Daily Results** (Should load with rules editor)
  3. **Trades Center** (Should show trade blotter with pagination)
  4. **Strategy Command Center** (Should auto-refresh every 5 seconds)

### ✅ Success Indicators
- **No red error boxes** with "Backend Connection Error"
- **No CORS policy messages** in browser console
- **No 429 (Too Many Requests) errors** in Network tab
- **Pages refresh smoothly** without error storms

### ❌ If Errors Still Appear

Check your browser's Developer Tools (F12 → Console tab):

**Error: "CORS policy: No 'Access-Control-Allow-Origin' header"**
- Solution: Ensure backend restarted (CORS middleware will handle preflight)
- Check: Backend console should show preflight OPTIONS requests succeeding

**Error: "429 Too Many Requests"**
- Solution: Rate limit now 500/min, should have headroom
- Check: Are other background processes hammering the API?
- Try: Reduce polling further (change 5000 → 10000 in StrategyCommandCenter)

**Error: "Cannot reach backend"**
- Check: Is backend running on port 8000?
- Command: `netstat -an | findstr :8000` (Windows) or `lsof -i :8000` (Mac/Linux)
- Fix: Start backend if not running

---

## Diagnostic Commands

### Check Backend is Listening
```bash
# Windows
netstat -an | findstr :8000

# Mac/Linux
lsof -i :8000
```

Should show something like `0.0.0.0:8000` or `127.0.0.1:8000` in LISTEN state.

### Check Frontend Can Reach Backend
In browser console (F12):
```javascript
// Test basic connectivity
fetch('http://localhost:8000/api/health')
  .then(r => r.json())
  .then(console.log)
  .catch(e => console.error('Backend unreachable:', e));
```

Should return `{"status": "ok"}` if backend is healthy.

### Monitor Rate Limiting
In backend terminal, you'll see logs like:
```
INFO: GET /api/strategies/summary HTTP/1.1" 200 OK
INFO: GET /api/strategies/positions/by_game HTTP/1.1" 200 OK
```

If rate limited requests appear:
```
INFO: GET /api/strategies/summary HTTP/1.1" 429 Too Many Requests
```

This means you're still hitting the limit. Options:
1. Increase limit further in config.py
2. Reduce polling frequency in frontend
3. Add request batching (one request returns multiple datasets)

---

## Detailed Fix Explanation

### Why 500 req/min?
- **StrategyCommandCenter** polling: 2 requests every 5 seconds = 24 req/min
- **TradesCenter** polling: 1 request every 15 seconds = 4 req/min
- **Browser preflight**: Each fetch may trigger 2 OPTIONS requests = ~6 req/min
- **Other pages**: Manual fetches, rules updates, trades = ~20 req/min
- **Total estimated**: ~54 req/min, so 500/min gives ~10x safety margin

### Why Exempting OPTIONS?
- CORS preflight requests happen **before** the actual request
- They don't consume data, just establish permission
- Counting them against rate limits blocks all cross-origin requests
- Solution: Skip rate limiting for "OPTIONS" requests only

### Why Not Higher Polling?
- 2-second intervals = 60 requests/min from one page
- Adds latency for other users/requests
- 5-second intervals = 12 req/min (very sustainable)
- Database queries are the bottleneck, not the polling interval

---

## Rollback (If Needed)

If something goes wrong, revert config:

**backend/config.py**: Change back to:
```python
rate_limit_requests: int = 100
```

**backend/server.py**: Remove the OPTIONS check from middleware (lines ~356-358):
```python
# Remove this section:
if request.method == "OPTIONS":
    return await call_next(request)
```

Then restart backend with Ctrl+C and re-run uvicorn command.

---

## Next Steps

Once verified working:

1. ✅ Test rules editor on DailyResults page
2. ✅ Test pagination on Trades page
3. ✅ Watch real-time updates on StrategyCommandCenter
4. ✅ Create a trade and verify it appears instantly
5. ⚙️ Monitor backend logs for 24 hours to ensure 500 req/min is sufficient
6. 🚀 If stable, consider production settings (stricter limits with metrics)

---

## Questions or Issues?

Check the error message carefully:
- **429**: Too many requests → reduce polling or increase limit
- **CORS**: Browser blocked request → ensure backend restarted
- **Network error**: Backend not responding → check if server is running
- **Timeout**: Query taking too long → check MongoDB connection

Always check both:
1. **Browser F12 Console**: What error does the browser see?
2. **Backend terminal**: What does the server log show?

These two views together will pinpoint the issue.
