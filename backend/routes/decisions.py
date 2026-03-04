"""
routes/decisions.py
────────────────────────────────────────────────────────────────────────────────
Endpoints for retrieving and explaining decision-trace records produced by
services/decision_tracer.py.

Endpoints
─────────
GET /api/decisions/latest?model=A&limit=200
    → last N records for a model (or all models) from today's JSONL file.

GET /api/decisions/explain?order_id=<id>
    → single record whose entry_order_id or exit_order_id matches.

GET /api/decisions/explain?market_ticker=<ticker>&model=B
    → most-recent record for that ticker/model combination.

Every response includes the raw DecisionTrace dict plus a
`human_summary` string (1–3 lines).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

# ── File resolution (must match decision_tracer._LOG_DIR) ─────────────────
_HERE     = Path(__file__).resolve().parent          # backend/routes/
_LOG_DIR  = _HERE.parent / "logs" / "decision_traces"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today_file() -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return _LOG_DIR / f"decision_trace_{date_str}.jsonl"


def _read_records(
    date_str: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 200,
    reverse: bool = True,
) -> List[Dict]:
    """
    Read JSONL records for a given date (default: today).
    Optionally filter by model_id.  Returns up to *limit* entries.
    When reverse=True the most-recent records come first.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    path = _LOG_DIR / f"decision_trace_{date_str}.jsonl"
    if not path.exists():
        return []

    records: List[Dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Model filter: match "A", "B", "C" against model_id field
                if model:
                    mid = (rec.get("model_id") or "").upper()
                    if mid != model.upper():
                        continue
                records.append(rec)
    except OSError as exc:
        logger.warning(f"[decisions] Cannot read {path}: {exc}")
        return []

    if reverse:
        records = list(reversed(records))

    return records[:limit]


def _build_human_summary(rec: Dict) -> str:
    """
    Produce a concise 1-3 line English explanation for any decision record.

    Format examples
    ───────────────
    ENTER  → "ENTER: Edge 6.1%>5%, Conf 74%>60, Persist 92s>90s, EV $11.20, Risk OK."
    EXIT   → "EXIT (Stop Loss -10%): entry 68¢→exit 61¢, PnL -$0.68 (-10.0%)."
    HOLD   → "HOLD: position open, edge 2.1% below entry threshold, no exit trigger."
    BLOCK  → "NO_TRADE: SPREAD_FILTER_FAIL — spread 12.3¢ exceeds 10¢ max."
    NO_TRADE→"NO_TRADE: edge 2.1% below 5% threshold."
    """
    action      = (rec.get("action") or "NO_TRADE").upper()
    model_id    = rec.get("model_id", "?")
    ticker      = rec.get("market_ticker", "?")
    edge_raw    = rec.get("edge", 0.0) or 0.0
    edge_pct    = round(edge_raw * 100, 2)
    conf_raw    = rec.get("confidence", 0.0) or 0.0
    conf_pct    = round(conf_raw * 100, 1)
    persist     = rec.get("persistence_sec", 0.0) or 0.0
    ev_usd      = rec.get("ev_usd")
    kelly       = rec.get("kelly_fraction", 0.0) or 0.0
    stake       = rec.get("stake_usd", 0.0) or 0.0
    reason_codes: List[str] = rec.get("reason_codes") or []
    pnl_r       = rec.get("pnl_realized_usd")
    pnl_u       = rec.get("pnl_unrealized_usd")
    spread_c    = rec.get("spread_cents")

    # ── Thresholds from eligibility checks (fall back to common defaults) ──
    def _threshold(check_name: str, fallback: str) -> str:
        echecks = rec.get("eligibility_checks") or {}
        info    = echecks.get(check_name) or {}
        reason  = info.get("reason", "")
        # parse "threshold=X" from reason string
        for part in reason.split(","):
            part = part.strip()
            if part.startswith("threshold="):
                return part.split("=", 1)[1]
        return fallback

    edge_thresh  = _threshold("min_edge",          "5%")
    score_thresh = _threshold("min_signal_score",  "60")
    persist_thresh = _threshold("edge_persistence", "90s")

    # ── Failing reason codes ───────────────────────────────────────────────
    fails = [c for c in reason_codes if c.endswith("_FAIL")]
    passes = [c for c in reason_codes if c.endswith("_OK")]

    def _pretty(code: str) -> str:
        """Turn 'SPREAD_FILTER_FAIL' → 'spread too wide'."""
        base = code.replace("_FAIL", "").replace("_OK", "").replace("_", " ").lower()
        return base

    # ─────────────────────────────────────────────────────────────────────
    # Build summary per action
    # ─────────────────────────────────────────────────────────────────────

    if action == "ENTER":
        ev_str     = f"EV ${ev_usd:.2f}" if ev_usd is not None else ""
        kelly_str  = f"Kelly {kelly:.1%}" if kelly else ""
        stake_str  = f"stake ${stake:.2f}" if stake else ""
        parts = [
            f"Edge {edge_pct:.1f}%>{edge_thresh}",
            f"Conf {conf_pct:.0f}%>{score_thresh}",
            f"Persist {persist:.0f}s>{persist_thresh}",
        ]
        if ev_str:
            parts.append(ev_str)
        if kelly_str:
            parts.append(kelly_str)
        if stake_str:
            parts.append(stake_str)
        parts.append("Risk OK" if not fails else f"Risks: {', '.join(_pretty(f) for f in fails)}")
        return f"ENTER [{model_id}@{ticker}]: " + ", ".join(parts) + "."

    if action == "EXIT":
        exit_reason_raw = rec.get("exit_reason") or ""
        entry_p = rec.get("entry_price")
        exit_p  = rec.get("exit_price")
        entry_str = f"entry {round(entry_p*100):.0f}¢"  if entry_p is not None else ""
        exit_str  = f"exit {round(exit_p*100):.0f}¢"   if exit_p  is not None else ""
        pnl_str   = ""
        if pnl_r is not None:
            sign = "+" if pnl_r >= 0 else ""
            pnl_str = f"PnL {sign}${pnl_r:.2f}"
            if entry_p and entry_p > 0 and exit_p is not None:
                ret_pct = ((exit_p - entry_p) / entry_p) * 100
                pnl_str += f" ({ret_pct:+.1f}%)"
        # Shorten exit reason for display
        reason_short = exit_reason_raw.split(":")[0].strip() if exit_reason_raw else "rule triggered"
        parts = [p for p in [entry_str, exit_str, pnl_str] if p]
        return (
            f"EXIT [{model_id}@{ticker}] — {reason_short}: "
            + (", ".join(parts) if parts else "position closed")
            + "."
        )

    if action == "HOLD":
        pos_pnl = ""
        if pnl_u is not None:
            sign = "+" if pnl_u >= 0 else ""
            pos_pnl = f", unrealised PnL {sign}${pnl_u:.2f}"
        return (
            f"HOLD [{model_id}@{ticker}]: position open, "
            f"edge {edge_pct:.1f}%, conf {conf_pct:.0f}%{pos_pnl}."
        )

    if action in ("BLOCK", "CIRCUIT_BREAKER"):
        if fails:
            fail_detail = "; ".join(_pretty(f) for f in fails)
        else:
            fail_detail = "risk/circuit-breaker limit hit"
        return (
            f"NO_TRADE [{model_id}@{ticker}]: blocked — {fail_detail}."
        )

    # NO_TRADE (no position, entry criteria not met)
    if fails:
        fail_detail = "; ".join(_pretty(f) for f in fails)
        return f"NO_TRADE [{model_id}@{ticker}]: {fail_detail}."

    # Generic fallback
    if spread_c is not None and spread_c > 10:
        return (
            f"NO_TRADE [{model_id}@{ticker}]: spread {spread_c:.1f}¢ too wide, "
            f"edge {edge_pct:.1f}%."
        )
    return (
        f"NO_TRADE [{model_id}@{ticker}]: "
        f"edge {edge_pct:.1f}% (threshold {edge_thresh}), "
        f"conf {conf_pct:.0f}%."
    )


def _enrich(rec: Dict) -> Dict:
    """Add human_summary to a raw record dict."""
    return {**rec, "human_summary": _build_human_summary(rec)}


async def _fallback_from_db(order_id: str) -> Optional[Dict]:
    """
    When no JSONL trace exists for *order_id* (e.g. trade was placed via the
    frontend before the trace-write fix, or the JSONL was rolled), synthesise a
    minimal trace dict from the MongoDB document stored by POST /api/trades.

    Returns None if the trade cannot be found.
    """
    try:
        import server as _srv
        db = getattr(_srv, "db", None)
        if db is None:
            return None

        doc = None
        # Trades are stored in db.trades by TradeRepository
        for col_name in ("trades", "orders", "live_orders"):
            doc = await db[col_name].find_one(
                {"$or": [
                    {"id":       order_id},
                    {"order_id": order_id},
                    {"entry_order_id": order_id},
                    {"exit_order_id":  order_id},
                ]},
                {"_id": 0}
            )
            if doc:
                break
        if doc is None:
            return None

        # Build a synthetic trace record from the stored trade fields.
        edge_val   = float(doc.get("edge_at_entry") or doc.get("edge") or 0.0)
        entry_p    = float(doc.get("avg_fill_price") or doc.get("entry_price") or
                           doc.get("price") or 0.0)
        qty        = int(doc.get("quantity") or doc.get("filled_quantity") or 0)
        model_raw  = (doc.get("strategy") or doc.get("model") or "unknown").lower()
        ticker     = doc.get("market_id") or doc.get("market_ticker") or "?"
        action     = "ENTER"
        status_val = (doc.get("status") or "").lower()
        if status_val in ("closed", "cancelled", "settled"):
            action = "EXIT"

        return {
            "source":          "mongodb_fallback",
            "ts":              str(doc.get("created_at") or doc.get("timestamp") or ""),
            "league":          doc.get("league") or "",
            "event_id":        doc.get("game_id") or "",
            "market_ticker":   ticker,
            "model_id":        model_raw,
            "edge":            round(edge_val, 6),
            "mid_price":       entry_p,
            "stake_usd":       round(entry_p * qty, 2),
            "reason_codes":    [doc.get("signal_type") or "TRADE_PLACED"],
            "action":          action,
            "entry_order_id":  order_id if action == "ENTER" else None,
            "entry_price":     entry_p   if action == "ENTER" else None,
            "exit_order_id":   order_id  if action == "EXIT"  else None,
            "exit_price":      float(doc.get("exit_price") or 0.0) if action == "EXIT" else None,
            "exit_reason":     doc.get("exit_reason"),
            "pnl_realized_usd": float(doc.get("realized_pnl") or doc.get("pnl") or 0.0)
                                if action == "EXIT" else None,
            "quantity":        qty,
            "side":            doc.get("side"),
            "game_title":      doc.get("game_title"),
            "market_name":     doc.get("market_name"),

            # Fields not available from trade doc
            "best_bid":        None, "best_ask":       None,
            "spread_cents":    None, "volume_5m":      None,
            "confidence":      None, "persistence_sec": None,
            "ev_usd":          None, "kelly_fraction": None,
            "eligibility_checks": {}, "risk_checks": {},
        }
    except Exception as exc:
        logger.warning(f"[decisions] _fallback_from_db failed: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/latest")
def get_latest_decisions(
    model: Optional[str] = Query(None, description="Filter by model id: A, B or C"),
    limit: int            = Query(200, ge=1, le=2000, description="Max records to return"),
    date:  Optional[str]  = Query(None, description="Date in YYYYMMDD, default today UTC"),
):
    """
    Return the most-recent *limit* decision-trace records (newest first).
    Optionally filter by model (A/B/C) and/or date.
    """
    records = _read_records(date_str=date, model=model, limit=limit, reverse=True)
    enriched = [_enrich(r) for r in records]
    return {
        "count":   len(enriched),
        "model":   model,
        "date":    date or datetime.now(timezone.utc).strftime("%Y%m%d"),
        "records": enriched,
    }


@router.get("/explain")
async def explain_decision(
    order_id:       Optional[str] = Query(None, description="entry_order_id or exit_order_id"),
    market_ticker:  Optional[str] = Query(None, description="Kalshi market ticker"),
    trade_id:       Optional[str] = Query(None, description="Internal trade UUID (looks up order_id from DB)"),
    model:          Optional[str] = Query(None, description="Model id: A, B or C (used with market_ticker)"),
    date:           Optional[str] = Query(None, description="Date in YYYYMMDD, default today UTC"),
):
    """
    Retrieve and explain a single decision with the exact rule path + numbers.

    Lookup priority
    ───────────────
    1. trade_id  → resolve to order_id via DB, then search traces
    2. order_id  → searches entry_order_id then exit_order_id in traces
    3. market_ticker [+ model]  → most-recent record for that ticker

    Response includes every numeric input (edge, confidence, persistence, EV,
    Kelly, spread, depth) plus the full eligibility_checks and risk_checks dicts
    showing exactly which rules passed/failed with their threshold values, plus a
    concise human_summary.
    """
    # ── Resolve trade_id → order_id via MongoDB (best-effort) ──────────────
    if trade_id and not order_id:
        try:
            import server as _srv
            db = getattr(_srv, "db", None)
            if db is None:
                raise HTTPException(
                    status_code=503,
                    detail="Database not available; cannot resolve trade_id."
                )

            trade_doc = None
            for _col in ("trades", "orders", "live_orders"):
                trade_doc = await db[_col].find_one(
                    {"$or": [
                        {"id": trade_id},
                        {"trade_id": trade_id},
                        {"order_id": trade_id},
                    ]},
                    {"_id": 0, "id": 1, "order_id": 1, "trade_id": 1,
                     "entry_order_id": 1, "exit_order_id": 1,
                     "market_ticker": 1, "created_at": 1}
                )
                if trade_doc:
                    break
            if trade_doc is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No order/trade found with trade_id='{trade_id}'."
                )
            # Prefer entry_order_id, then exit_order_id, then the id itself
            order_id = (
                trade_doc.get("entry_order_id")
                or trade_doc.get("exit_order_id")
                or trade_doc.get("order_id")
                or trade_doc.get("id")
            )
            # Also infer date from created_at if not supplied
            if date is None and trade_doc.get("created_at"):
                try:
                    dt = trade_doc["created_at"]
                    if hasattr(dt, "strftime"):
                        date = dt.strftime("%Y%m%d")
                except Exception:
                    pass
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"[decisions] trade_id DB lookup failed: {exc}")
            # Fall back: use trade_id as a raw order_id
            order_id = trade_id

    if not order_id and not market_ticker:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: order_id, market_ticker, trade_id"
        )

    # Read full day (no limit, no model pre-filter when searching by order_id)
    all_records = _read_records(
        date_str=date,
        model=model if not order_id else None,
        limit=50_000,
        reverse=True,
    )

    match: Optional[Dict] = None

    if order_id:
        oid = order_id.strip()
        for rec in all_records:
            if rec.get("entry_order_id") == oid or rec.get("exit_order_id") == oid:
                match = rec
                break
        if match is None:
            # ── Fallback: look up in MongoDB trades collection ────────────────
            match = await _fallback_from_db(order_id=oid)
        if match is None:
            raise HTTPException(
                status_code=404,
                detail=f"No decision found with order_id='{oid}' "
                       f"for date {date or 'today'}."
            )
    else:
        ticker = market_ticker.strip()
        for rec in all_records:
            if (rec.get("market_ticker") or "").upper() == ticker.upper():
                match = rec
                break
        if match is None:
            model_hint = f" model={model}" if model else ""
            raise HTTPException(
                status_code=404,
                detail=f"No decision found for market_ticker='{ticker}'"
                       f"{model_hint} on date {date or 'today'}."
            )

    return _enrich(match)


@router.get("/dates")
def list_trace_dates():
    """
    Return a list of dates for which decision-trace JSONL files exist.
    Useful for the debug-bundle UI to show available days.
    """
    if not _LOG_DIR.exists():
        return {"dates": []}
    dates = []
    for p in sorted(_LOG_DIR.glob("decision_trace_*.jsonl"), reverse=True):
        stem = p.stem  # decision_trace_YYYYMMDD
        compact = stem.replace("decision_trace_", "")
        try:
            dt = datetime.strptime(compact, "%Y%m%d")
            dates.append({
                "date_compact": compact,
                "date_iso": dt.strftime("%Y-%m-%d"),
                "size_bytes": p.stat().st_size,
            })
        except ValueError:
            continue
    return {"count": len(dates), "dates": dates}
