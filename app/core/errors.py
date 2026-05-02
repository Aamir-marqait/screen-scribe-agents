"""Error classification + retry helpers for upstream LLM/API calls.

The Gemini/LiteLLM stack surfaces failures as plain ``Exception`` with the
provider message embedded in ``str(exc)``. We inspect that text to map them
to clean HTTP responses so the frontend always gets a structured JSON body
instead of a raw 502 from the hosting layer.
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from app.core.logging import get_logger, log_extra

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class UpstreamError(Exception):
    """Normalized upstream failure with an HTTP-friendly shape."""

    status_code: int
    code: str  # short machine-readable token, e.g. "rate_limited"
    message: str  # user-facing message
    retry_after: float | None = None  # seconds, when known
    transient: bool = False  # true => safe to retry

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"


_RETRY_AFTER_RE = re.compile(r"retry[_\- ]?after[^0-9]*(\d+(?:\.\d+)?)", re.IGNORECASE)
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s?", re.IGNORECASE)


def _extract_retry_after(text: str) -> float | None:
    for pattern in (_RETRY_AFTER_RE, _RETRY_DELAY_RE):
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def classify_upstream_error(exc: BaseException) -> UpstreamError:
    """Map an arbitrary upstream exception to an :class:`UpstreamError`.

    Falls back to a generic ``502 upstream_error`` when nothing matches.
    """

    if isinstance(exc, UpstreamError):
        return exc

    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    retry_after = _extract_retry_after(text)

    # Rate limit / quota
    if (
        "429" in text
        or "resource_exhausted" in lowered
        or "rate limit" in lowered
        or "ratelimit" in lowered
        or "quota" in lowered
        or "too many requests" in lowered
    ):
        return UpstreamError(
            status_code=429,
            code="rate_limited",
            message=(
                "The AI provider is rate-limiting requests right now. "
                "Please wait a moment and try again."
            ),
            retry_after=retry_after,
            transient=True,
        )

    # Timeouts
    if isinstance(exc, asyncio.TimeoutError) or "timeout" in lowered or "timed out" in lowered:
        return UpstreamError(
            status_code=504,
            code="upstream_timeout",
            message="The AI provider took too long to respond. Please try again.",
            retry_after=retry_after,
            transient=True,
        )

    # Auth / config
    if (
        "401" in text
        or "403" in text
        or "unauthorized" in lowered
        or "permission" in lowered
        or "api key" in lowered
        or "api_key" in lowered
    ):
        return UpstreamError(
            status_code=502,
            code="upstream_auth",
            message="AI provider rejected the request (auth/config issue).",
            transient=False,
        )

    # 5xx-ish / connection / unavailable
    if (
        "500" in text
        or "502" in text
        or "503" in text
        or "504" in text
        or "unavailable" in lowered
        or "connection" in lowered
        or "network" in lowered
    ):
        return UpstreamError(
            status_code=503,
            code="upstream_unavailable",
            message="The AI provider is temporarily unavailable. Please try again.",
            retry_after=retry_after,
            transient=True,
        )

    return UpstreamError(
        status_code=502,
        code="upstream_error",
        message="The AI provider returned an unexpected error.",
        transient=False,
    )


async def run_with_retries(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    op: str = "upstream_call",
) -> T:
    """Run ``func`` and retry on transient upstream failures with jittered backoff.

    Non-transient errors are re-raised immediately as :class:`UpstreamError`.
    """

    last: UpstreamError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 — we re-raise after classifying
            err = classify_upstream_error(exc)
            last = err
            logger.warning(
                "upstream call failed",
                extra=log_extra(
                    op=op,
                    attempt=attempt,
                    attempts=attempts,
                    code=err.code,
                    status_code=err.status_code,
                    transient=err.transient,
                    error=str(exc)[:500],
                ),
            )
            if not err.transient or attempt >= attempts:
                raise err from exc

            delay = err.retry_after if err.retry_after is not None else base_delay * (2 ** (attempt - 1))
            delay = min(delay, max_delay)
            delay += random.uniform(0, delay * 0.25)
            await asyncio.sleep(delay)

    # Unreachable, but keeps type checkers happy.
    assert last is not None
    raise last
