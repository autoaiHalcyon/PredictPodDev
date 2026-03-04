<!-- QUICK REFERENCE: Daily Results & Rules Management -->

# 🎯 QUICK START GUIDE

## 📍 New Features Locations

### Daily Results Dashboard
- **URL**: `/daily-results`
- **Navigation**: Click "Daily Results" in top menu
- **What**: See all three strategy performance + manage rules

### Trades Center (Improved)
- **URL**: `/trades`
- **New**: Pagination (10/25/50/100 trades per page)
- **UI**: Cleaner layout, no horizontal scrolling

---

## 🎮 How to Use

### View Daily Performance
1. Go to **Daily Results** page
2. Use date picker to select date
3. See 3 strategy cards with:
   - Daily P&L
   - Win rate
   - Rules in effect
4. Scroll down to see today's trades

### Edit Strategy Rules ⭐ NEW
1. On Daily Results page, click **"Edit"** button on strategy
2. Change parameters like:
   - `Min Edge`: Lower = more trades
   - `Min Signal Score`: Lower = broader signals
   - `Profit Target`: When to sell
   - `Stop Loss`: Max loss allowed
3. Type change description
4. Click **"Save Rules"**
5. ✅ Rules saved to database immediately!

### Browse Trades with Pagination
1. Go to **Trades** page
2. Select page size top-left (10/25/50/100)
3. Use Next/Previous to browse
4. Click page numbers for direct navigation
5. Filters work with pagination

---

## 📊 Key Metrics to Adjust

| Parameter | Effect | Adjust to |
|-----------|--------|-----------|
| Min Edge | Entry threshold | ↓ for more trades, ↑ for quality |
| Signal Score | Signal strength min | ↓ for sensitivity, ↑ for confidence |
| Profit Target | When to take profit | ↓ to lock in gains, ↑ for momentum |
| Stop Loss | Max loss per trade | ↓ for protection, ↑ for wiggle room |
| Max Spread | Liquidity filter | ↓ for tight orders, ↑ for flexibility |
| Persistence | Confirmation bars | ↓ for speed, ↑ for confirmation |

---

## 🔄 Optimization Workflow

```
1. View Daily Results
   ↓
2. Analyze Performance
   ↓
3. Edit Rules that underperformed
   ↓
4. Save (versioned automatically)
   ↓
5. Monitor today's trades
   ↓
6. Compare results tomorrow
   ↓
7. Rollback if needed
```

---

## 💡 Pro Tips

✅ **Save detailed change summaries** - "Loosened edge to 2% to catch more early signals"
✅ **One change at a time** - Makes it easier to track what worked
✅ **Check trade execution** - Scroll down to see rules actually triggered
✅ **Use pagination** - 25 trades/page is perfect for scrolling
✅ **Track version history** - Each save creates a numbered version

---

## 🔗 Navigation Quick Links

- 🏠 **Terminal** `/` - Main dashboard
- 🎮 **All Games** `/all-games` - Game selector  
- ⚡ **Strategy Center** `/strategy-command-center` - Model control
- 📈 **Daily Results** `/daily-results` - Performance + rules ⭐ NEW
- 📋 **Trades** `/trades` - Trade blotter (now with pagination) ⭐ IMPROVED
- 💼 **Portfolio** `/portfolio` - Aggregate metrics
- ⚙️ **Settings** `/settings` - Configuration

---

## 🚨 If Something Doesn't Work

### Rules won't save?
- Check backend is running
- Look at browser DevTools console
- Verify all fields are filled

### Can't see daily trades?
- Check date is set to today
- Verify trades were actually placed
- Try clicking Refresh

### Pagination acting odd?
- Clear browser cache
- Refresh the page  
- Try different page size

---

## 📞 Summary

You now have:
- ✅ Daily results page with rule editor
- ✅ Ability to override and save new rules to database
- ✅ Trade pagination (no more side-scrolling)
- ✅ Three strategies editable from one place
- ✅ Version history and rollback capability

**Start optimizing your strategies today!**
