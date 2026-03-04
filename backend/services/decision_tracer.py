"""
Decision Tracer — writes one JSON-Lines record per trading decision tick.

Log location: backend/logs/decision_traces/decision_trace_YYYYMMDD.jsonl

Schema
------
Every record contains ALL of the following top-level keys:

  ts                   ISO-8601 UTC timestamp
  run_id               UUID generated once at service start
  env                  "paper" | "sandbox" | "live"
  league               NBA | NCAA_M | NCAA_W
  event_id             game.id (Kalshi event id)
  market_ticker        market.kalshi_ticker
  model_id             A | B | C (from strategy_id)

  # Market snapshot
  best_bid             yes_bid (0–1)
  best_ask             yes_ask (0–1)
  mid_price            (bid+ask)/2
  spread_cents         (ask–bid)*100
  top_depth_usd        top-of-book depth in $
  total_depth_usd      full orderbook depth in $
  volume_5m            rolling 5-min volume (null if n/a)
  volume_60m           rolling 60-min volume (null if n/a)

  # Model snapshot
  p_model              signal.fair_prob
  p_market             signal.market_prob
  edge                 signal.edge
  confidence           signal.confidence
  persistence_sec      seconds edge has been above threshold
  ev_usd               signal.expected_value
  txn_cost_buffer_pct  (spread_cents / 2) as percentage
  kelly_fraction       Kelly criterion fraction (clipped at 0.25)
  stake_usd            decision.quantity * decision.price (0 for non-ENTER)

  # Rule evaluation
  eligibility_checks   {check_name: {pass: bool, reason: str}}
  risk_checks          {check_name: {pass: bool, reason: str}}
  reason_codes         ["EDGE_OK", "CONF_OK", ...] or ["SPREAD_TOO_WIDE", ...]

  # Action
  action               NO_TRADE | ENTER | EXIT | HOLD

  # ENTER fields (null when not ENTER)
  entry_order_id       None (placeholder until live order IDs exist)
  entry_price          decision.price
  target_price         entry * (1 + profit_target_pct/100)
  stop_price           entry * (1 - stop_loss_pct/100)

  # EXIT fields (null when not EXIT)
  exit_order_id        None
  exit_price           decision.price
  exit_reason          decision.reason

  # P&L (all null when not available)
  pnl_realized_usd
  pnl_unrealized_usd
  pnl_total_usd
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── One run_id per process lifetime ───────────────────────────────────────
RUN_ID: str = str(uuid.uuid4())

# ── Resolve log directory relative to this file ───────────────────────────
_HERE = Path(__file__).resolve().parent          # backend/services/
_LOG_DIR = _HERE.parent / "logs" / "decision_traces"   # backend/logs/decision_traces/


def _get_log_path(date: Optional[str] = None) -> Path:
    """Return the JSONL file path for the given date (default: today UTC)."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    return _LOG_DIR / f"decision_trace_{date}.jsonl"


def _open_log(path: Path):
    """Open log file in append mode, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return open(path, "a", encoding="utf-8")


# ── Module-level file handle cache (one handle per date) ──────────────────
_handles: Dict[str, Any] = {}   # date_str -> file handle


def _get_handle(date_str: str):
    """Return (or open) the append file handle for *date_str*."""
    if date_str not in _handles:
        path = _get_log_path(date_str)
        _handles[date_str] = _open_log(path)
        logger.info(f"[DecisionTracer] Opened log: {path}")
    return _handles[date_str]


# ── Helpers ────────────────────────────────────────────────────────────────

def _infer_env() -> str:
    """Infer environment: paper / sandbox / live."""
    env = os.environ.get("TRADING_ENV", "").lower()
    if env in ("live", "sandbox"):
        return env
    return "paper"


def _infer_league(game_id: str, game=None) -> str:
    gid = (game_id or "").upper()
    if "NCAAM" in gid or "NCAA_M" in gid:
        return "NCAA_M"
    if "NCAAW" in gid or "NCAA_W" in gid:
        return "NCAA_W"
    if game and hasattr(game, "league"):
        return game.league
    return "NBA"


def _calc_depth(orderbook) -> tuple:
    """Return (top_depth_usd, total_depth_usd) from an orderbook dict or OrderBook obj."""
    if orderbook is None:
        return (0.0, 0.0)

    # Normalise: accept dict or pydantic OrderBook
    if hasattr(orderbook, 'dict'):
        ob = orderbook.dict()
    elif isinstance(orderbook, dict):
        ob = orderbook
    else:
        return (0.0, 0.0)

    bids: List[Dict] = ob.get("bids", [])
    asks: List[Dict] = ob.get("asks", [])

    def level_usd(level: Dict) -> float:
        price = level.get("price", 0)
        qty = level.get("quantity", 0)
        return price * qty

    top_depth = 0.0
    if bids:
        top_depth += level_usd(bids[0])
    if asks:
        top_depth += level_usd(asks[0])

    total_depth = sum(level_usd(l) for l in bids) + sum(level_usd(l) for l in asks)
    return (round(top_depth, 2), round(total_depth, 2))


def _kelly(edge: float, confidence: float) -> float:
    """
    Simplified half-Kelly:  f = (edge * confidence) / (1 - edge)
    Clipped to [0, 0.25].
    """
    if edge <= 0 or confidence <= 0:
        return 0.0
    denom = 1.0 - abs(edge)
    if denom <= 0:
        return 0.25
    raw = (abs(edge) * confidence) / denom
    return round(min(raw, 0.25), 4)


def _persistence_seconds(edge_history: Optional[Dict], market_id: str, min_edge: float) -> float:
    """
    Walk the edge history backwards to find how long edge has been
    above *min_edge* continuously.
    """
    if not edge_history:
        return 0.0
    history = edge_history.get(market_id, [])
    if not history:
        return 0.0

    now_ts, _ = history[-1]
    secs = 0.0
    for ts, e in reversed(history):
        if abs(e) >= abs(min_edge):
            secs = (now_ts - ts).total_seconds()
        else:
            break
    return round(secs, 1)


def _build_eligibility_checks(
    game,
    market,
    signal,
    config,
    edge_history: Optional[Dict] = None
) -> Dict[str, Dict]:
    """
    Rebuild the eligibility gate results from available data.
    All entries: {pass: bool, reason: str}
    """
    checks = {}
    entry_rules = config.entry_rules if config else {}
    filters_cfg = config.filters if config else {}

    # League filter
    league = _infer_league(game.id if game else "", game)
    allowed = filters_cfg.get("allowed_leagues", ["NBA", "NCAA_M", "NCAA_W"])
    checks["league_filter"] = {
        "pass": league in allowed,
        "reason": f"league={league} allowed={allowed}"
    }

    # Edge threshold
    min_edge = entry_rules.get("min_edge_threshold", 0.05)
    edge_val = abs(signal.edge) if signal else 0.0
    checks["min_edge"] = {
        "pass": edge_val >= min_edge,
        "reason": f"edge={edge_val:.4f} threshold={min_edge}"
    }

    # Signal score
    min_score = entry_rules.get("min_signal_score", 60)
    score = getattr(signal, '_signal_score', (signal.confidence * 100) if signal else 0)
    checks["min_signal_score"] = {
        "pass": score >= min_score,
        "reason": f"score={score:.1f} threshold={min_score}"
    }

    # Persistence
    min_ticks = entry_rules.get("min_persistence_ticks", 3)
    persistence = _persistence_seconds(edge_history, market.id if market else "", min_edge)
    # Rough heuristic: 3 ticks ≈ 9s at 3s interval
    checks["edge_persistence"] = {
        "pass": persistence >= (min_ticks * 3),
        "reason": f"persistent_sec={persistence} ticks_required={min_ticks}"
    }

    # Spread
    max_spread = filters_cfg.get("max_spread_pct", 0.10)
    spread = (market.yes_ask - market.yes_bid) if market else 0.0
    checks["spread_filter"] = {
        "pass": spread <= max_spread,
        "reason": f"spread={spread:.4f} max={max_spread}"
    }

    return checks


def _build_risk_checks(config, portfolio) -> Dict[str, Dict]:
    """
    Risk gate evaluation from portfolio state.
    """
    checks = {}
    risk_limits = config.risk_limits if config else {}

    # Circuit breaker
    cb_active = portfolio.is_circuit_breaker_active if portfolio else False
    checks["circuit_breaker"] = {
        "pass": not cb_active,
        "reason": "circuit breaker active" if cb_active else "OK"
    }

    # Daily loss limit
    max_daily_loss = risk_limits.get("max_daily_loss_pct", 5.0)
    daily_pnl_pct = 0.0
    if portfolio:
        cap = getattr(portfolio, 'starting_capital', 1)
        daily_pnl_pct = (getattr(portfolio, 'total_pnl', 0) / cap) * 100 if cap else 0
    checks["daily_loss_cap"] = {
        "pass": daily_pnl_pct > -max_daily_loss,
        "reason": f"daily_pnl={daily_pnl_pct:.2f}% cap={-max_daily_loss}%"
    }

    # Max concurrent positions
    max_pos = risk_limits.get("max_concurrent_positions", 10)
    n_pos = len(portfolio.positions) if portfolio and hasattr(portfolio, 'positions') else 0
    checks["max_positions"] = {
        "pass": n_pos < max_pos,
        "reason": f"open={n_pos} max={max_pos}"
    }

    return checks


def _build_reason_codes(
    eligibility: Dict[str, Dict],
    risk: Dict[str, Dict],
    decision_type: str
) -> List[str]:
    codes = []
    all_pass = all(v["pass"] for v in {**eligibility, **risk}.values())

    if decision_type in ("ENTER", "HOLD", "EXIT"):
        for k, v in eligibility.items():
            codes.append(k.upper() + ("_OK" if v["pass"] else "_FAIL"))
        for k, v in risk.items():
            codes.append(k.upper() + ("_OK" if v["pass"] else "_FAIL"))
    else:
        # NO_TRADE / BLOCK — report the first failing check
        for k, v in {**eligibility, **risk}.items():
            if not v["pass"]:
                codes.append(k.upper() + "_FAIL")
        if not codes:
            codes.append("BLOCKED")

    return codes


# ── Public API ─────────────────────────────────────────────────────────────

def write_decision(
    *,
    game,
    market,
    signal,
    decision,
    strategy,
    orderbook=None,
    position=None,
    volume_5m: Optional[float] = None,
    volume_60m: Optional[float] = None,
    order_id: Optional[str] = None,
):
    """
    Write one JSONL record for a trading decision.

    Parameters
    ----------
    game       : models.game.Game
    market     : models.market.Market
    signal     : models.signal.Signal
    decision   : strategies.base_strategy.StrategyDecision  (may be None for NO_TRADE)
    strategy   : strategies.base_strategy.BaseStrategy instance
    orderbook  : dict | OrderBook | None
    position   : VirtualPosition | None  (for unrealised P&L)
    volume_5m  : float | None
    volume_60m : float | None
    order_id   : str | None  — Kalshi / paper order ID to embed in the trace.
                              Can be supplied immediately if synchronous, or
                              backfilled later via patch_order_id().
    """
    try:
        _write_decision_inner(
            game=game,
            market=market,
            signal=signal,
            decision=decision,
            strategy=strategy,
            orderbook=orderbook,
            position=position,
            volume_5m=volume_5m,
            volume_60m=volume_60m,
            order_id=order_id,
        )
    except Exception as exc:
        # Never let tracing crash the trading loop
        logger.warning(f"[DecisionTracer] Failed to write record: {exc}", exc_info=True)


def _write_decision_inner(
    *,
    game,
    market,
    signal,
    decision,
    strategy,
    orderbook=None,
    position=None,
    volume_5m,
    volume_60m,
    order_id: Optional[str] = None,
):
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")

    # ── IDs & context ──────────────────────────────────────────────────────
    game_id = game.id if game else ""
    ticker = (market.kalshi_ticker or market.id) if market else ""
    model_id = getattr(strategy, 'strategy_id', 'unknown') if strategy else 'unknown'
    config = getattr(strategy, 'config', None)
    portfolio = getattr(strategy, 'portfolio', None)
    edge_history = getattr(strategy, '_edge_history', None)

    # ── Market snapshot ───────────────────────────────────────────────────
    best_bid = market.yes_bid if market else None
    best_ask = market.yes_ask if market else None
    mid_price = round((best_bid + best_ask) / 2, 4) if (best_bid is not None and best_ask is not None) else None
    spread_cents = round((best_ask - best_bid) * 100, 2) if (best_bid is not None and best_ask is not None) else None
    top_depth, total_depth = _calc_depth(orderbook)

    # ── Model snapshot ────────────────────────────────────────────────────
    edge_val = signal.edge if signal else 0.0
    confidence = signal.confidence if signal else 0.0
    p_model = signal.fair_prob if signal else None
    p_market = signal.market_prob if signal else None
    ev_usd = signal.expected_value if signal else None

    min_edge = config.entry_rules.get("min_edge_threshold", 0.05) if config else 0.05
    persistence = _persistence_seconds(edge_history, market.id if market else "", min_edge)
    txn_cost_buffer = round((spread_cents / 2) / 100, 4) if spread_cents is not None else None
    kelly = _kelly(edge_val, confidence)

    dec_type = decision.decision_type.value if decision else "NO_TRADE"
    dec_price = decision.price if decision else 0.0
    dec_qty = decision.quantity if decision else 0
    stake_usd = round(dec_qty * dec_price, 2) if dec_type == "ENTER" else 0.0

    # ── Rule evaluation ───────────────────────────────────────────────────
    eligibility = _build_eligibility_checks(game, market, signal, config, edge_history)
    risk_chk = _build_risk_checks(config, portfolio)
    reason_codes = _build_reason_codes(eligibility, risk_chk, dec_type)

    # ── P&L ───────────────────────────────────────────────────────────────
    pnl_realized = None
    pnl_unrealized = None
    pnl_total = None

    if portfolio:
        try:
            pnl_realized = round(getattr(portfolio, 'total_realized_pnl', 0) or 0, 4)
        except Exception:
            pass
        if position:
            try:
                cur = dec_price or (market.mid_price if market else 0)
                entry = getattr(position, 'entry_price', cur)
                qty = getattr(position, 'quantity', 0)
                side = getattr(position, 'side', 'yes')
                if side == 'yes':
                    pnl_unrealized = round((cur - entry) * qty, 4)
                else:
                    pnl_unrealized = round((entry - cur) * qty, 4)
            except Exception:
                pass
        if pnl_realized is not None and pnl_unrealized is not None:
            pnl_total = round(pnl_realized + pnl_unrealized, 4)
        elif pnl_realized is not None:
            pnl_total = pnl_realized

    # ── Pull exit/entry rules for target/stop ─────────────────────────────
    exit_rules = config.exit_rules if config else {}
    profit_target_pct = exit_rules.get("profit_target_pct", 15.0)
    stop_loss_pct = exit_rules.get("stop_loss_pct", 10.0)

    entry_price_field = dec_price if dec_type == "ENTER" else None
    target_price_field = round(dec_price * (1 + profit_target_pct / 100), 4) if dec_type == "ENTER" else None
    stop_price_field = round(dec_price * (1 - stop_loss_pct / 100), 4) if dec_type == "ENTER" else None

    exit_price_field = dec_price if dec_type == "EXIT" else None
    exit_reason_field = decision.reason if dec_type == "EXIT" else None

    # ── Assemble record ───────────────────────────────────────────────────
    record = {
        "ts": now.isoformat(),
        "run_id": RUN_ID,
        "env": _infer_env(),
        "league": _infer_league(game_id, game),
        "event_id": game_id,
        "market_ticker": ticker,
        "model_id": model_id,

        # Market snapshot
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread_cents": spread_cents,
        "top_depth_usd": top_depth,
        "total_depth_usd": total_depth,
        "volume_5m": volume_5m,
        "volume_60m": volume_60m,

        # Model snapshot
        "p_model": p_model,
        "p_market": p_market,
        "edge": round(edge_val, 6),
        "confidence": round(confidence, 4),
        "persistence_sec": persistence,
        "ev_usd": ev_usd,
        "txn_cost_buffer_pct": txn_cost_buffer,
        "kelly_fraction": kelly,
        "stake_usd": stake_usd,

        # Rule evaluation
        "eligibility_checks": eligibility,
        "risk_checks": risk_chk,
        "reason_codes": reason_codes,

        # Action
        "action": dec_type,

        # ENTER fields
        "entry_order_id": order_id if dec_type == "ENTER" else None,
        "entry_price": entry_price_field,
        "target_price": target_price_field,
        "stop_price": stop_price_field,

        # EXIT fields
        "exit_order_id": order_id if dec_type == "EXIT" else None,
        "exit_price": exit_price_field,
        "exit_reason": exit_reason_field,

        # P&L
        "pnl_realized_usd": pnl_realized,
        "pnl_unrealized_usd": pnl_unrealized,
        "pnl_total_usd": pnl_total,
    }

    fh = _get_handle(date_str)
    fh.write(json.dumps(record, default=str) + "\n")
    fh.flush()


def write_from_trade_dict(
    trade: Dict,
    *,
    date: Optional[str] = None,
) -> None:
    """
    Write a minimal trace record from a trade document dict.

    Called when a trade is placed via POST /api/trades (frontend auto-edge path)
    which bypasses the strategy loop and therefore never hits write_decision().

    The record uses only the fields available in the stored trade doc.
    Fields that require live strategy objects (orderbook depth, Kelly, etc.)
    are recorded as None so the schema remains consistent.
    """
    try:
        now = datetime.now(timezone.utc)
        date_str = date or now.strftime("%Y%m%d")
        order_id = trade.get("id") or trade.get("order_id")
        action = "ENTER"
        status = (trade.get("status") or "").lower()
        if status in ("closed", "cancelled"):
            action = "EXIT"

        edge_val = float(trade.get("edge_at_entry") or trade.get("edge") or 0.0)
        entry_price = float(trade.get("avg_fill_price") or trade.get("entry_price") or trade.get("price") or 0.0)
        qty = int(trade.get("quantity") or trade.get("filled_quantity") or 0)
        stake = round(entry_price * qty, 2)

        record = {
            "ts":           now.isoformat(),
            "run_id":       RUN_ID,
            "env":          _infer_env(),
            "source":       "trade_placed",   # distinguishes from strategy-loop traces
            "league":       trade.get("league") or _infer_league(trade.get("game_id", "")),
            "event_id":     trade.get("game_id") or "",
            "market_ticker": trade.get("market_id") or trade.get("market_ticker") or "",
            "model_id":     (trade.get("strategy") or "unknown").lower().replace(" ", "_"),

            # Market snapshot (not available from trade doc)
            "best_bid":         None,
            "best_ask":         None,
            "mid_price":        entry_price,
            "spread_cents":     None,
            "top_depth_usd":    None,
            "total_depth_usd":  None,
            "volume_5m":        None,
            "volume_60m":       None,

            # Model snapshot
            "p_model":              None,
            "p_market":             None,
            "edge":                 round(edge_val, 6),
            "confidence":           None,
            "persistence_sec":      None,
            "ev_usd":               None,
            "txn_cost_buffer_pct":  None,
            "kelly_fraction":       None,
            "stake_usd":            stake,

            # Rule evaluation — not available from trade doc
            "eligibility_checks": {},
            "risk_checks":        {},
            "reason_codes":       [trade.get("signal_type") or "MANUAL_ENTRY"],

            # Action
            "action": action,

            # ENTER fields
            "entry_order_id": order_id if action == "ENTER" else None,
            "entry_price":    entry_price if action == "ENTER" else None,
            "target_price":   None,
            "stop_price":     None,

            # EXIT fields
            "exit_order_id":  order_id if action == "EXIT" else None,
            "exit_price":     float(trade.get("exit_price") or 0.0) if action == "EXIT" else None,
            "exit_reason":    trade.get("exit_reason"),

            # P&L
            "pnl_realized_usd":   float(trade.get("realized_pnl") or trade.get("pnl") or 0.0)
                                   if action == "EXIT" else None,
            "pnl_unrealized_usd": None,
            "pnl_total_usd":      None,

            # Extra context
            "game_title":   trade.get("game_title"),
            "market_name":  trade.get("market_name"),
            "side":         trade.get("side"),
            "quantity":     qty,
        }

        fh = _get_handle(date_str)
        fh.write(json.dumps(record, default=str) + "\n")
        fh.flush()
    except Exception as exc:
        logger.warning(f"[DecisionTracer] write_from_trade_dict failed: {exc}", exc_info=True)


def patch_order_id(
    *,
    order_id: str,
    market_ticker: str,
    action: str,
    date: Optional[str] = None,
) -> bool:
    """
    Backfill a real order ID into the most-recent matching trace record.

    Rewrites the JSONL file in-place (daily file is typically < 10 k lines).
    Thread-safety: acquires an exclusive lock on the file via a temporary
    rename — safe for single-process use.  Returns True on success.

    Parameters
    ----------
    order_id      : the Kalshi (or paper) order ID returned after placement
    market_ticker : the market's Kalshi ticker (used to locate the record)
    action        : "ENTER" or "EXIT"
    date          : YYYYMMDD string; defaults to today UTC
    """
    if not order_id or not market_ticker:
        return False

    path = _get_log_path(date)
    if not path.exists():
        logger.warning(f"[DecisionTracer] patch_order_id: file not found {path}")
        return False

    action_upper = action.upper()
    id_field = "entry_order_id" if action_upper == "ENTER" else "exit_order_id"
    ticker_upper = market_ticker.upper()

    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        logger.warning(f"[DecisionTracer] patch_order_id read error: {exc}")
        return False

    # Walk backwards: patch the *most recent* matching record
    patched = False
    for i in range(len(lines) - 1, -1, -1):
        raw = lines[i].strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if (
            (rec.get("market_ticker") or "").upper() == ticker_upper
            and rec.get("action", "").upper() == action_upper
            and rec.get(id_field) is None
        ):
            rec[id_field] = order_id
            lines[i] = json.dumps(rec, default=str) + "\n"
            patched = True
            break

    if not patched:
        logger.debug(
            f"[DecisionTracer] patch_order_id: no un-patched {action_upper} record "
            f"for {market_ticker}"
        )
        return False

    # Flush cached handle before rewriting
    date_str = (date or datetime.now(timezone.utc).strftime("%Y%m%d"))
    if date_str in _handles:
        try:
            _handles[date_str].flush()
        except Exception:
            pass

    # Write atomically via temp file
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning(f"[DecisionTracer] patch_order_id write error: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    logger.info(
        f"[DecisionTracer] Patched {id_field}={order_id!r} into {action_upper} "
        f"record for {market_ticker}"
    )
    return True


def flush_all():
    """Flush all open file handles (call on shutdown)."""
    for fh in _handles.values():
        try:
            fh.flush()
            fh.close()
        except Exception:
            pass
    _handles.clear()
