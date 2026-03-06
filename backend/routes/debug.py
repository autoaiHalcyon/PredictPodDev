"""
routes/debug.py
────────────────────────────────────────────────────────────────────────────────
Debug-bundle endpoint.

GET /api/debug/bundle?date=YYYY-MM-DD
    Returns a ZIP file containing all diagnostic artefacts for the requested day:

    decision_trace_YYYYMMDD.jsonl       (from disk: logs/decision_traces/)
    orders_YYYYMMDD.jsonl               (from DB:   orders / order_events collection)
    audit_YYYYMMDD.jsonl                (from DB:   trading_audit_log)
    metrics_snapshots/<day>/*.json      (from disk: logs/metrics_snapshots/)
    config_versions/<day>/*.json        (from DB:   config_versions)
    current_config.json                 (from disk: strategies/configs/ A+B+C merged)

The endpoint is intentionally synchronous-safe: all DB queries are
awaited, file I/O uses stdlib, zip built in memory.
"""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone, date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])

# ── Filesystem roots (relative to this file: backend/routes/) ─────────────
_BACKEND_DIR    = Path(__file__).resolve().parent.parent   # backend/
_LOG_DIR        = _BACKEND_DIR / "logs"
_TRACES_DIR     = _LOG_DIR / "decision_traces"
_SNAPSHOTS_DIR  = _LOG_DIR / "metrics_snapshots"
_CONFIGS_DIR    = _BACKEND_DIR / "strategies" / "configs"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str: Optional[str]) -> _date:
    """Parse 'YYYY-MM-DD' → date.  Default: today UTC."""
    if not date_str:
        return datetime.now(timezone.utc).date()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."
        )


def _day_range(d: _date):
    """Return (start_dt, end_dt) as UTC datetimes bracketing *d*."""
    from datetime import timedelta
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end   = start + timedelta(days=1)
    return start, end


def _date_compact(d: _date) -> str:
    return d.strftime("%Y%m%d")


def _json_default(obj):
    """Fallback JSON serialiser for datetime / ObjectId-like objects."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _to_jsonl(records: List[Dict]) -> bytes:
    lines = (json.dumps(r, default=_json_default) for r in records)
    return "\n".join(lines).encode("utf-8")


# ── Disk sources ──────────────────────────────────────────────────────────

def _read_decision_trace(d: _date) -> Optional[bytes]:
    path = _TRACES_DIR / f"decision_trace_{_date_compact(d)}.jsonl"
    if not path.exists():
        return None
    return path.read_bytes()


def _read_metrics_snapshots(d: _date) -> List[Dict]:
    """
    Collect all metrics_snapshots JSON files whose filename contains
    the date suffix YYYYMMDD or whose content timestamp matches the day.
    """
    if not _SNAPSHOTS_DIR.exists():
        return []
    compact = _date_compact(d)
    files: List[Dict] = []
    for p in sorted(_SNAPSHOTS_DIR.glob("*.json")):
        # Include if filename contains the date or it's the 24h summary for that day
        if compact in p.name or p.name == "24h_summary_report.json":
            try:
                content = json.loads(p.read_text(encoding="utf-8"))
                files.append({"_source_file": p.name, **content})
            except Exception as exc:
                logger.warning(f"[debug_bundle] Cannot parse {p}: {exc}")
    return files


def _read_current_configs() -> Dict[str, Any]:
    """Read model_1 + model_2 configs and merge."""
    out: Dict[str, Any] = {}
    for fname in ("model_1_enhanced_clv.json", "model_2_strong_favorite.json"):
        p = _CONFIGS_DIR / fname
        if p.exists():
            try:
                out[fname] = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"[debug_bundle] Cannot read {p}: {exc}")
    return out


# ── DB sources (async, injected via server globals) ──────────────────────

def _get_db():
    """Pull the global db handle set up in server.py lifespan."""
    try:
        import server
        return server.db
    except Exception:
        return None


async def _fetch_orders(d: _date) -> List[Dict]:
    """Fetch trades for the given day from MongoDB."""
    db = _get_db()
    if db is None:
        return []
    start, end = _day_range(d)
    try:
        # Trades are stored in the 'trades' collection by TradeRepository.
        # Also try 'live_orders' (OrderRepository) and fall back to string
        # comparison for any docs whose created_at was serialised as ISO str.
        results: List[Dict] = []
        for col_name in ("trades", "live_orders"):
            col = db[col_name]
            # Datetime-native query (Motor stores naive datetimes as UTC BSON)
            cursor = col.find(
                {"$or": [
                    {"created_at": {"$gte": start, "$lt": end}},
                    {"timestamp":  {"$gte": start, "$lt": end}},
                ]},
                {"_id": 0}
            ).sort("created_at", 1)
            batch = await cursor.to_list(length=10_000)
            results.extend(batch)
        return results
    except Exception as exc:
        logger.warning(f"[debug_bundle] orders fetch error: {exc}")
        return []


async def _fetch_audit(d: _date) -> List[Dict]:
    """Fetch trading_audit_log entries for the given day from MongoDB."""
    db = _get_db()
    if db is None:
        return []
    start, end = _day_range(d)
    try:
        cursor = db.trading_audit_log.find(
            {"$or": [
                {"timestamp":  {"$gte": start, "$lt": end}},
                {"created_at": {"$gte": start, "$lt": end}},
            ]},
            {"_id": 0}
        ).sort("timestamp", 1)
        records = await cursor.to_list(length=50_000)
        return records
    except Exception as exc:
        logger.warning(f"[debug_bundle] audit fetch error: {exc}")
        return []


async def _fetch_config_versions(d: _date) -> List[Dict]:
    """Fetch config_versions created/updated on the given day from MongoDB."""
    db = _get_db()
    if db is None:
        return []
    start, end = _day_range(d)
    try:
        cursor = db.config_versions.find(
            {"$or": [
                {"created_at":  {"$gte": start, "$lt": end}},
                {"updated_at":  {"$gte": start, "$lt": end}},
                {"activated_at":{"$gte": start, "$lt": end}},
            ]},
            {"_id": 0}
        ).sort("created_at", 1)
        records = await cursor.to_list(length=1_000)
        return records
    except Exception as exc:
        logger.warning(f"[debug_bundle] config_versions fetch error: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Bundle assembly
# ─────────────────────────────────────────────────────────────────────────────

async def _build_zip(d: _date) -> io.BytesIO:
    """Assemble all artefacts into an in-memory ZIP and return the buffer."""
    compact = _date_compact(d)
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        # 1. decision_trace_YYYYMMDD.jsonl  (disk)
        trace_bytes = _read_decision_trace(d)
        if trace_bytes:
            zf.writestr(f"decision_trace_{compact}.jsonl", trace_bytes)

        # 2. orders_YYYYMMDD.jsonl  (DB)
        orders = await _fetch_orders(d)
        zf.writestr(f"orders_{compact}.jsonl", _to_jsonl(orders))

        # 3. audit_YYYYMMDD.jsonl  (DB)
        audit = await _fetch_audit(d)
        zf.writestr(f"audit_{compact}.jsonl", _to_jsonl(audit))

        # 4. metrics_snapshots/<compact>/*.json  (disk)
        snapshots = _read_metrics_snapshots(d)
        for snap in snapshots:
            fname = snap.get("_source_file", "snapshot_unknown.json")
            payload = {k: v for k, v in snap.items() if k != "_source_file"}
            zf.writestr(
                f"metrics_snapshots/{compact}/{fname}",
                json.dumps(payload, indent=2, default=_json_default).encode("utf-8")
            )

        # 5. config_versions/<compact>/*.json  (DB)
        config_versions = await _fetch_config_versions(d)
        for idx, cv in enumerate(config_versions):
            model  = cv.get("model_id") or cv.get("strategy_id") or "unknown"
            ver    = cv.get("version_id") or cv.get("version") or str(idx + 1)
            fname  = f"config_versions/{compact}/config_{model}_v{ver}.json"
            zf.writestr(fname, json.dumps(cv, indent=2, default=_json_default).encode("utf-8"))

        # 6. current_config.json  (disk — A/B/C merged)
        current = _read_current_configs()
        zf.writestr(
            "current_config.json",
            json.dumps(current, indent=2, default=_json_default).encode("utf-8")
        )

        # 7. Manifest
        manifest = {
            "exported_at":      datetime.now(timezone.utc).isoformat(),
            "date":             d.isoformat(),
            "decision_traces":  1 if trace_bytes else 0,
            "orders":           len(orders),
            "audit_events":     len(audit),
            "metrics_snapshots":len(snapshots),
            "config_versions":  len(config_versions),
            "config_files":     list(current.keys()),
        }
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, default=_json_default).encode("utf-8")
        )

    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/bundle")
async def export_debug_bundle(
    date: Optional[str] = Query(
        None,
        description="Date in YYYY-MM-DD format. Defaults to today UTC.",
        example="2026-03-02",
    )
):
    """
    Build and return a ZIP file containing all diagnostic artefacts for the
    requested date:

    - decision_trace_YYYYMMDD.jsonl
    - orders_YYYYMMDD.jsonl
    - audit_YYYYMMDD.jsonl
    - metrics_snapshots/<date>/*.json
    - config_versions/<date>/*.json
    - current_config.json
    - manifest.json
    """
    d = _parse_date(date)
    compact = _date_compact(d)

    logger.info(f"[debug_bundle] Building bundle for {d.isoformat()}")
    zip_buf = await _build_zip(d)

    filename = f"debug_bundle_{compact}.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Bundle-Date": d.isoformat(),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# One-time audit backfill — populates trading_audit_log for trades that
# pre-date the automatic write added to POST /api/trades.
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/backfill-audit")
async def backfill_audit():
    """
    Back-fill trading_audit_log entries for all trades in db.trades that
    don't already have a corresponding audit record.  Safe to call multiple
    times — already-present entries are skipped via order_id deduplication.
    """
    import uuid as _uuid
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available.")

    trades = await db.trades.find({}, {"_id": 0}).to_list(length=10_000)
    inserted = 0
    skipped  = 0

    for t in trades:
        order_id = t.get("id") or str(_uuid.uuid4())
        if await db.trading_audit_log.find_one({"order_id": order_id}):
            skipped += 1
            continue

        price_f = float(t.get("avg_fill_price") or t.get("price") or 0)
        qty     = int(t.get("quantity") or 0)
        created = t.get("created_at") or datetime.now(timezone.utc)
        if isinstance(created, str):
            try:    created = datetime.fromisoformat(created)
            except: created = datetime.now(timezone.utc)

        await db.trading_audit_log.insert_one({
            "id":               str(_uuid.uuid4()),
            "order_id":         order_id,
            "market_id":        t.get("market_id") or "",
            "market_ticker":    t.get("market_id") or "",
            "game_id":          t.get("game_id"),
            "side":             t.get("side") or "",
            "action":           t.get("direction") or "buy",
            "order_type":       t.get("order_type") or "market",
            "quantity":         qty,
            "price_cents":      round(price_f * 100),
            "edge":             float(t.get("edge_at_entry") or 0),
            "status":           t.get("status") or "filled",
            "fill_price_cents": round(price_f * 100),
            "filled_quantity":  int(t.get("filled_quantity") or qty),
            "cost_basis_cents": round(price_f * 100 * qty),
            "fees_cents":       round(float(t.get("fees") or 0) * 100),
            "strategy":         t.get("strategy"),
            "signal_type":      t.get("signal_type"),
            "game_title":       t.get("game_title"),
            "market_name":      t.get("market_name"),
            "league":           t.get("league"),
            "is_paper":         t.get("is_paper", True),
            "timestamp":        created,
            "created_at":       created,
        })
        inserted += 1

    total = await db.trading_audit_log.count_documents({})
    return {
        "status":   "ok",
        "inserted": inserted,
        "skipped":  skipped,
        "total_audit_docs": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Replay endpoint (AC3) — deterministic re-run of strategy rules on snapshots
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/replay")
def replay_decisions(
    date: str = Query(
        ...,
        description="Date to replay in YYYY-MM-DD format.",
        example="2026-03-02",
    ),
    model: str = Query(
        "A",
        description="Strategy model to replay: A, B, or C.",
        regex="^[ABCabc]$",
    ),
    config: Optional[str] = Query(
        None,
        description=(
            "Config JSON filename (basename only) inside strategies/configs/, "
            "e.g. 'model_1_enhanced_clv.json'. Defaults to the model's live config."
        ),
    ),
    synthetic: bool = Query(
        False,
        description="Force synthetic data even if a real trace exists (for testing).",
    ),
):
    """
    Replay strategy-rule evaluation on the stored decision-trace snapshot for
    *date* + *model*, using the config that was active that day (or a specified
    config override).

    Returns a structured JSON result \u2014 identical logic to the CLI
    ``python backend/tools/replay.py --date <date> --model <model>``.

    Determinism guarantee: the replay reads the immutable JSONL snapshot
    and runs the exact same rule-evaluation code as the live loop, with
    decision-tracer writes suppressed so no new files are touched.

    Response fields
    ───────────────
    date, model, config_label, total_ticks, enters, exits, holds, blocks,
    total_pnl, baseline_pnl, pnl_delta, win_count, loss_count, win_rate_pct,
    synthetic (bool), trades [ {market_id, side, qty, entry, exit, pnl, status} ],
    entry_reasons { reason: count }, reject_reasons { reason: count }
    """
    # ── Import replay internals (lazy, avoids polluting module-level import) ─
    import sys as _sys
    _TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
    _BACKEND   = Path(__file__).resolve().parent.parent
    for _p in (str(_TOOLS_DIR), str(_BACKEND)):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)

    try:
        from tools.replay import (
            _load_traces,
            _make_synthetic_records,
            _run_replay,
            _DEFAULT_CONFIGS,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot import replay module: {exc}"
        )

    # ── Validate date ──────────────────────────────────────────────────────
    d = _parse_date(date)   # raises 422 on bad format
    date_iso = d.isoformat()
    model_upper = model.upper()

    # ── Resolve config path ───────────────────────────────────────────────
    if config:
        cfg_path = _CONFIGS_DIR / config
        if not cfg_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Config file not found: strategies/configs/{config}"
            )
        cfg_label = cfg_path.stem
    else:
        cfg_path = _DEFAULT_CONFIGS.get(model_upper)
        if not cfg_path or not cfg_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No default config found for Model {model_upper}."
            )
        cfg_label = "default"

    # ── Load traces ───────────────────────────────────────────────────────
    records = _load_traces(date_iso, model_upper)
    used_synthetic = False
    if not records or synthetic:
        records = _make_synthetic_records(date_iso, model_upper)
        used_synthetic = True

    # ── Run replay (synchronous, decision-tracer suppressed inside) ────────
    try:
        result = _run_replay(
            records=records,
            model_letter=model_upper,
            config_path=str(cfg_path),
            config_label=cfg_label,
            date_str=date_iso,
        )
    except Exception as exc:
        logger.exception(f"[debug_replay] Replay failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Replay error: {exc}")

    # ── Serialise result ──────────────────────────────────────────────────
    closed = result.closed_trades
    win_rate = round((result.win_count / len(closed) * 100), 1) if closed else 0.0

    trades_out = [
        {
            "market_id":    t.market_id,
            "game_id":      t.game_id,
            "side":         t.side,
            "quantity":     t.quantity,
            "entry_price":  t.entry_price,
            "exit_price":   t.exit_price,
            "entry_ts":     t.entry_ts,
            "exit_ts":      t.exit_ts,
            "entry_reason": t.entry_reason,
            "exit_reason":  t.exit_reason,
            "pnl":          t.pnl,
            "status":       "OPEN" if t.is_open else ("WIN" if t.pnl > 0 else "LOSS"),
        }
        for t in result.trades
    ]

    return {
        "date":            date_iso,
        "model":           model_upper,
        "config_label":    cfg_label,
        "config_path":     str(cfg_path),
        "synthetic":       used_synthetic,
        "total_ticks":     result.total_ticks,
        "enters":          result.enters,
        "exits":           result.exits,
        "holds":           result.holds,
        "blocks":          result.blocks,
        "total_pnl":       result.total_pnl,
        "baseline_pnl":    result.baseline_pnl,
        "pnl_delta":       round(result.total_pnl - result.baseline_pnl, 4),
        "win_count":       result.win_count,
        "loss_count":      result.loss_count,
        "open_trades":     len(result.open_trades),
        "win_rate_pct":    win_rate,
        "trades":          trades_out,
        "entry_reasons":   dict(result.entry_reasons),
        "reject_reasons":  dict(result.reject_reasons),
    }
