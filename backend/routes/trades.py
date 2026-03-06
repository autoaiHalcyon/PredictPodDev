"""
routes/trades.py
────────────────────────────────────────────────────────────────────────────────
FastAPI router for paper + live trades.
Wires the five endpoints that tradeService.js (frontend) calls to the
existing TradeRepository methods.

Endpoints
─────────
POST   /api/trades                     → place a new trade
GET    /api/trades                     → list trades (optional ?game_id=)
PATCH  /api/trades/refresh-prices      → update current_price + pnl for open trades
PATCH  /api/trades/{trade_id}/close    → exit / close a position
DELETE /api/trades/{trade_id}          → hard-delete a trade record
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from repositories.trade_repository import TradeRepository
from models.trade import Trade, TradeStatus
from fastapi import APIRouter, Depends, HTTPException, Query, status
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def get_trade_repository():
    """Returns the global trade_repo initialized in server.py lifespan."""
    import server  # server.py holds the global trade_repo
    if server.trade_repo is None:
        raise HTTPException(status_code=503, detail="Trade repository not initialized")
    return server.trade_repo

router = APIRouter(prefix="/api/trades", tags=["trades"])


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class PlaceTradeRequest(BaseModel):
    """Matches the toDbDoc() output in tradeService.js."""
    id:              str
    game_id:         str
    market_id:       str

    side:            str                        # 'yes' | 'no'
    direction:       str                        # 'buy' | 'sell'
    quantity:        int
    price:           float                      # entry / limit price (0–1)
    order_type:      str      = "market"
    limit_price:     Optional[float] = None

    status:          str      = "filled"
    filled_quantity: int      = 0
    avg_fill_price:  float    = 0.0
    fees:            float    = 0.0
    is_paper:        bool     = True

    created_at:      Optional[datetime] = None
    executed_at:     Optional[datetime] = None

    signal_type:     Optional[str]   = None
    edge_at_entry:   Optional[float] = None

    # Extended / display fields (stored but not in original schema)
    type:            Optional[str]   = None     # 'manual' | 'auto-edge' | 'signal' | 'live'
    strategy:        Optional[str]   = None
    market_name:     Optional[str]   = None
    game_title:      Optional[str]   = None
    league:          Optional[str]   = None
    current_price:   Optional[float] = None
    exit_price:      Optional[float] = None
    closed_at:       Optional[datetime] = None
    pnl:             float = 0.0


class RefreshPricesRequest(BaseModel):
    game_id:       str
    current_price: float                        # mid-price from Kalshi (0–1)


class CloseTradeRequest(BaseModel):
    exit_price:  float
    closed_at:   Optional[datetime] = None
    status:      str = "closed"
    exit_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_pnl(side: str, entry: float, current: float, qty: int) -> float:
    """Replicate the frontend computePnl() so both sides always agree."""
    def eff(p):
        return p if side == "yes" else 1 - p
    return round((eff(current) - eff(entry)) * qty, 2)


def _trade_to_dict(req: PlaceTradeRequest) -> dict:
    now = datetime.utcnow()
    current = req.current_price if req.current_price is not None else req.price
    pnl     = _compute_pnl(req.side, req.avg_fill_price or req.price, current, req.quantity)

    return {
        # Core schema fields
        "id":              req.id,
        "game_id":         req.game_id,
        "market_id":       req.market_id,
        "side":            req.side,
        "direction":       req.direction,
        "quantity":        req.quantity,
        "price":           req.price,
        "order_type":      req.order_type,
        "limit_price":     req.limit_price,
        "status":          req.status,
        "filled_quantity": req.quantity,
        "avg_fill_price":  req.avg_fill_price or req.price,
        "fees":            req.fees,
        "is_paper":        req.is_paper,
        "created_at":      req.created_at or now,
        "executed_at":     req.executed_at or now,
        "signal_type":     req.signal_type,
        "edge_at_entry":   req.edge_at_entry,
        # Extended fields
        "type":            req.type or ("live" if not req.is_paper else "manual"),
        "strategy":        req.strategy,
        "market_name":     req.market_name,
        "game_title":      req.game_title,
        "league":          req.league,
        "current_price":   current,
        "exit_price":      req.exit_price,
        "closed_at":       req.closed_at,
        "pnl":             pnl,
        "realized_pnl":    0.0,       # locked in on close
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST  /api/trades  — place a new trade
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def place_trade(
    body: PlaceTradeRequest,
    repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Persist a new paper (or live) trade.
    Returns the saved document in the same shape the frontend expects.
    
    Active models: Model 1 (Enhanced CLV) + Model 2 (Strong Favorite Value).
    """
    # ── VALIDATION: Only allow Model 1 or Model 2 ────────────────────────────
    MAX_OPEN_TRADES_PER_MODEL = 20
    ALLOWED_STRATEGIES = (
        "model_1", "model_1_enhanced_clv", "model 1", "enhanced clv",
        "model_2", "model_2_strong_favorite", "model 2", "strong favorite",
    )

    if body.strategy and body.strategy.lower() not in ALLOWED_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only Model 1 (Enhanced CLV) and Model 2 (Strong Favorite) are active. "
                   f"Received strategy: '{body.strategy}'"
        )

    # ── VALIDATION: Max open trades per model ─────────────────────────────────
    all_trades = await repo.get_all(limit=1000)
    is_model_2 = body.strategy and "2" in body.strategy.lower()
    model_label = "model_2" if is_model_2 else "model_1"

    open_for_model = sum(
        1 for t in all_trades
        if getattr(t, "status", None) not in ("closed", "cancelled", "expired")
        and model_label in (getattr(t, "strategy", "") or "").lower().replace(" ", "_")
    )
    if open_for_model >= MAX_OPEN_TRADES_PER_MODEL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Max open trade limit ({MAX_OPEN_TRADES_PER_MODEL}) reached for "
                   f"{'Model 2' if is_model_2 else 'Model 1'}. Close some positions first."
        )

    # ── VALIDATION: Reject trades with a zero or missing entry price ─────────
    effective_price = body.avg_fill_price or body.price or 0.0
    if effective_price <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Trade rejected: entry price is $0.00. A valid market price is required."
        )

    doc = _trade_to_dict(body)
    trade = Trade(**doc)
    saved = await repo.create(trade)

    # ── Write decision trace (so /api/decisions/explain works for these trades) ─
    try:
        from services import decision_tracer as _dt
        _dt.write_from_trade_dict(saved.dict())
    except Exception as _te:
        import logging as _lg
        _lg.getLogger(__name__).warning(f"[trades] trace write failed: {_te}")

    # ── Write audit log entry to trading_audit_log collection ────────────────
    try:
        import server as _srv
        _db = getattr(_srv, "db", None)
        if _db is not None:
            _saved = saved.dict()
            price_f = float(_saved.get("avg_fill_price") or _saved.get("price") or 0)
            audit_entry = {
                "id":               str(__import__("uuid").uuid4()),
                "order_id":         _saved.get("id") or "",
                "market_id":        _saved.get("market_id") or "",
                "market_ticker":    _saved.get("market_id") or "",
                "game_id":          _saved.get("game_id"),
                "side":             _saved.get("side") or "",
                "action":           _saved.get("direction") or "buy",
                "order_type":       _saved.get("order_type") or "market",
                "quantity":         int(_saved.get("quantity") or 0),
                "price_cents":      round(price_f * 100),
                "edge":             float(_saved.get("edge_at_entry") or 0),
                "signal_score":     None,
                "status":           _saved.get("status") or "filled",
                "fill_price_cents": round(price_f * 100),
                "filled_quantity":  int(_saved.get("filled_quantity") or _saved.get("quantity") or 0),
                "cost_basis_cents": round(price_f * 100 * int(_saved.get("quantity") or 0)),
                "fees_cents":       round(float(_saved.get("fees") or 0) * 100),
                "strategy":         _saved.get("strategy"),
                "signal_type":      _saved.get("signal_type"),
                "game_title":       _saved.get("game_title"),
                "market_name":      _saved.get("market_name"),
                "league":           _saved.get("league"),
                "is_paper":         _saved.get("is_paper", True),
                "timestamp":        __import__("datetime").datetime.utcnow(),
                "created_at":       __import__("datetime").datetime.utcnow(),
            }
            await _db.trading_audit_log.insert_one(audit_entry)
    except Exception as _ae:
        import logging as _lg2
        _lg2.getLogger(__name__).warning(f"[trades] audit log write failed: {_ae}")

    return saved.dict()


# ─────────────────────────────────────────────────────────────────────────────
# GET  /api/trades  — list trades, optionally filtered by game_id
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_trades(
    game_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    trade_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(500, le=1000),
    repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Return trades newest-first.
    Frontend calls:  GET /api/trades
                     GET /api/trades?game_id=KXNBA-...
    """
    if game_id:
        trades = await repo.get_by_game_id(game_id)
    else:
        trades = await repo.get_all(limit=limit)

    # Optional in-memory filters (keep DB queries simple)
    if status_filter:
        # 'filled' in DB = 'open' in UI; normalise for the filter
        db_status = "filled" if status_filter == "open" else status_filter
        trades = [t for t in trades if t.status == db_status]

    if trade_type:
        trades = [t for t in trades if getattr(t, "type", None) == trade_type]

    return [t.dict() for t in trades]


# ─────────────────────────────────────────────────────────────────────────────
# PATCH  /api/trades/refresh-prices  — update live P&L for open positions
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: this route MUST be declared before /{trade_id} to avoid FastAPI
#       matching "refresh-prices" as a trade_id path param.

@router.patch("/refresh-prices")
async def refresh_prices(
    body: RefreshPricesRequest,
    repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Called on every 10-second Kalshi poll for a game.
    Updates current_price + pnl for all open trades belonging to that game.
    """
    open_trades = await repo.find({
        "game_id": body.game_id,
        "status":  "filled",          # 'filled' == open in DB
    })

    updated = 0
    for trade in open_trades:
        new_pnl = _compute_pnl(
            trade.side,
            trade.avg_fill_price or trade.price,
            body.current_price,
            trade.quantity,
        )
        await repo.update(trade.id, {
            "current_price": body.current_price,
            "pnl":           new_pnl,
        })
        updated += 1

    return {"updated": updated, "game_id": body.game_id}


# ─────────────────────────────────────────────────────────────────────────────
# PATCH  /api/trades/{trade_id}/close  — exit / close a position
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{trade_id}/close")
async def close_trade(
    trade_id: str,
    body: CloseTradeRequest,
    repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Mark a trade as closed, lock in the exit price, and record realised P&L.
    """
    trade = await repo.get_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

    realized_pnl = _compute_pnl(
        trade.side,
        trade.avg_fill_price or trade.price,
        body.exit_price,
        trade.quantity,
    )

    try:
        updated = await repo.update(trade_id, {
            "status":        "closed",
            "exit_price":    body.exit_price,
            "current_price": body.exit_price,
            "closed_at":     body.closed_at or datetime.utcnow(),
            "pnl":           realized_pnl,
            "realized_pnl":  realized_pnl,   # used by get_daily_pnl() aggregate
            **({"exit_reason": body.exit_reason} if body.exit_reason else {}),
        })

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to close trade")

        # Return the full document including all fields
        return updated.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing trade: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# DELETE  /api/trades/{trade_id}  — hard-delete a trade record
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: str,
    repo: TradeRepository = Depends(get_trade_repository),
):
    """Permanently remove a trade document."""
    deleted = await repo.delete(trade_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")