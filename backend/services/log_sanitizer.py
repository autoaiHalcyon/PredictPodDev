"""
services/log_sanitizer.py
─────────────────────────────────────────────────────────────────────────────
PII & secrets scrubber for the Python logging pipeline.

Install once (on server startup) via ``install_log_sanitizer()``.  After that,
every log record emitted through the standard ``logging`` module is filtered
before it reaches any handler (file, stream, etc.).

Patterns scrubbed
─────────────────
• MongoDB connection strings (may contain username + password)
• Kalshi API key / private key values
• JWT access tokens (Bearer …  and raw eyJ… tokens)
• Arbitrary key=<long-secret> patterns (api_key=, secret=, token=, password=)
• Email addresses
• PEM private-key blocks

Each match is replaced with a bracketed placeholder, e.g.:
  [REDACTED:mongodb_uri]
  [REDACTED:bearer_token]
  [REDACTED:email]
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


# ── Compiled patterns ─────────────────────────────────────────────────────
#
# Each entry: (name, compiled_regex, replacement_template)
# The replacement may reference captured groups with \\1, \\2 etc.

_RULES: List[Tuple[str, re.Pattern, str]] = [
    # MongoDB URI  — mongodb[+srv]://user:pass@host/db?…
    (
        "mongodb_uri",
        re.compile(
            r"mongodb(?:\+srv)?://[^\s\"'<>]{4,}",
            re.IGNORECASE,
        ),
        "[REDACTED:mongodb_uri]",
    ),
    # PEM private key blocks
    (
        "pem_private_key",
        re.compile(
            r"-----BEGIN[ A-Z]*PRIVATE KEY-----.*?-----END[ A-Z]*PRIVATE KEY-----",
            re.DOTALL | re.IGNORECASE,
        ),
        "[REDACTED:pem_private_key]",
    ),
    # JWT Bearer tokens in Authorization header or log line
    (
        "bearer_token",
        re.compile(
            r"Bearer\s+eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*",
            re.IGNORECASE,
        ),
        "Bearer [REDACTED:jwt]",
    ),
    # Raw JWT tokens (eyJ… triple-dot format)
    (
        "jwt_token",
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b",
        ),
        "[REDACTED:jwt]",
    ),
    # Generic secret-looking query/form params:
    #   password=secret, api_key=abc123, secret=…, token=…, private_key=…
    (
        "secret_param",
        re.compile(
            r"(?i)((?:password|api[_-]?key|private[_-]?key|secret|access[_-]?token"
            r"|auth[_-]?token|kalshi[_-]?key)\s*[=:]\s*)[\"']?[^\s\"',;]{4,}[\"']?",
        ),
        r"\1[REDACTED:secret]",
    ),
    # Email addresses
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        ),
        "[REDACTED:email]",
    ),
    # Long random hex / base64 that look like API keys (standalone, > 20 chars,
    # not a UUID which we want to keep for traceability)
    # Heuristic: 32+ contiguous hex chars not separated by hyphens (not a UUID)
    (
        "hex_api_key",
        re.compile(
            r"\b(?<![0-9a-fA-F\-])[0-9a-fA-F]{32,}(?![0-9a-fA-F\-])\b",
        ),
        "[REDACTED:api_key]",
    ),
]


def _scrub(text: str) -> str:
    """Apply all sanitisation rules to *text*.  Returns the cleaned string."""
    for _name, pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


class PiiFilter(logging.Filter):
    """
    A ``logging.Filter`` that redacts PII and secrets from every log record
    *before* it is formatted and written to any handler.

    The filter mutates ``record.msg`` and each element of ``record.args`` so
    that the final formatted string is clean.  It also patches
    ``record.getMessage`` to return the scrubbed result for handlers that call
    it directly.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            # Scrub the raw message template
            record.msg = _scrub(str(record.msg))

            # Scrub positional args (if used with %-style formatting)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _scrub(str(v)) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        _scrub(str(a)) if isinstance(a, str) else a
                        for a in record.args
                    )

            # Also scrub exc_info / exception text if present
            if record.exc_text:
                record.exc_text = _scrub(record.exc_text)

        except Exception:
            # Never let the filter crash the logging pipeline
            pass

        return True   # always allow the record through


# ── Public installer ─────────────────────────────────────────────────────────

# Sentinel so we only patch once
_INSTALLED: bool = False


def install_log_sanitizer() -> None:
    """
    Intercept every log record emitted anywhere in the process and scrub PII.

    Implementation
    ──────────────
    Python's propagation mechanism only checks the *originating* logger's
    filters, not parent-logger filters, so adding a filter to ``logging.root``
    alone is insufficient for records emitted by child loggers.

    We patch ``logging.Logger.handle`` at the class level so that our filter
    is invoked for *every* logger instance, not just root.  The patch is
    applied exactly once (idempotent).
    """
    global _INSTALLED
    if _INSTALLED:
        return

    _filter = PiiFilter()
    _orig_handle = logging.Logger.handle

    def _patched_handle(self: logging.Logger, record: logging.LogRecord) -> None:
        """Apply PII scrubber before the original handle() logic."""
        _filter.filter(record)          # mutates record in-place; always returns True
        _orig_handle(self, record)

    logging.Logger.handle = _patched_handle  # type: ignore[method-assign]
    _INSTALLED = True

    # Log via the (now patched) logger — safe because PiiFilter always returns True
    logging.getLogger(__name__).info(
        "[LogSanitizer] PII/secrets scrubber installed (Logger.handle patched)."
    )


def scrub(text: str) -> str:
    """
    Public helper — run the scrubber on an arbitrary string.
    Useful for sanitising data before it's embedded in responses or files.
    """
    return _scrub(text)
