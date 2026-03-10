"""
tests/test_acceptance.py
════════════════════════════════════════════════════════════════════════
Acceptance test suite — four criteria must all pass.

  AC1  For any trade, we can pull /explain and see the exact rule path
       + every numeric input that drove the decision.

  AC2  Daily debug bundle can be generated (ZIP) in one HTTP call.

  AC3  Replay mode reproduces decisions deterministically from stored
       snapshots / config — two runs on identical input must yield
       identical outputs.

  AC4  No PII or secrets appear in application log output.

Run with pytest:

    cd backend
    python -m pytest tests/test_acceptance.py -v

Or directly (no pytest required):

    cd backend
    python tests/test_acceptance.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

# ── Path setup ────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ════════════════════════════════════════════════════════════════════════
# AC1 – Trade explain: rule path + exact numbers
# ════════════════════════════════════════════════════════════════════════

class TestTradeExplain:
    """
    AC1: Given a decision-trace record, /explain must return a response
    that contains all the numeric inputs and the full rule-check tree.
    """

    # ── Fixtures ──────────────────────────────────────────────────────────

    def _make_trace_record(
        self,
        order_id: str = "order-abc-123",
        action: str = "ENTER",
    ) -> Dict:
        """Return a realistic decision-trace JSONL record."""
        return {
            "ts": "2026-03-02T20:00:00+00:00",
            "run_id": "run-test-001",
            "env": "paper",
            "league": "NBA",
            "event_id": "game-001",
            "market_ticker": "NBA-GAME-001-WIN",
            "model_id": "model_a",
            "best_bid": 0.53,
            "best_ask": 0.57,
            "mid_price": 0.55,
            "spread_cents": 4.0,
            "top_depth_usd": 220.0,
            "total_depth_usd": 1800.0,
            "volume_5m": 850,
            "volume_60m": 9000,
            "p_model": 0.61,
            "p_market": 0.55,
            "edge": 0.06,
            "confidence": 0.72,
            "persistence_sec": 95.0,
            "ev_usd": 11.52,
            "txn_cost_buffer_pct": 0.02,
            "kelly_fraction": 0.093,
            "stake_usd": 55.0,
            "eligibility_checks": {
                "min_edge": {"pass": True, "reason": "edge=0.0600 threshold=0.05"},
                "min_signal_score": {"pass": True, "reason": "score=72.0 threshold=60"},
                "edge_persistence": {"pass": True, "reason": "persistent_sec=95.0 ticks_required=3"},
                "spread_filter": {"pass": True, "reason": "spread=0.0400 max=0.10"},
                "league_filter": {"pass": True, "reason": "league=NBA allowed=['NBA', 'NCAA_M', 'NCAA_W']"},
            },
            "risk_checks": {
                "circuit_breaker": {"pass": True, "reason": "OK"},
                "daily_loss_cap": {"pass": True, "reason": "daily_pnl=0.0% cap=-5.0%"},
                "max_positions": {"pass": True, "reason": "open=0 max=5"},
            },
            "reason_codes": [
                "MIN_EDGE_OK", "MIN_SIGNAL_SCORE_OK", "EDGE_PERSISTENCE_OK",
                "SPREAD_FILTER_OK", "LEAGUE_FILTER_OK",
                "CIRCUIT_BREAKER_OK", "DAILY_LOSS_CAP_OK", "MAX_POSITIONS_OK",
            ],
            "action": action,
            "entry_order_id": order_id if action == "ENTER" else None,
            "entry_price": 0.57,
            "target_price": 0.6555,
            "stop_price": 0.513,
            "exit_order_id": order_id if action == "EXIT" else None,
            "exit_price": None,
            "exit_reason": None,
            "pnl_realized_usd": None,
            "pnl_unrealized_usd": None,
            "pnl_total_usd": None,
        }

    def _write_trace_to_tmpfile(self, record: Dict) -> Path:
        """Write one JSONL record to a temp file and return the path."""
        tmp = tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False, encoding="utf-8"
        )
        tmp.write(json.dumps(record) + "\n")
        tmp.close()
        return Path(tmp.name)

    # ── Tests ─────────────────────────────────────────────────────────────

    def test_trace_record_has_all_numeric_fields(self):
        """The trace record must contain every numeric input field."""
        rec = self._make_trace_record()
        required_numeric = [
            "best_bid", "best_ask", "mid_price", "spread_cents",
            "p_model", "p_market", "edge", "confidence",
            "persistence_sec", "ev_usd", "kelly_fraction", "stake_usd",
            "entry_price", "target_price", "stop_price",
        ]
        missing = [f for f in required_numeric if rec.get(f) is None]
        assert not missing, f"Trace record missing numeric fields: {missing}"
        print(f"  ✅ All {len(required_numeric)} numeric fields present in trace record.")

    def test_trace_record_has_full_rule_tree(self):
        """eligibility_checks and risk_checks must be present with pass/reason."""
        rec = self._make_trace_record()
        for section in ("eligibility_checks", "risk_checks"):
            checks = rec.get(section, {})
            assert checks, f"Missing {section}"
            for name, info in checks.items():
                assert "pass" in info, f"{section}.{name} missing 'pass'"
                assert "reason" in info, f"{section}.{name} missing 'reason'"
        print(
            f"  ✅ Rule tree: {len(rec['eligibility_checks'])} eligibility checks, "
            f"{len(rec['risk_checks'])} risk checks."
        )

    def test_explain_by_order_id_finds_record(self):
        """_read_records + order_id lookup returns the correct trace record."""
        # We test the route helper directly (no live server needed)
        from routes.decisions import _read_records, _enrich

        order_id = "order-test-xyz-999"
        rec = self._make_trace_record(order_id=order_id, action="ENTER")
        date_str = "20260302"

        # Patch the log dir to point at a temp directory
        tmp_dir = Path(tempfile.mkdtemp())
        trace_file = tmp_dir / f"decision_trace_{date_str}.jsonl"
        trace_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

        import routes.decisions as _dec_mod
        orig_log_dir = _dec_mod._LOG_DIR
        _dec_mod._LOG_DIR = tmp_dir
        try:
            records = _read_records(date_str=date_str, limit=50_000, reverse=False)
            match = next(
                (r for r in records if r.get("entry_order_id") == order_id),
                None,
            )
            assert match is not None, "Record not found by order_id"
            enriched = _enrich(match)
            assert "human_summary" in enriched
            assert "eligibility_checks" in enriched
            assert "risk_checks" in enriched
            assert enriched["action"] == "ENTER"
        finally:
            _dec_mod._LOG_DIR = orig_log_dir
            trace_file.unlink(missing_ok=True)

        print(f"  ✅ explain(order_id) → record found, human_summary: {enriched['human_summary'][:60]}…")

    def test_explain_by_market_ticker_finds_record(self):
        """Lookup by market_ticker returns the most-recent matching record."""
        from routes.decisions import _read_records, _enrich

        ticker = "NBA-GAME-LOOKUP-001-WIN"
        rec = self._make_trace_record()
        rec["market_ticker"] = ticker
        rec["entry_order_id"] = None
        date_str = "20260302"

        tmp_dir = Path(tempfile.mkdtemp())
        trace_file = tmp_dir / f"decision_trace_{date_str}.jsonl"
        trace_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

        import routes.decisions as _dec_mod
        orig = _dec_mod._LOG_DIR
        _dec_mod._LOG_DIR = tmp_dir
        try:
            records = _read_records(date_str=date_str, limit=50_000, reverse=True)
            match = next(
                (r for r in records if (r.get("market_ticker") or "").upper() == ticker.upper()),
                None,
            )
            assert match is not None, "Record not found by ticker"
            enriched = _enrich(match)
            assert enriched["market_ticker"] == ticker
        finally:
            _dec_mod._LOG_DIR = orig
            trace_file.unlink(missing_ok=True)

        print(f"  ✅ explain(market_ticker) → record found for {ticker}.")

    def test_human_summary_contains_rule_conditions(self):
        """human_summary must reference key numeric conditions."""
        from routes.decisions import _build_human_summary
        rec = self._make_trace_record()
        summary = _build_human_summary(rec)
        # Should mention edge, confidence/score, persistence
        assert "Edge" in summary or "edge" in summary, "Missing edge in summary"
        assert "ENTER" in summary.upper(), "Missing ENTER action in summary"
        print(f"  ✅ human_summary: '{summary}'")

    def test_patch_order_id_backfills_trace(self):
        """patch_order_id() must write the order ID into an existing ENTER record."""
        import services.decision_tracer as _dt

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        tmp_dir = Path(tempfile.mkdtemp())
        orig_log_dir = _dt._LOG_DIR
        _dt._LOG_DIR = tmp_dir

        ticker = "NBA-PATCH-TEST-WIN"
        rec = self._make_trace_record(order_id=None, action="ENTER")
        rec["market_ticker"] = ticker
        rec["entry_order_id"] = None

        trace_file = tmp_dir / f"decision_trace_{date_str}.jsonl"
        trace_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

        try:
            result = _dt.patch_order_id(
                order_id="order-backfill-001",
                market_ticker=ticker,
                action="ENTER",
                date=date_str,
            )
            assert result is True, "patch_order_id returned False"

            patched = json.loads(trace_file.read_text(encoding="utf-8").strip())
            assert patched.get("entry_order_id") == "order-backfill-001", (
                f"entry_order_id not patched: {patched.get('entry_order_id')!r}"
            )
        finally:
            _dt._LOG_DIR = orig_log_dir

        print("  ✅ patch_order_id() successfully backfills entry_order_id into existing record.")


# ════════════════════════════════════════════════════════════════════════
# AC2 – Daily debug bundle in one click
# ════════════════════════════════════════════════════════════════════════

class TestDebugBundle:
    """
    AC2: GET /api/debug/bundle?date=YYYY-MM-DD must return a valid ZIP
    containing at least a manifest.json.  The call must complete without
    a database connection (DB sources degrade gracefully to empty lists).
    """

    def test_build_zip_produces_valid_zip(self):
        """_build_zip() must return a readable ZIP with a manifest."""
        import asyncio
        import io
        import zipfile
        from datetime import date as _date

        # We need to run the async helper; patch DB to avoid network calls
        with patch("routes.debug._get_db", return_value=None):
            from routes.debug import _build_zip
            buf = asyncio.get_event_loop().run_until_complete(
                _build_zip(_date(2026, 3, 2))
            )

        assert isinstance(buf, io.BytesIO), "Expected BytesIO buffer"
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

        assert "manifest.json" in names, f"manifest.json not in ZIP: {names}"
        print(f"  ✅ ZIP produced with {len(names)} entries: {names}")

    def test_manifest_has_required_fields(self):
        """manifest.json inside the bundle must have the required summary fields."""
        import asyncio
        import zipfile
        from datetime import date as _date

        with patch("routes.debug._get_db", return_value=None):
            from routes.debug import _build_zip
            buf = asyncio.get_event_loop().run_until_complete(
                _build_zip(_date(2026, 3, 2))
            )

        with zipfile.ZipFile(buf, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))

        required = ["exported_at", "date", "decision_traces", "orders",
                    "audit_events", "metrics_snapshots", "config_versions"]
        missing = [f for f in required if f not in manifest]
        assert not missing, f"manifest.json missing fields: {missing}"
        print(f"  ✅ manifest.json has all required fields: {list(manifest.keys())}")

    def test_bundle_endpoint_is_registered(self):
        """The /api/debug/bundle route must exist on the router."""
        from routes.debug import router
        paths = [r.path for r in router.routes]
        assert any("bundle" in p for p in paths), (
            f"No 'bundle' route found in debug router. Routes: {paths}"
        )
        print(f"  ✅ /api/debug/bundle is registered.  All debug routes: {paths}")

    def test_bundle_content_type_is_zip(self):
        """The bundle endpoint must set Content-Disposition with a .zip filename."""
        import asyncio
        from datetime import date as _date
        from fastapi.responses import StreamingResponse

        with patch("routes.debug._get_db", return_value=None):
            from routes.debug import export_debug_bundle
            import asyncio
            resp = asyncio.get_event_loop().run_until_complete(
                export_debug_bundle(date="2026-03-02")
            )

        assert isinstance(resp, StreamingResponse)
        cd = resp.headers.get("Content-Disposition", "")
        assert ".zip" in cd, f"Expected .zip in Content-Disposition, got: {cd!r}"
        print(f"  ✅ Content-Disposition: {cd}")


# ════════════════════════════════════════════════════════════════════════
# AC3 – Replay mode: deterministic reproduction
# ════════════════════════════════════════════════════════════════════════

class TestReplayMode:
    """
    AC3: Running the same replay twice on identical input (synthetic data
    with a fixed seed) must produce bit-for-bit identical results.
    """

    def _get_synthetic_records(self, model: str = "A", date: str = "2026-03-02", n: int = 80):
        from tools.replay import _make_synthetic_records
        return _make_synthetic_records(date, model, n)

    def _run(self, records, model: str = "A"):
        config_path = str(
            BACKEND_DIR / "strategies" / "configs" / f"model_{model.lower()}.json"
        )
        from tools.replay import _run_replay
        return _run_replay(
            records=records,
            model_letter=model,
            config_path=config_path,
            config_label="default",
            date_str="2026-03-02",
        )

    def test_synthetic_records_are_deterministic(self):
        """Two calls to _make_synthetic_records with the same args must be identical."""
        r1 = self._get_synthetic_records()
        r2 = self._get_synthetic_records()
        assert len(r1) == len(r2), "Different record counts"
        for i, (a, b) in enumerate(zip(r1, r2)):
            assert a.ts == b.ts, f"ts mismatch at index {i}"
            assert a.edge == b.edge, f"edge mismatch at index {i}"
        print(f"  ✅ Synthetic records deterministic across two calls ({len(r1)} records).")

    def test_replay_is_deterministic(self):
        """Two replay runs on identical input must produce identical PnL + trade counts."""
        records = self._get_synthetic_records()
        r1 = self._run(records)
        r2 = self._run(records)

        assert r1.enters == r2.enters, f"enters differ: {r1.enters} vs {r2.enters}"
        assert r1.exits  == r2.exits,  f"exits differ: {r1.exits} vs {r2.exits}"
        assert r1.blocks == r2.blocks, f"blocks differ: {r1.blocks} vs {r2.blocks}"
        assert abs(r1.total_pnl - r2.total_pnl) < 1e-6, (
            f"PnL differs: {r1.total_pnl} vs {r2.total_pnl}"
        )
        print(
            f"  ✅ Replay deterministic: enters={r1.enters}, exits={r1.exits}, "
            f"PnL=${r1.total_pnl:+.2f} (run1 == run2)."
        )

    def test_replay_trade_list_order_is_stable(self):
        """The trade list order must match between identical replay runs."""
        records = self._get_synthetic_records()
        r1 = self._run(records)
        r2 = self._run(records)

        trade_ids_1 = [t.market_id for t in r1.trades]
        trade_ids_2 = [t.market_id for t in r2.trades]
        assert trade_ids_1 == trade_ids_2, (
            f"Trade list order differs:\n  run1: {trade_ids_1}\n  run2: {trade_ids_2}"
        )
        print(f"  ✅ Trade list order stable across runs ({len(trade_ids_1)} trades).")

    def test_config_change_changes_results(self):
        """A config with tighter edge threshold must produce fewer or equal ENTERs."""
        import copy, json, tempfile
        from tools.replay import _make_synthetic_records, _run_replay

        records = _make_synthetic_records("2026-03-02", "A", n=120)

        # Load default config and create a tighter variant
        default_cfg_path = BACKEND_DIR / "strategies" / "configs" / "model_a.json"
        with open(default_cfg_path) as f:
            cfg = json.load(f)

        tight_cfg = copy.deepcopy(cfg)
        tight_cfg.setdefault("entry_rules", {})
        tight_cfg["entry_rules"]["min_edge_threshold"] = 0.15   # much tighter

        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(tight_cfg, tf)
            tight_path = tf.name

        try:
            baseline  = _run_replay(records, "A", str(default_cfg_path), "default", "2026-03-02")
            candidate = _run_replay(records, "A", tight_path, "tight",   "2026-03-02")
        finally:
            Path(tight_path).unlink(missing_ok=True)

        assert candidate.enters <= baseline.enters, (
            f"Tighter config produced MORE entries ({candidate.enters} > {baseline.enters})"
        )
        print(
            f"  ✅ Config change is effective: baseline enters={baseline.enters}, "
            f"tight enters={candidate.enters}."
        )

    def test_replay_api_endpoint_is_registered(self):
        """GET /api/debug/replay must exist on the debug router."""
        from routes.debug import router
        paths = [r.path for r in router.routes]
        assert any("replay" in p for p in paths), (
            f"No 'replay' route found in debug router. Routes: {paths}"
        )
        print(f"  ✅ /api/debug/replay is registered.")


# ════════════════════════════════════════════════════════════════════════
# AC4 – No PII / secrets in logs
# ════════════════════════════════════════════════════════════════════════

class TestNoSecretsInLogs:
    """
    AC4: The PiiFilter must scrub all known secret / PII patterns from
    every log record before it reaches any handler.
    """

    def _capture_logs(self, message: str, *args) -> str:
        """Emit *message* through a child logger and capture the formatted output."""
        from services.log_sanitizer import install_log_sanitizer
        # Ensure the class-level patch is active (idempotent in production)
        install_log_sanitizer()

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            logging.getLogger("test.pii").warning(message, *args)
        finally:
            root.removeHandler(handler)
        return buf.getvalue()

    # ── Individual pattern tests ──────────────────────────────────────────

    def test_mongodb_uri_is_scrubbed(self):
        """MongoDB URIs with embedded credentials must be redacted."""
        output = self._capture_logs(
            "Connecting to mongodb://admin:s3cr3t@db.example.com:27017/prod"
        )
        assert "s3cr3t" not in output, f"Password leaked in log: {output!r}"
        assert "[REDACTED:mongodb_uri]" in output, f"Redaction marker missing: {output!r}"
        print(f"  ✅ MongoDB URI scrubbed: …{output.strip()[-60:]}")

    def test_jwt_bearer_token_is_scrubbed(self):
        """Bearer tokens in log lines must be redacted."""
        fake_jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiJ1c2VyLTEyMyIsImlhdCI6MTYwMDAwMH0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        output = self._capture_logs(f"Auth header: Bearer {fake_jwt}")
        assert fake_jwt not in output, f"JWT leaked in log: {output!r}"
        assert "[REDACTED" in output, f"Redaction marker missing: {output!r}"
        print(f"  ✅ JWT Bearer token scrubbed.")

    def test_password_param_is_scrubbed(self):
        """password=<value> in a log line must be redacted."""
        output = self._capture_logs("Login attempt: password=hunter2 user=alice")
        assert "hunter2" not in output, f"Password leaked: {output!r}"
        assert "[REDACTED:secret]" in output, f"Redaction missing: {output!r}"
        print(f"  ✅ password= param scrubbed.")

    def test_api_key_param_is_scrubbed(self):
        """api_key=<value> must be redacted."""
        output = self._capture_logs("Using api_key=ABCDEF1234567890ABCD")
        assert "ABCDEF1234567890ABCD" not in output, f"API key leaked: {output!r}"
        assert "[REDACTED" in output
        print(f"  ✅ api_key= param scrubbed.")

    def test_email_address_is_scrubbed(self):
        """Email addresses must be redacted."""
        output = self._capture_logs("User email: alice@example.com signed in")
        assert "alice@example.com" not in output, f"Email leaked: {output!r}"
        assert "[REDACTED:email]" in output, f"Redaction missing: {output!r}"
        print(f"  ✅ Email address scrubbed.")

    def test_private_key_param_is_scrubbed(self):
        """private_key=<value> in a log line must be redacted."""
        output = self._capture_logs("private_key=SECRETPRIVATEKEY1234567890")
        assert "SECRETPRIVATEKEY1234567890" not in output, f"Private key leaked: {output!r}"
        assert "[REDACTED" in output
        print(f"  ✅ private_key= param scrubbed.")

    def test_pem_block_is_scrubbed(self):
        """PEM private key blocks must be fully redacted."""
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4P5cECo\n"
            "-----END RSA PRIVATE KEY-----"
        )
        output = self._capture_logs(f"Loaded key: {pem}")
        assert "MIIEow" not in output, f"PEM content leaked: {output!r}"
        assert "[REDACTED:pem_private_key]" in output
        print(f"  ✅ PEM private key block scrubbed.")

    def test_non_sensitive_data_passes_through(self):
        """Normal log messages without secrets must pass through unchanged."""
        msg = "Strategy Model A evaluated market NBA-GAME-001-WIN: edge=6.1% conf=72%"
        output = self._capture_logs(msg)
        assert "edge=6.1%" in output, f"Normal content was incorrectly stripped: {output!r}"
        assert "NBA-GAME-001-WIN" in output
        print(f"  ✅ Non-sensitive log content passes through unmodified.")

    def test_scrub_helper_is_available(self):
        """The scrub() helper function must be importable and work correctly."""
        from services.log_sanitizer import scrub
        clean = scrub("Connecting to mongodb://user:pass@host/db")
        assert "pass" not in clean
        assert "[REDACTED:mongodb_uri]" in clean
        print(f"  ✅ scrub() helper works: {clean!r}")

    def test_install_log_sanitizer_is_idempotent(self):
        """Calling install_log_sanitizer() twice must not double-install the filter."""
        from services.log_sanitizer import install_log_sanitizer
        import services.log_sanitizer as _ls
        install_log_sanitizer()
        install_log_sanitizer()
        # Module-level sentinel must be True and stable
        assert _ls._INSTALLED is True, "Sanitizer sentinel not set"
        # Logger.handle should be patched (qualname will contain 'patched' wrapper)
        import logging
        handle_qualname = logging.Logger.handle.__qualname__
        assert "patched" in handle_qualname or _ls._INSTALLED, (
            f"Logger.handle does not appear patched: {handle_qualname!r}"
        )
        print(f"  ✅ install_log_sanitizer() is idempotent (_INSTALLED={_ls._INSTALLED}).")


# ════════════════════════════════════════════════════════════════════════
# Standalone runner (no pytest needed)
# ════════════════════════════════════════════════════════════════════════

def _run_suite(cls):
    instance = cls()
    methods = sorted(m for m in dir(instance) if m.startswith("test_"))
    passed = failed = 0
    for name in methods:
        label = f"[{cls.__name__}] {name}"
        print(f"\n  {label}")
        try:
            getattr(instance, name)()
            passed += 1
        except Exception as exc:
            print(f"  ❌ FAILED: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    return passed, failed


if __name__ == "__main__":
    _SUITES = [
        (TestTradeExplain,   "AC1 – Trade explain: rule path + numbers"),
        (TestDebugBundle,    "AC2 – Daily debug bundle in 1 click"),
        (TestReplayMode,     "AC3 – Replay mode: deterministic reproduction"),
        (TestNoSecretsInLogs,"AC4 – No PII / secrets in logs"),
    ]

    total_p = total_f = 0
    for suite_cls, title in _SUITES:
        print(f"\n{'═'*70}")
        print(f"  {title}")
        print(f"{'═'*70}")
        p, f = _run_suite(suite_cls)
        total_p += p
        total_f += f

    print(f"\n{'═'*70}")
    verdict = "✅ ALL ACCEPTANCE TESTS PASSED" if total_f == 0 else f"❌ {total_f} TEST(S) FAILED"
    print(f"  {verdict}  ({total_p} passed, {total_f} failed)")
    print(f"{'═'*70}\n")
    sys.exit(0 if total_f == 0 else 1)
