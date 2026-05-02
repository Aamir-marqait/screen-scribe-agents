"""Logging setup for the API.

Uses stdlib logging with a single stream handler that writes a compact,
greppable line per record. Railway captures stdout/stderr, so JSON-style
structured fields are appended as ``key=value`` pairs via ``extra``.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


_CONFIGURED = False


class _KeyValueFormatter(logging.Formatter):
    """Append any non-standard ``extra`` fields as ``key=value`` pairs."""

    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            extras.append(f"{key}={value!r}")
        if extras:
            return f"{base} | {' '.join(extras)}"
        return base


def configure_logging(level: str = "info") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _KeyValueFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Tame noisy libs.
    for noisy in ("httpx", "httpcore", "litellm", "LiteLLM", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


_RESERVED_LOGRECORD_KEYS = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"message", "asctime"}


def log_extra(**fields: Any) -> dict[str, Any]:
    """Helper so call-sites can write ``logger.info("msg", extra=log_extra(...))``.

    Auto-prefixes any key that collides with a reserved ``LogRecord`` attribute
    (``filename``, ``module``, ``name``, ``message``, ...) with ``ctx_`` so the
    stdlib logger doesn't raise ``"Attempt to overwrite 'X' in LogRecord"``.
    """
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _RESERVED_LOGRECORD_KEYS:
            safe[f"ctx_{key}"] = value
        else:
            safe[key] = value
    return safe
