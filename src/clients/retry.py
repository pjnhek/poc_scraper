"""Shared Retry-After helpers for the HTTP clients.

`parse_retry_after` accepts the RFC 7231 *integer* (or float) seconds form only
per D-06; the HTTP-date form is intentionally rejected, in line with what both
Exa and Browserbase document. Malformed values (non-numeric, negative) return
None so the caller can fall back to its existing wait strategy.

`retry_after_aware_wait` builds a tenacity-compatible wait callable that
honors the server hint *exactly* when present (no max, no min, no cap
composition, per D-05) and delegates to `fallback` otherwise. The header is
reached through `state.outcome.exception()`, isinstance-narrowed to
`httpx.HTTPStatusError` because only that subclass carries the response.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from tenacity import RetryCallState
from tenacity.wait import wait_base


def parse_retry_after(response: httpx.Response) -> float | None:
    """Return Retry-After seconds, or None if absent / malformed / HTTP-date.

    D-06: seconds-only. The RFC HTTP-date form is rejected; if either provider
    starts sending it we'll add an `email.utils.parsedate_to_datetime` branch.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if seconds < 0:
        return None
    return seconds


def retry_after_aware_wait(*, fallback: wait_base) -> Callable[[RetryCallState], float]:
    """Build a tenacity wait callable that honors Retry-After exactly when present.

    The wait callable receives a RetryCallState and reaches the response via the
    exception that triggered the retry. Only `httpx.HTTPStatusError` carries
    `.response` (the parent `httpx.HTTPError` does not), so we narrow on it
    explicitly. Anything else, including a missing/malformed header, delegates
    to `fallback`.
    """

    def _wait(state: RetryCallState) -> float:
        outcome = state.outcome
        exc = outcome.exception() if outcome is not None else None
        if isinstance(exc, httpx.HTTPStatusError):
            ra = parse_retry_after(exc.response)
            if ra is not None:
                return ra
        return fallback(state)

    return _wait
