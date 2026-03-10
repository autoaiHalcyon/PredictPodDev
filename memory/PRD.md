# PredictPod - Dynamic Strategy Management PRD

## Project Overview
PredictPod is a Bloomberg-style probability intelligence terminal for NBA prediction markets trading via Kalshi using a paper trading engine.

## Problem Statement
Extend the system so users can create and manage strategies dynamically while maintaining full compatibility with the existing JSON configuration schema used by the backend trading engines.

## User Choices & Decisions
1. **Database**: MongoDB (existing)
2. **Config Generation**: Option B - Generate JSON files on startup in `backend/strategies/configs/generated/`
3. **UI Design**: Keep current Bloomberg-style terminal aesthetic
4. **Authentication**: Available to all authenticated users (existing app auth)
5. **Feature Priority**: Create → Clone → Edit

## Architecture

### Backend Components
- `/app/backend/models/strategy.py` - Strategy Pydantic models
- `/app/backend/repositories/strategy_repository.py` - MongoDB CRUD operations
- `/app/backend/routes/strategies.py` - REST API endpoints for strategy management
- `/app/backend/strategies/strategy_manager.py` - Updated to load strategies from DB + generated configs

### Frontend Components
- `/app/frontend/src/pages/StrategyCommandCenter.js` - Updated with Create/Clone modals
- `/app/frontend/src/pages/TradesCenter.js` - Updated to support dynamic strategies

### Database Schema
```
strategies collection:
- id: ObjectId
- strategy_key: string (unique)
- model_id: string (model_a, model_b, etc.)
- display_name: string
- description: string
- enabled: boolean
- config_json: object (full JSON config)
- created_at: datetime
- updated_at: datetime
```

## What's Been Implemented ✅ (2026-03-10)
- [x] Strategy model and repository (MongoDB)
- [x] REST API endpoints:
  - GET /api/user-strategies - List all strategies
  - POST /api/user-strategies - Create new strategy
  - PUT /api/user-strategies/{id} - Update strategy
  - DELETE /api/user-strategies/{id} - Delete user-created strategy
  - POST /api/user-strategies/{id}/clone - Clone existing strategy
  - GET /api/user-strategies/base-models - Get base model templates
  - GET /api/user-strategies/parameter-bounds - Get validation bounds
- [x] JSON config file generation in `configs/generated/`
- [x] Strategy Manager updates to load from DB + generated configs
- [x] Frontend Create Strategy modal with base model selection
- [x] Frontend Clone Strategy modal
- [x] Dynamic strategy rendering in Strategy Command Center
- [x] Strategy cards with Clone buttons
- [x] Environment configuration (.env files for frontend/backend)

## Preserved JSON Schema
All user-created strategies preserve the existing schema required by trading engines:
- model_id, display_name, description, enabled
- starting_capital, currency
- entry_rules, exit_rules, position_sizing
- risk_limits, filters, trim_rules, circuit_breakers

## API Credentials
- Test User: predictpod@example.com / Halcyon12$

## Remaining / Backlog
### P0 (Critical)
- None

### P1 (High Priority)
- [ ] Edit Strategy modal with full parameter editing
- [ ] Parameter validation against bounds

### P2 (Medium Priority)
- [ ] Strategy performance comparison for user-created strategies
- [ ] Export/Import strategies as JSON
- [ ] Strategy templates library

## Next Steps
1. Implement Edit Strategy modal with parameter editing
2. Add parameter validation using parameter_bounds.json
3. Show user-created strategies in Trades Center with proper attribution
