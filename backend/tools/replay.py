#!/usr/bin/env python
"""
replay.py — Re-run strategy rules on historical decision-trace snapshots.

No live connections are made; no trades are placed.  The tool reads the
JSON-Lines decision-trace log produced by decision_tracer, reconstructs
Game/Market/Signal objects, and pumps them through a fresh strategy
instance so you can validate rule changes without guessing.

Usage
-----
  # Single model, default config
  python backend/tools/replay.py --date 2026-02-28 --model A --dry-run

  # Two-config diff (baseline vs candidate)
  python backend/tools/replay.py --date 2026-02-28 --model A \\
      --config path/to/baseline.json --config path/to/candidate.json

Output
------
  • ENTER / EXIT decision counts
  • Simulated trade list (market, side, qty, entry, exit, PnL)
  • Expected PnL vs baseline (original trace actions)
  • Top reasons for entries and rejects
  • Diff report when two configs are supplied
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import textwrap
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Resolve repo root so imports work whether run from the repo root or
#    from inside the backend/ directory ─────────────────────────────────────
_HERE = Path(__file__).resolve().parent          # backend/tools/
_BACKEND = _HERE.parent                          # backend/
_REPO = _BACKEND.parent                          # project root
for _p in (_BACKEND, _REPO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Now import project modules ───────────────────────────────────────────────
from datetime import datetime as _DT
from models.game import Game, GameStatus, Team
from models.market import Market
from models.signal import Signal, SignalType
from strategies.base_strategy import StrategyConfig, StrategyDecision, DecisionType
from strategies.model_a_disciplined import ModelADisciplined
from strategies.model_b_high_frequency import ModelBHighFrequency
from strategies.model_c_institutional import ModelCInstitutional
import services.decision_tracer as _dt_module  # patched to no-op during replay

logging.basicConfig(
    level=logging.WARNING,          # suppress strategy INFO noise during replay
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger("replay")

# ── Paths ────────────────────────────────────────────────────────────────────
_TRACE_DIR    = _BACKEND / "logs" / "decision_traces"
_CONFIG_DIR   = _BACKEND / "strategies" / "configs"
_DEFAULT_CONFIGS: Dict[str, Path] = {
    "A": _CONFIG_DIR / "model_a.json",
    "B": _CONFIG_DIR / "model_b.json",
    "C": _CONFIG_DIR / "model_c.json",
}
_STRATEGY_CLASSES = {
    "A": ModelADisciplined,
    "B": ModelBHighFrequency,
    "C": ModelCInstitutional,
}
# Trace model_id prefix per letter
_MODEL_ID_PREFIX: Dict[str, str] = {
    "A": "model_a",
    "B": "model_b",
    "C": "model_c",
}

# ── Trace record ─────────────────────────────────────────────────────────────
@dataclass
class TraceRecord:
    """One JSON-Lines record from the decision-trace log."""
    ts: str
    model_id: str
    event_id: str
    market_ticker: str
    league: str

    best_bid: float
    best_ask: float
    mid_price: float
    spread_cents: float

    p_model: float
    p_market: float
    edge: float
    confidence: float
    ev_usd: float
    volume_5m: Optional[float]
    volume_60m: Optional[float]
    top_depth_usd: float
    total_depth_usd: float

    action: str                     # ENTER | EXIT | NO_TRADE | HOLD
    pnl_realized_usd: Optional[float]
    reason_codes: List[str]
    eligibility_checks: Dict
    risk_checks: Dict

    raw: Dict = field(repr=False)   # full original dict

    @classmethod
    def from_dict(cls, d: Dict) -> "TraceRecord":
        return cls(
            ts=d.get("ts", ""),
            model_id=d.get("model_id", ""),
            event_id=d.get("event_id", ""),
            market_ticker=d.get("market_ticker", ""),
            league=d.get("league", "NBA"),
            best_bid=float(d.get("best_bid") or 0.49),
            best_ask=float(d.get("best_ask") or 0.51),
            mid_price=float(d.get("mid_price") or 0.50),
            spread_cents=float(d.get("spread_cents") or 2.0),
            p_model=float(d.get("p_model") or 0.50),
            p_market=float(d.get("p_market") or 0.50),
            edge=float(d.get("edge") or 0.0),
            confidence=float(d.get("confidence") or 0.0),
            ev_usd=float(d.get("ev_usd") or 0.0),
            volume_5m=d.get("volume_5m"),
            volume_60m=d.get("volume_60m"),
            top_depth_usd=float(d.get("top_depth_usd") or 0.0),
            total_depth_usd=float(d.get("total_depth_usd") or 0.0),
            action=d.get("action", "NO_TRADE"),
            pnl_realized_usd=d.get("pnl_realized_usd"),
            reason_codes=d.get("reason_codes") or [],
            eligibility_checks=d.get("eligibility_checks") or {},
            risk_checks=d.get("risk_checks") or {},
            raw=d,
        )

    @property
    def ts_dt(self) -> datetime:
        try:
            return datetime.fromisoformat(self.ts.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)


# ── Object reconstruction ─────────────────────────────────────────────────────
_STUB_TEAM_HOME = Team(id="home", name="Home", abbreviation="HME")
_STUB_TEAM_AWAY = Team(id="away", name="Away", abbreviation="AWY")


def _make_game(rec: TraceRecord) -> Game:
    """Reconstruct a minimal Game from a trace record."""
    return Game(
        id=rec.event_id or "unknown_game",
        league=rec.league,
        home_team=_STUB_TEAM_HOME,
        away_team=_STUB_TEAM_AWAY,
        start_time=rec.ts_dt,
        status=GameStatus.LIVE,
        home_score=0,
        away_score=0,
        quarter=2,
        time_remaining="10:00",
        time_remaining_seconds=600,
    )


def _make_market(rec: TraceRecord, game_id: str) -> Market:
    """Reconstruct a minimal Market from a trace record."""
    # derive settled/settlement from the YES side resolving at 1.0 or 0.0
    return Market(
        id=rec.market_ticker or "unknown_market",
        game_id=game_id,
        kalshi_ticker=rec.market_ticker or None,
        outcome="home",
        yes_price=rec.mid_price,
        no_price=round(1.0 - rec.mid_price, 4),
        yes_bid=rec.best_bid,
        yes_ask=rec.best_ask,
        volume=int(rec.top_depth_usd * 2),
        is_active=True,
        settled=False,
    )


def _make_signal(rec: TraceRecord, game_id: str, market_id: str) -> Signal:
    """Reconstruct a Signal from a trace record."""
    edge = rec.edge
    if edge >= 0.05:
        stype = SignalType.STRONG_BUY
    elif edge >= 0.03:
        stype = SignalType.BUY
    elif edge <= -0.05:
        stype = SignalType.STRONG_SELL
    elif edge <= -0.03:
        stype = SignalType.SELL
    else:
        stype = SignalType.HOLD

    sig = Signal(
        game_id=game_id,
        market_id=market_id,
        signal_type=stype,
        edge=edge,
        fair_prob=rec.p_model,
        market_prob=rec.p_market,
        confidence=rec.confidence,
        volatility=0.0,
        recommended_side="yes" if edge > 0 else "no",
        recommended_size=0.0,
        max_loss=0.0,
        expected_value=rec.ev_usd,
        score_diff=0,
        time_remaining_seconds=600,
        quarter=2,
    )
    # Attach signal score for strategies that check it
    sig._signal_score = rec.confidence * 100       # type: ignore[attr-defined]
    sig._momentum_direction = "up" if edge > 0 else "down"  # type: ignore[attr-defined]
    return sig


# ── Replay engine ─────────────────────────────────────────────────────────────
@dataclass
class SimulatedTrade:
    market_id: str
    game_id: str
    side: str
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    entry_ts: str
    exit_ts: Optional[str]
    entry_reason: str
    exit_reason: Optional[str]
    pnl: float = 0.0
    is_open: bool = True


@dataclass
class ReplayResult:
    config_label: str
    date: str
    model: str
    total_ticks: int
    enters: int
    exits: int
    holds: int
    blocks: int
    trades: List[SimulatedTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    entry_reasons: Counter = field(default_factory=Counter)
    reject_reasons: Counter = field(default_factory=Counter)
    baseline_pnl: float = 0.0            # original trace realized PnL

    @property
    def open_trades(self) -> List[SimulatedTrade]:
        return [t for t in self.trades if t.is_open]

    @property
    def closed_trades(self) -> List[SimulatedTrade]:
        return [t for t in self.trades if not t.is_open]


def _make_strategy(model_letter: str, config_path: str):
    """Instantiate a fresh strategy with the given config."""
    cfg = StrategyConfig(config_path)
    cls = _STRATEGY_CLASSES[model_letter.upper()]
    return cls(cfg)


def _run_replay(
    records: List[TraceRecord],
    model_letter: str,
    config_path: str,
    config_label: str,
    date_str: str,
) -> ReplayResult:
    """
    Core replay loop.

    For each record (in timestamp order) reconstruct objects and call
    strategy.process_tick().  The VirtualPortfolio inside the strategy
    accumulates positions and realised PnL as if it were running live.
    """
    # Suppress all decision-tracer writes during replay
    original_write = _dt_module.write_decision

    def _noop_write(**kwargs):
        pass

    _dt_module.write_decision = _noop_write  # type: ignore[attr-defined]

    try:
        strategy = _make_strategy(model_letter, config_path)
        strategy.enable()

        result = ReplayResult(
            config_label=config_label,
            date=date_str,
            model=model_letter,
            total_ticks=len(records),
            enters=0,
            exits=0,
            holds=0,
            blocks=0,
        )

        # Accumulate original-trace PnL for baseline comparison
        result.baseline_pnl = sum(
            r.pnl_realized_usd for r in records
            if r.pnl_realized_usd is not None
        )

        # Track open positions for PnL attribution
        open_trade_map: Dict[str, SimulatedTrade] = {}   # market_id → SimulatedTrade

        for rec in records:
            game   = _make_game(rec)
            market = _make_market(rec, game.id)
            signal = _make_signal(rec, game.id, market.id)

            decision: Optional[StrategyDecision] = strategy.process_tick(
                game=game,
                market=market,
                signal=signal,
                orderbook=None,
                volume_5m=rec.volume_5m,
                volume_60m=rec.volume_60m,
            )

            if decision is None:
                continue

            dtype = decision.decision_type

            if dtype == DecisionType.ENTER:
                result.enters += 1
                result.entry_reasons[decision.reason] += 1
                sim_trade = SimulatedTrade(
                    market_id=market.id,
                    game_id=game.id,
                    side=decision.side,
                    quantity=decision.quantity,
                    entry_price=decision.price,
                    exit_price=None,
                    entry_ts=rec.ts,
                    exit_ts=None,
                    entry_reason=decision.reason,
                    exit_reason=None,
                    is_open=True,
                )
                open_trade_map[market.id] = sim_trade
                result.trades.append(sim_trade)

            elif dtype in (DecisionType.EXIT, DecisionType.TRIM):
                result.exits += 1
                opened = open_trade_map.pop(market.id, None)
                if opened:
                    pnl = (decision.price - opened.entry_price) * opened.quantity
                    if opened.side == "no":
                        pnl = -pnl
                    opened.exit_price = decision.price
                    opened.exit_ts    = rec.ts
                    opened.exit_reason = decision.reason
                    opened.pnl        = round(pnl, 4)
                    opened.is_open    = False
                    result.total_pnl += pnl
                    if pnl > 0:
                        result.win_count += 1
                    else:
                        result.loss_count += 1

            elif dtype == DecisionType.HOLD:
                result.holds += 1

            elif dtype in (DecisionType.BLOCK, DecisionType.CIRCUIT_BREAKER):
                result.blocks += 1
                result.reject_reasons[decision.reason] += 1

        # Unrealised PnL for any still-open positions
        for market_id, sim in open_trade_map.items():
            # Use last known mid price from portfolio
            pos = strategy.portfolio.get_position(market_id)
            if pos:
                upnl = pos.unrealized_pnl
                sim.pnl = round(upnl, 4)
                result.total_pnl += upnl

        result.total_pnl = round(result.total_pnl, 4)
        return result

    finally:
        _dt_module.write_decision = original_write   # type: ignore[attr-defined]


# ── Trace file loader ─────────────────────────────────────────────────────────
def _load_traces(date_str: str, model_letter: str) -> List[TraceRecord]:
    """
    Load and filter records from the decision-trace JSONL for *date_str*.

    date_str : "YYYY-MM-DD"
    Returns records sorted by timestamp.
    """
    compact = date_str.replace("-", "")
    trace_path = _TRACE_DIR / f"decision_trace_{compact}.jsonl"

    if not trace_path.exists():
        # Also try a Windows-style path relative to the repo
        alt = _BACKEND.parent / "logs" / "metrics_snapshots"
        logger.warning(
            f"Trace file not found: {trace_path}\n"
            "No decision-trace log exists for this date.\n"
            "Tip: the file is created by the live strategy loop.  "
            "Run the system for at least one tick to produce it."
        )
        return []

    prefix = _MODEL_ID_PREFIX.get(model_letter.upper(), "model_a")
    records: List[TraceRecord] = []

    with open(trace_path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                d = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.warning(f"Line {lineno}: invalid JSON, skipped")
                continue

            mid = d.get("model_id", "")
            if not (mid == prefix or mid.startswith(prefix)):
                continue

            records.append(TraceRecord.from_dict(d))

    records.sort(key=lambda r: r.ts)
    return records


# ── Sampling synthetic data for demo / testing ───────────────────────────────
def _make_synthetic_records(
    date_str: str,
    model_letter: str,
    n: int = 120,
) -> List[TraceRecord]:
    """
    If no real trace exists, generate plausible synthetic ticks so the
    tool always produces output for demonstration and CI purposes.
    """
    import random, uuid
    from datetime import timedelta

    rng = random.Random(42)
    base_ts = datetime.fromisoformat(f"{date_str}T19:00:00+00:00")
    prefix  = _MODEL_ID_PREFIX.get(model_letter.upper(), "model_a")

    records = []
    for i in range(n):
        game_id   = f"NBA-GAME-{(i // 20) + 1:03d}"
        ticker    = f"NBA-{game_id}-WIN"
        edge      = rng.gauss(0.0, 0.06)
        bid       = round(rng.uniform(0.35, 0.65), 2)
        ask       = round(bid + rng.uniform(0.01, 0.04), 2)
        mid       = round((bid + ask) / 2, 3)
        conf      = round(rng.uniform(0.5, 0.9), 3)
        p_market  = round(rng.uniform(0.4, 0.6), 3)
        p_model   = round(p_market + edge, 3)
        ts        = (base_ts + timedelta(seconds=i * 30)).isoformat()

        # Simulate what the LIVE system would have decided
        if abs(edge) >= 0.05 and conf >= 0.60:
            action = "ENTER"
            pnl    = None
        elif abs(edge) < 0.02 and i % 5 == 0:
            action = "EXIT"
            pnl    = round(rng.gauss(0.5, 2.0), 2)
        else:
            action = "NO_TRADE"
            pnl    = None

        d = dict(
            ts=ts,
            model_id=prefix,
            event_id=game_id,
            market_ticker=ticker,
            league="NBA",
            best_bid=bid,
            best_ask=ask,
            mid_price=mid,
            spread_cents=round((ask - bid) * 100, 1),
            p_model=p_model,
            p_market=p_market,
            edge=round(edge, 4),
            confidence=conf,
            ev_usd=round(edge * conf * 100, 2),
            volume_5m=rng.randint(200, 2000),
            volume_60m=rng.randint(2000, 20000),
            top_depth_usd=round(rng.uniform(50, 500), 2),
            total_depth_usd=round(rng.uniform(500, 5000), 2),
            action=action,
            pnl_realized_usd=pnl,
            reason_codes=[],
            eligibility_checks={},
            risk_checks={},
        )
        records.append(TraceRecord.from_dict(d))

    return records


# ── Report formatters ─────────────────────────────────────────────────────────
_SEP  = "─" * 70
_DSEP = "═" * 70


def _fmt_result(res: ReplayResult, *, synthetic: bool = False) -> str:
    closed = res.closed_trades
    opened = res.open_trades

    header_note = "  ⚠  SYNTHETIC DATA (no real trace found)" if synthetic else ""
    label    = f"[{res.config_label}]" if res.config_label else ""
    win_rate = 0.0
    if closed:
        win_rate = (res.win_count / len(closed)) * 100

    lines = [
        "",
        _DSEP,
        f"  REPLAY  {label}  Model {res.model}  ·  {res.date}{header_note}",
        _DSEP,
        "",
        f"  Ticks processed : {res.total_ticks:,}",
        f"  ENTER decisions : {res.enters:>6}",
        f"  EXIT  decisions : {res.exits:>6}",
        f"  HOLD            : {res.holds:>6}",
        f"  BLOCK / reject  : {res.blocks:>6}",
        "",
        _SEP,
        "  TRADE LIST (simulated)",
        _SEP,
    ]

    if not res.trades:
        lines.append("  (no trades triggered)")
    else:
        lines.append(
            f"  {'market':<28} {'side':<5} {'qty':>4}  {'entry':>6}  {'exit':>6}  {'pnl':>8}  status"
        )
        lines.append(f"  {'─'*28} {'─'*5} {'─'*4}  {'─'*6}  {'─'*6}  {'─'*8}  ──────")
        for t in res.trades:
            exit_str = f"{t.exit_price:.3f}" if t.exit_price else "  open"
            pnl_str  = f"{t.pnl:+.2f}"      if not t.is_open else "  open"
            status   = "OPEN" if t.is_open else ("WIN" if t.pnl > 0 else "LOSS")
            lines.append(
                f"  {t.market_id:<28} {t.side:<5} {t.quantity:>4}  "
                f"{t.entry_price:.3f}  {exit_str:>6}  {pnl_str:>8}  {status}"
            )

    pnl_delta = res.total_pnl - res.baseline_pnl
    lines += [
        "",
        _SEP,
        "  PnL SUMMARY",
        _SEP,
        f"  Replay PnL          : ${res.total_pnl:>+9.2f}",
        f"  Baseline (trace)    : ${res.baseline_pnl:>+9.2f}",
        f"  Delta               : ${pnl_delta:>+9.2f}",
        f"  Closed trades       : {len(closed):>4}  (W:{res.win_count}  L:{res.loss_count}  "
        f"WR:{win_rate:.0f}%)",
        f"  Open (unrealised)   : {len(opened):>4}",
        "",
    ]

    # Top entry reasons
    if res.entry_reasons:
        lines += [_SEP, "  TOP ENTRY REASONS", _SEP]
        for reason, cnt in res.entry_reasons.most_common(5):
            lines.append(f"  {cnt:>4}×  {reason}")
        lines.append("")

    # Top reject reasons
    if res.reject_reasons:
        lines += [_SEP, "  TOP REJECT REASONS", _SEP]
        for reason, cnt in res.reject_reasons.most_common(10):
            lines.append(f"  {cnt:>4}×  {reason}")
        lines.append("")

    return "\n".join(lines)


def _fmt_diff(baseline: ReplayResult, candidate: ReplayResult) -> str:
    """Side-by-side diff of two replay configs."""

    def _delta(a, b, fmt="+.2f"):
        d = b - a
        return f"{d:{fmt}}"

    lines = [
        "",
        _DSEP,
        f"  DIFF REPORT  ·  Model {baseline.model}  ·  {baseline.date}",
        _DSEP,
        f"  {'Metric':<28} {'Baseline':>12} {'Candidate':>12} {'Delta':>12}",
        f"  {'─'*28} {'─'*12} {'─'*12} {'─'*12}",
        f"  {'ENTER count':<28} {baseline.enters:>12} {candidate.enters:>12} "
        f"{_delta(baseline.enters, candidate.enters, '+d'):>12}",
        f"  {'EXIT count':<28} {baseline.exits:>12} {candidate.exits:>12} "
        f"{_delta(baseline.exits, candidate.exits, '+d'):>12}",
        f"  {'BLOCK count':<28} {baseline.blocks:>12} {candidate.blocks:>12} "
        f"{_delta(baseline.blocks, candidate.blocks, '+d'):>12}",
        f"  {'Replay PnL ($)':<28} {baseline.total_pnl:>+12.2f} {candidate.total_pnl:>+12.2f} "
        f"{_delta(baseline.total_pnl, candidate.total_pnl):>12}",
        f"  {'Win count':<28} {baseline.win_count:>12} {candidate.win_count:>12} "
        f"{_delta(baseline.win_count, candidate.win_count, '+d'):>12}",
        f"  {'Loss count':<28} {baseline.loss_count:>12} {candidate.loss_count:>12} "
        f"{_delta(baseline.loss_count, candidate.loss_count, '+d'):>12}",
        "",
    ]

    # entry reasons that changed
    all_entry_keys = set(baseline.entry_reasons) | set(candidate.entry_reasons)
    changed_entries = [
        (k, baseline.entry_reasons[k], candidate.entry_reasons[k])
        for k in all_entry_keys
        if baseline.entry_reasons[k] != candidate.entry_reasons[k]
    ]
    if changed_entries:
        lines += [_SEP, "  ENTRY REASON CHANGES", _SEP]
        for k, b_cnt, c_cnt in sorted(changed_entries, key=lambda x: abs(x[2]-x[1]), reverse=True):
            lines.append(f"  {k:<50} {b_cnt:>4} → {c_cnt:>4}")
        lines.append("")

    # reject reasons that changed
    all_reject_keys = set(baseline.reject_reasons) | set(candidate.reject_reasons)
    changed_rejects = [
        (k, baseline.reject_reasons[k], candidate.reject_reasons[k])
        for k in all_reject_keys
        if baseline.reject_reasons[k] != candidate.reject_reasons[k]
    ]
    if changed_rejects:
        lines += [_SEP, "  REJECT REASON CHANGES", _SEP]
        for k, b_cnt, c_cnt in sorted(changed_rejects, key=lambda x: abs(x[2]-x[1]), reverse=True):
            lines.append(f"  {k:<50} {b_cnt:>4} → {c_cnt:>4}")
        lines.append("")

    # trades only in one run
    baseline_mkt  = {t.market_id for t in baseline.trades}
    candidate_mkt = {t.market_id for t in candidate.trades}
    new_trades    = candidate_mkt - baseline_mkt
    dropped_trades = baseline_mkt - candidate_mkt

    if new_trades or dropped_trades:
        lines += [_SEP, "  TRADE SET CHANGES", _SEP]
        for m in sorted(new_trades):
            lines.append(f"  + NEW    {m}")
        for m in sorted(dropped_trades):
            lines.append(f"  - DROPPED {m}")
        lines.append("")

    verdict = "NEUTRAL"
    delta_pnl = candidate.total_pnl - baseline.total_pnl
    delta_entries = candidate.enters - baseline.enters
    if delta_pnl > 0 and delta_entries <= baseline.enters * 0.25:
        verdict = "✓ CANDIDATE LOOKS BETTER  (higher PnL, similar trade count)"
    elif delta_pnl < 0:
        verdict = "✗ CANDIDATE LOOKS WORSE   (lower PnL)"
    elif delta_entries > baseline.enters:
        verdict = "~ MORE ACTIVE  (more entries, re-check churn budget)"

    lines += [_DSEP, f"  VERDICT:  {verdict}", _DSEP, ""]
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="replay.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            Replay strategy rules on historical snapshots — no trades placed.

            Single run:
              python backend/tools/replay.py --date 2026-02-28 --model A --dry-run

            Config diff:
              python backend/tools/replay.py --date 2026-02-28 --model A \\
                  --config path/to/baseline.json --config path/to/candidate.json
        """),
    )
    p.add_argument(
        "--date", required=True,
        help="Date to replay  (YYYY-MM-DD)",
    )
    p.add_argument(
        "--model", required=True, choices=["A", "B", "C"],
        help="Strategy model to replay  (A | B | C)",
    )
    p.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=True,
        help="Dry-run mode (always true — this tool never places trades)",
    )
    p.add_argument(
        "--config", action="append", dest="configs", metavar="PATH",
        help=(
            "Config JSON file.  "
            "Supply once for a single run, twice for a baseline-vs-candidate diff."
        ),
    )
    p.add_argument(
        "--synthetic", action="store_true",
        help="Force use of synthetic data even if a real trace exists",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        parser.error(f"--date must be YYYY-MM-DD, got: {args.date!r}")

    # Validate config args
    configs = args.configs or []
    if len(configs) > 2:
        parser.error("Supply at most two --config paths (baseline and candidate)")

    # Resolve config paths
    def _resolve_config(path_str: str) -> str:
        p = Path(path_str)
        if p.is_absolute():
            return str(p)
        # Try relative to CWD first, then to Backend, then configs dir
        for base in (Path.cwd(), _BACKEND, _CONFIG_DIR):
            candidate = base / p
            if candidate.exists():
                return str(candidate)
        parser.error(f"Config file not found: {path_str!r}")

    if len(configs) == 0:
        # Use default config for the model
        default_path = _DEFAULT_CONFIGS.get(args.model.upper())
        if not default_path or not default_path.exists():
            parser.error(
                f"No default config found for Model {args.model} "
                f"(expected {default_path}).  Use --config to specify one."
            )
        resolved_configs = [(str(default_path), "default")]
    elif len(configs) == 1:
        resolved_configs = [(_resolve_config(configs[0]), Path(configs[0]).stem)]
    else:
        resolved_configs = [
            (_resolve_config(configs[0]), Path(configs[0]).stem),
            (_resolve_config(configs[1]), Path(configs[1]).stem),
        ]

    # Load traces
    print(f"\nLoading decision traces for {args.date}  model={args.model} …")
    records = _load_traces(args.date, args.model)

    synthetic = False
    if not records or args.synthetic:
        if not records:
            print(
                f"  No trace records found.  Using synthetic data for demonstration.\n"
                f"  (Run the strategy live for at least a few minutes to produce real traces.)"
            )
        synthetic = True
        records = _make_synthetic_records(args.date, args.model)

    print(f"  {len(records)} tick records loaded.\n")

    # Run replay(s)
    results: List[ReplayResult] = []
    for cfg_path, cfg_label in resolved_configs:
        print(f"  Running replay with config [{cfg_label}]  ({cfg_path}) …")
        res = _run_replay(
            records=records,
            model_letter=args.model,
            config_path=cfg_path,
            config_label=cfg_label,
            date_str=args.date,
        )
        results.append(res)

    # Print per-run reports
    for res in results:
        print(_fmt_result(res, synthetic=synthetic))

    # Diff report if two configs
    if len(results) == 2:
        print(_fmt_diff(results[0], results[1]))


if __name__ == "__main__":
    main()
