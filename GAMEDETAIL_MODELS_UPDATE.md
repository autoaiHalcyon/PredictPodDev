# Game Details Page - Model A/B/C Enforcement

## Summary
Updated `GameDetail.jsx` to enforce strict adherence to Model A, B, and C trading strategies only. All legacy strategies (Strong Buy, Buy, Sell, Clutch Momentum, Sell Into Strength) have been replaced.

## Changes Made

### 1. **STRATEGIES Array Updated** (Lines 187-217)
**Before**: 5 legacy strategies
- Strong Buy (green)
- Buy (blue) 
- Sell (red)
- Clutch Momentum (orange)
- Sell Into Strength (yellow)

**After**: 3 Model-Based Strategies
- **Model A** (emerald) - Disciplined Edge Trader
  - Min Edge: ≥5%
  - Min Signal Score: ≥60
  - Momentum: Required
  - Risk Tier: LOW only
  - Rules: Edge, Signal Score, Momentum, Risk Tier

- **Model B** (blue) - High Frequency Hunter
  - Min Edge: ≥3%
  - Min Signal Score: ≥45
  - Risk Tier: LOW/MEDIUM
  - Rules: Edge, Signal Score, Risk Tier

- **Model C** (purple) - Institutional Risk-First
  - Min Edge: ≥7%
  - Min Signal Score: ≥75
  - Momentum: Required
  - Risk Tier: LOW only
  - Rules: Edge, Signal Score, Momentum, Risk Tier

### 2. **Color Map Extended** (Lines 261-267)
Added new color schemes:
- `emerald` - Model A theme
- `purple` - Model C theme

## Impact
- **Trade Enforcement**: All trades must now satisfy Model A, B, or C entry criteria
- **Strategy Matching**: `evaluateStrategies()` function now evaluates trades against these 3 models only
- **StrategyMatchPanel**: Displays only Model A, B, or C recommendations
- **Legacy Strategies Removed**: No more arbitrary strong/medium/weak classifications
- **Clear Model Attribution**: Every matched strategy now shows which model was selected

## Model Eligibility Summary

| Criterion | Model A | Model B | Model C |
|-----------|---------|---------|---------|
| Min Edge | 5% | 3% | 7% |
| Min Signal | 60 | 45 | 75 |
| Momentum | Required | Optional | Required |
| Risk Tier | LOW | LOW/MED | LOW |
| Best For | Conservative traders | High-frequency scalpers | Institutional managers |

## Testing Checklist
- [ ] Game Detail page loads without errors
- [ ] No Strategy Matched when conditions don't meet any model
- [ ] Model A matches when: Edge ≥5%, Signal ≥60, Momentum, Risk LOW
- [ ] Model B matches when: Edge ≥3%, Signal ≥45, Risk LOW/MED
- [ ] Model C matches when: Edge ≥7%, Signal ≥75, Momentum, Risk LOW
- [ ] Strategy panel shows emerald/blue/purple badges correctly
- [ ] Paper trades respect selected model rules

## Backend Validation
**IMPORTANT**: Backend trade execution engine must also validate trades against these 3 models only. See:
- `backend/models/signal.py` - Signal generation
- `backend/services/kalshi_ingestor_v2.py` - Trade entry evaluation
- `backend/routes/trades.py` - Trade acceptance logic

Reject any trades that don't match Model A, B, or C criteria.

## Files Modified
- `frontend/src/pages/GameDetail.jsx` - Lines 187-217 (STRATEGIES), Lines 261-267 (colorMap)

## No Errors
✅ All syntax validated - no errors found
