from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from starlette.requests import Request

from src.mcp_server.limits import (
    DAILY_CAP_MESSAGE,
    SHARED_BUCKET,
    DemoLimiter,
    resolve_client_ip,
)


class FakeClock:
    """Injected clock: deterministic time for every limits test (TEST-01)."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def advance(self, *, minutes: float = 0, hours: float = 0) -> None:
        self._now += timedelta(minutes=minutes, hours=hours)


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": headers,
    }
    return Request(scope)


# --- Rolling per-IP window (D-05) ---


async def test_five_calls_allowed_sixth_refused_with_reset_message() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=5, daily_cap=100, clock=clock)

    for _ in range(5):
        result = await limiter.check_and_consume("203.0.113.9")
        assert result.allowed

    refusal = await limiter.check_and_consume("203.0.113.9")
    assert not refusal.allowed
    reset_at = t0 + timedelta(hours=1)
    assert refusal.message == f"rate limit reached, resets at {reset_at.strftime('%H:%M')} UTC"


async def test_ip_allowed_again_after_window_rolls() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=5, daily_cap=100, clock=clock)

    for _ in range(5):
        assert (await limiter.check_and_consume("203.0.113.9")).allowed
    assert not (await limiter.check_and_consume("203.0.113.9")).allowed

    clock.advance(minutes=61)
    result = await limiter.check_and_consume("203.0.113.9")
    assert result.allowed


async def test_reset_time_computed_from_oldest_remaining_timestamp() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=5, daily_cap=100, clock=clock)

    for offset in (0, 10, 20, 30, 40):
        clock.advance(minutes=0) if offset == 0 else clock.advance(minutes=10)
        assert (await limiter.check_and_consume("203.0.113.9")).allowed

    clock.advance(minutes=10)  # t0 + 50m
    refusal = await limiter.check_and_consume("203.0.113.9")
    assert not refusal.allowed
    expected_reset = t0 + timedelta(hours=1)
    assert refusal.message == (
        f"rate limit reached, resets at {expected_reset.strftime('%H:%M')} UTC"
    )


async def test_entry_exactly_one_hour_old_is_pruned_no_boundary_loophole() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=1, daily_cap=100, clock=clock)

    assert (await limiter.check_and_consume("203.0.113.9")).allowed
    clock.advance(hours=1)
    result = await limiter.check_and_consume("203.0.113.9")
    assert result.allowed


# --- Global UTC-day cap (D-05, D-06) ---


async def test_daily_cap_refuses_fourth_distinct_ip_with_reset_message() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=100, daily_cap=3, clock=clock)

    for ip in ("203.0.113.1", "203.0.113.2", "203.0.113.3"):
        assert (await limiter.check_and_consume(ip)).allowed

    refusal = await limiter.check_and_consume("203.0.113.4")
    assert not refusal.allowed
    assert refusal.message == DAILY_CAP_MESSAGE
    assert refusal.message == "demo budget spent for today, resets at 00:00 UTC"


async def test_daily_cap_resets_after_utc_midnight() -> None:
    t0 = datetime(2026, 7, 16, 23, 30, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=100, daily_cap=1, clock=clock)

    assert (await limiter.check_and_consume("203.0.113.1")).allowed
    assert not (await limiter.check_and_consume("203.0.113.2")).allowed

    clock.advance(hours=1)  # crosses into 2026-07-17 UTC
    result = await limiter.check_and_consume("203.0.113.2")
    assert result.allowed


# --- Consume-neither semantics (D-04) ---


async def test_refused_call_consumes_neither_counter() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=1, daily_cap=3, clock=clock)

    a1 = await limiter.check_and_consume("203.0.113.1")
    assert a1.allowed  # global count 1

    a2 = await limiter.check_and_consume("203.0.113.1")
    assert not a2.allowed  # per-IP refusal; global count still 1

    b = await limiter.check_and_consume("203.0.113.2")
    assert b.allowed  # global count 2

    c = await limiter.check_and_consume("203.0.113.3")
    assert c.allowed  # global count 3

    d = await limiter.check_and_consume("203.0.113.4")
    assert not d.allowed
    assert d.message == DAILY_CAP_MESSAGE


async def test_daily_cap_refusal_does_not_consume_per_ip_allowance() -> None:
    t0 = datetime(2026, 7, 16, 23, 58, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=5, daily_cap=6, clock=clock)

    # Exhaust the day's global budget from six other IPs so the target IP's
    # next call is refused purely by the daily cap, never touching its bucket.
    for i in range(6):
        assert (await limiter.check_and_consume(f"203.0.113.{i + 10}")).allowed
    refused = await limiter.check_and_consume("203.0.113.2")
    assert not refused.allowed
    assert refused.message == DAILY_CAP_MESSAGE

    clock.advance(minutes=3)  # rolls into next UTC day, daily cap resets
    # The refused IP still has its full per-IP allowance: 5 consecutive
    # calls succeed (well under the reset daily_cap=6 budget for this IP alone).
    for _ in range(5):
        result = await limiter.check_and_consume("203.0.113.2")
        assert result.allowed


# --- Concurrency (roadmap criterion 4) ---


async def test_concurrent_same_ip_calls_never_exceed_ip_limit() -> None:
    t0 = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    clock = FakeClock(t0)
    limiter = DemoLimiter(ip_limit=5, daily_cap=100, clock=clock)

    results = await asyncio.gather(*(limiter.check_and_consume("203.0.113.9") for _ in range(10)))
    allowed = [r for r in results if r.allowed]
    refused = [r for r in results if not r.allowed]
    assert len(allowed) == 5
    assert len(refused) == 5


# --- Client-IP resolution (HOST-04 verbatim) ---


def test_resolve_client_ip_none_request_returns_shared_bucket() -> None:
    assert resolve_client_ip(None) == SHARED_BUCKET


def test_resolve_client_ip_valid_fly_client_ip() -> None:
    request = _request([(b"fly-client-ip", b"203.0.113.9")])
    assert resolve_client_ip(request) == "203.0.113.9"


def test_resolve_client_ip_malformed_fly_client_ip_fails_closed_ignores_xff() -> None:
    request = _request(
        [
            (b"fly-client-ip", b"not-an-ip"),
            (b"x-forwarded-for", b"198.51.100.1, 203.0.113.7"),
        ]
    )
    assert resolve_client_ip(request) == SHARED_BUCKET


def test_resolve_client_ip_ignores_xff_fallback_when_fly_absent() -> None:
    # WR-01: X-Forwarded-For is fully client-spoofable and is never
    # consulted, even when it is well-formed. Absence of Fly-Client-IP
    # fails closed to SHARED_BUCKET rather than trusting it.
    request = _request([(b"x-forwarded-for", b"198.51.100.1, 203.0.113.7")])
    assert resolve_client_ip(request) == SHARED_BUCKET


def test_resolve_client_ip_ignores_malformed_xff_when_fly_absent() -> None:
    request = _request([(b"x-forwarded-for", b"198.51.100.1, not-an-ip")])
    assert resolve_client_ip(request) == SHARED_BUCKET


def test_resolve_client_ip_no_headers_returns_shared_bucket() -> None:
    request = _request([])
    assert resolve_client_ip(request) == SHARED_BUCKET


def test_resolve_client_ip_valid_ipv6_fly_client_ip() -> None:
    request = _request([(b"fly-client-ip", b"2001:db8::1")])
    assert resolve_client_ip(request) == "2001:db8::1"
