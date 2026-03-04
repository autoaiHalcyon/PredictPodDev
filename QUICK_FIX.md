# ⚡ Quick Start: Get System Running Now

## 🎯 Your Goal
Fix the "429 Too Many Requests" and "CORS policy blocked" errors preventing the frontend from loading.

## ✅ What's Been Fixed
- Rate limit increased from 100 → 500 requests/minute
- CORS preflight requests now bypass rate limiting
- Polling reduced from 2s → 5s intervals (less traffic)
- Better error messages to help diagnose issues
- Removed duplicate code

## 🚀 What You Need to Do

### Step 1: Stop the Old Backend (REQUIRED)
**In your terminal running `python -m uvicorn ...`:**
```
Press: Ctrl + C
```
Wait for it to say "Shutdown complete"

### Step 2: Start the New Backend (REQUIRED)
**In the same terminal, type:**
```bash
cd backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

**You should see:**
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
INFO: Waiting for code changes...
```

✅ If you see those lines, **THE FIX IS WORKING**

### Step 3: Clear Browser Cache (RECOMMENDED)
**In your browser:**
- Press **Ctrl + Shift + Delete**
- Make sure **"Cached images and files"** is checked
- Click **"Delete"**

Then reload: `http://localhost:3000`

### Step 4: Check Each Page
1. **Dashboard** - should load without error boxes
2. **Daily Results** - should show 3 strategy cards with rules
3. **Trades Center** - should show trade table with pagination
4. **Strategy Command Center** - should update every 5 seconds

**SUCCESS**: No red error boxes = you're done! ✅

---

## ❌ Still Getting Errors?

Open your browser's Developer Tools: **F12 → Console**

### Error: "429 Too Many Requests"
- ❌ Backend did NOT restart properly
- Fix: 
  1. Ctrl+C in backend terminal
  2. Clear cache (Ctrl+Shift+Del)
  3. Restart backend with uvicorn command above

### Error: "CORS policy: No 'Access-Control-Allow-Origin'"
- ❌ Backend did NOT restart properly (same as above)
- Fix: Stop backend, restart backend

### Error: "Cannot reach backend" or "Failed to fetch"
- ❌ Backend is not running
- Fix:
  1. Make sure your terminal is in the `backend/` directory
  2. Run: `python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
  3. Check: You should see "Application startup complete"

### Error keeps repeating (same error every 5 seconds)
- ❌ Frontend still polling but backend unavailable
- Fix: Check backend is running (see above)

---

## 💡 How to Verify It's Fixed

**Test in browser console (F12):**
```javascript
fetch('http://localhost:8000/api/health')
  .then(r => r.json())
  .then(d => console.log('✅ Backend OK:', d))
  .catch(e => console.error('❌ Backend down:', e))
```

Should print: `✅ Backend OK: {status: 'ok'}`

---

## 📊 What Changed

| Item | Before | After |
|------|--------|-------|
| Rate Limit | 100 req/min | 500 req/min |
| Polling | Every 2 seconds | Every 5 seconds |
| CORS Preflight | Blocked | Allowed |
| Errors | Repeated 429s | Clear messages |

---

## 🆘 If Still Stuck

### Check #1: Is backend running?
```bash
# Windows:
netstat -an | findstr :8000

# Mac/Linux:
lsof -i :8000
```
Should show something with "LISTEN" (means it's running)

### Check #2: Is it the right Python?
```bash
python --version
```
Should be 3.8 or higher

### Check #3: Is MongoDB running?
Check you have MongoDB accessible (if backend can't connect to DB, API won't respond)

### Check #4: Any error messages in backend terminal?
Look for red text or "ERROR" in your backend terminal. Copy and check those errors.

---

## 📝 Summary

**What you're doing**: Restarting the backend with a fixed configuration
**Why**: Old rate limit (100) was too strict for your polling traffic
**How long**: 2-3 minutes total
**Result**: All pages should work without errors

**No code changes needed on your part** - everything is fixed in the files automatically!

---

Got it running? 🎉

Next steps:
1. Test rules editing on Daily Results page
2. Try creating/closing trades
3. Watch Strategy Command Center auto-update

Questions? Check the `BACKEND_RESTART_GUIDE.md` or `CRITICAL_FIXES_SUMMARY.md` for detailed info.
