from __future__ import annotations

import asyncio
import ipaddress
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from starlette.requests import Request

# Fail-closed bucket key for stdio, missing headers, and malformed headers
# (HOST-04). Any caller that cannot be attributed to a real IP shares one
# bucket rather than bypassing the limit entirely.
SHARED_BUCKET = "shared"

# Single source of truth for the global-cap refusal message (D-06). Exported
# because plan 11-02's D-07 exhaustion-masquerade path reuses this exact
# string when Exa credit is exhausted in demo mode.
DAILY_CAP_MESSAGE = "demo budget spent for today, resets at 00:00 UTC"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class LimitResult:
    """Outcome of a single check_and_consume call.

    message is empty on success: D-07 forbids quota disclosure on
    successful calls, so allowed results never carry rationing text.
    """

    allowed: bool
    message: str = ""


class DemoLimiter:
    """In-memory demo-mode rate limiter (HOST-04).

    Deliberately the one stateful, mutable container in this codebase
    (every other model is frozen per project convention) -- counter storage
    cannot be frozen. Tracks a rolling per-IP hour window (D-05) plus a
    fixed-UTC-day global cap, both consumed together at one check-and-consume
    point (D-04).
    """

    def __init__(
        self,
        ip_limit: int,
        daily_cap: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.ip_limit = ip_limit
        self.daily_cap = daily_cap
        self.clock = clock
        self._ip_calls: dict[str, deque[datetime]] = {}
        self._day: date | None = None
        self._day_count = 0
        self._lock = asyncio.Lock()

    async def check_and_consume(self, ip: str) -> LimitResult:
        # No await inside the critical section: this makes the lock
        # defense-in-depth rather than strictly necessary today (asyncio's
        # cooperative scheduling alone would suffice for a purely
        # synchronous body), but it protects the read-modify-write
        # invariant against a future edit that sneaks an await in here.
        async with self._lock:
            now = self.clock()
            self._roll_day(now)

            bucket = self._ip_calls.get(ip)
            if bucket is not None:
                cutoff = now - timedelta(hours=1)
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._ip_calls[ip]
                    bucket = None

            if bucket is not None and len(bucket) >= self.ip_limit:
                reset_at = bucket[0] + timedelta(hours=1)
                return LimitResult(
                    allowed=False,
                    message=f"rate limit reached, resets at {reset_at.strftime('%H:%M')} UTC",
                )

            if self._day_count >= self.daily_cap:
                return LimitResult(allowed=False, message=DAILY_CAP_MESSAGE)

            if bucket is None:
                bucket = deque(maxlen=self.ip_limit)
                self._ip_calls[ip] = bucket
            bucket.append(now)
            self._day_count += 1
            return LimitResult(allowed=True)

    def _roll_day(self, now: datetime) -> None:
        today = now.astimezone(UTC).date()
        if today != self._day:
            self._day = today
            self._day_count = 0


def resolve_client_ip(request: Request | None) -> str:
    """Resolve the rate-limit bucket key for a request (HOST-04 verbatim).

    Trusts only Fly-Client-IP, which Fly's edge sets on every request that
    reaches this process (deploys are Fly-only; see mcp_http_host docs).
    Deliberately does not fall back to X-Forwarded-For: that header is
    fully attacker-controlled unless a trusted proxy is guaranteed to
    overwrite rather than append to it, and nothing here enforces that
    boundary. Fails closed into SHARED_BUCKET on a None request (stdio) or
    on a missing/malformed Fly-Client-IP header. Never logs raw header
    values (untrusted input).
    """
    if request is None:
        return SHARED_BUCKET

    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip is not None:
        return _validated_ip(fly_ip)

    # No X-Forwarded-For fallback: Fly always sets Fly-Client-Ip at its
    # edge, so absence of it means we are not behind Fly and must not
    # trust client-supplied forwarding headers.
    return SHARED_BUCKET


def _validated_ip(candidate: str) -> str:
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return SHARED_BUCKET
