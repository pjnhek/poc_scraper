# Phase 11: Rate Limits & Streamable HTTP Transport - Research

**Researched:** 2026-07-16
**Domain:** MCP `mcp` Python SDK (1.28.1) streamable-HTTP transport internals; in-memory rate limiting; Fly.io header semantics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Limit activation scope**
- **D-01:** `MCP_DEMO_MODE=1` enables `limits.py` on ANY transport. Stdio in demo mode has no client IP and falls into the fail-closed shared bucket HOST-04 already requires. One mental model; demo behavior is locally testable over stdio.
- **D-02:** `make mcp-http` WITHOUT demo mode is unlimited. Limits are a demo-mode concern only; a local BYOK user self-rations. The hosted deploy always sets the flag (Phase 13 guarantees it), so the public URL stays protected.
- **D-03:** The Exa results clamp (5, env-tunable) follows the same gate: demo mode only, any transport (per the design spec's "demo scope clamps").

**Counting semantics**
- **D-04:** A quota unit is consumed only by calls that reach retrieval: check-and-consume happens after `Account` validation passes, immediately before `collect_context`. Invalid domains and rate-limit refusals cost nothing (they burn no Exa credit). A retrieval that fails mid-flight still counts because Exa was hit. Per-IP and global counters are consumed together at that single point; a call refused by either limit consumes neither.
- **D-05:** The per-IP hourly limit uses a rolling 60-minute window: keep the last-5 call timestamps per IP; allow when fewer than 5 fall in the trailing hour; reset time = oldest timestamp + 1h. No burst-at-boundary loophole; bounded state (max `ip_limit` timestamps per IP). The global cap stays a fixed UTC day per HOST-04's wording ("25 per UTC day").

**Rationing error UX**
- **D-06:** Distinct refusal messages per limit, both as `isError: true` tool results in Phase 10's plain-message style (no machine codes): per-IP roughly "rate limit reached, resets at HH:MM UTC"; global roughly "demo budget spent for today, resets at 00:00 UTC". Exact strings are Claude's discretion; each MUST carry its reset time.
- **D-07:** No quota disclosure on successful calls. `EvidencePack` stays the pure evidence wire format Phase 10 locked (D-02 there: one model, `model_dump()` single serialization path); rationing info appears only in refusals. In demo mode, Exa credit exhaustion (402/429 surviving tenacity retries) borrows the global daily-cap wording so the public URL looks rationed, never broken; non-demo mode keeps Phase 10's "retrieval unavailable, try again".

**HTTP hardening front-load**
- **D-08:** Front-load HOST-06's transport-security half now: configure `TransportSecuritySettings` explicitly with a localhost allowlist (covering `127.0.0.1:<port>` / `localhost:<port>`). Phase 13 only swaps in the Fly hostname and verifies. Mirrors the Phase 10 precedent of front-loading HOST-05 (sanitized errors) so protection is never "off between phases".
- **D-09:** Local HTTP defaults: bind `127.0.0.1`, port `8000` (the spec's `mcp_http_port`), both env-overridable. Phase 13's Dockerfile explicitly overrides the host to `0.0.0.0`; exposure is a deliberate deploy-time act, never a local default.
- **D-10:** `make mcp-demo` (HTTP + `MCP_DEMO_MODE=1`, what the Dockerfile will run) lands THIS phase alongside `make mcp-http`, so the rationed server can be exercised locally (e.g. the 6th-call refusal by hand) and Phase 13 invokes an already-tested target.

**Locked by prior phases / requirements (do not re-litigate)**
- `limits.py` lives in `src/mcp_server/` (package layout locked in Phase 10); entry point stays `python -m src.mcp_server`, stdio default, `--transport http` added now.
- Demo mode forces thin tier and `NullBrowserbase` unconditionally (Phases 9/10; `Settings.mcp_tier()` already implements the thin force).
- Rationing errors are `isError: true` tool results (raise through the existing sanitizing wrapper), never protocol errors (MCP-07, Phase 10 D-07/D-08).
- Env-tunable caps (`MCP_DEMO_IP_LIMIT`, `MCP_DEMO_DAILY_CAP`, `MCP_DEMO_EXA_RESULTS` naming per the design spec) are a requirement-locked exception to Phase 10 D-03's "no new env knobs" principle -- HOST-04 explicitly demands env-tunable.
- In-memory counters only; no Redis or external store (design spec + research both explicitly exclude it). Single-machine globality is Phase 13's `fly.toml` concern.
- Client IP: prefer `Fly-Client-IP`; XFF fallback takes the RIGHTMOST entry; missing or malformed headers fail closed into one shared bucket (HOST-04 verbatim; research pitfall 4).
- Injected clock for all limit tests (roadmap criterion 3; TEST-01); counters protected against read-modify-write races under concurrent requests (roadmap criterion 4).
- Stack pin `mcp>=1.28,<2.0`; strict mypy, no new overrides.

### Claude's Discretion
- Exact refusal-message strings (within D-06's constraints) and the reset-time formatting details.
- Concurrency-protection mechanism for the counters (e.g. `asyncio.Lock` vs relying on no-await critical sections) -- criterion 4 demands protection; the mechanism is the planner/executor's call.
- Per-IP bucket pruning of stale entries (memory hygiene for a demo server), internal `limits.py` API shape, and how the injected clock is threaded (callable vs protocol).
- How the client-IP middleware mounts given the SDK finding below (wrap the returned Starlette app via `add_middleware`, a pure-ASGI wrapper, or equivalent) and how the IP reaches the tool (e.g. `contextvars.ContextVar` per research). **Resolved by this research -- see Summary: no middleware is needed at all.**
- Startup log wording for demo-mode/limit state (extending the Phase 10 tier log).

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope. (Fly deploy, `fly.toml` single-machine pin, production `TransportSecuritySettings` hostname, and README/CLAUDE.md docs were kept in Phase 13; resources/prompt and the full-tier tool stay in Phase 12.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HOST-02 | The same server runs over streamable HTTP (`make mcp-http`) from the same entry point | `FastMCP.streamable_http_app()` / `run_streamable_http_async()` confirmed against installed `mcp==1.28.1`; `build_server()` extended with host/port/stateless_http/transport_security kwargs, `__main__.py` gains `--transport` dispatch. See Architecture Patterns and Code Examples. |
| HOST-04 | Demo mode enforces per-IP hourly (5), global daily (25), Exa clamp (5), env-tunable, structured rationing errors with reset times; client IP from `Fly-Client-IP` with rightmost-XFF fallback, fail-closed on missing/malformed headers | Client-IP resolution mechanism resolved via `Context.request_context.request` (verified from SDK source, not middleware/contextvar). `limits.py` design (rolling window + fixed UTC day) in Architecture Patterns / Code Examples. Fly header semantics verified against Fly.io docs. |
</phase_requirements>

## Summary

The roadmap's named "highest-uncertainty step" is resolved, and the resolution changes the shape of the implementation from what the milestone's own prior research (`.planning/research/ARCHITECTURE.md` Pattern 4, `SUMMARY.md`) assumed. Reading the installed SDK source directly (`mcp==1.28.1`, confirmed via `.venv` and `uv.lock`) shows two things the milestone research did not have access to:

1. **`streamable_http_app()` takes no `middleware=` kwarg** (already confirmed in CONTEXT.md's SDK finding) -- it returns a plain `Starlette` app built fresh on every call. `TransportSecuritySettings` (DNS-rebinding protection, D-08) is **not** middleware you mount; it is a `FastMCP(transport_security=...)` **constructor kwarg** that the SDK threads internally into the session manager and every transport (`streamable_http_app`, `sse_app`, `run_sse_async`) without any extra wiring. Likewise `host`, `port`, and `stateless_http` are `FastMCP(...)` constructor kwargs (backed by the SDK's own `Settings(BaseSettings)`, env-prefixed `FASTMCP_*` -- **do not** rely on that prefix; pass this project's own `Settings` values explicitly as kwargs instead).

2. **The milestone's proposed fallback -- a custom ASGI middleware writing a `contextvars.ContextVar`, mounted via the (nonexistent) `middleware=` kwarg -- would not have worked correctly even if `streamable_http_app()` did accept middleware.** In stateful mode (the SDK default), a session's message-processing loop (`app.run(...)`) is spawned **once**, on the first HTTP request that creates the session, as a long-lived anyio task (`mcp/server/streamable_http_manager.py::_handle_stateful_request`, `run_server` task started via `task_group.start(run_server)`). Every subsequent HTTP request against that session feeds its body into the *same* persistent task through memory-object streams; it does not re-enter the ASGI middleware's calling task. A contextvar set by middleware in request N's task is invisible inside that already-running task from request 1, so this approach would silently deliver either no IP or a stale one for every request after the first in a session.
   The SDK avoids this problem with its own, different mechanism: at the transport layer (`mcp/server/streamable_http.py`, both the JSON-response and SSE branches), the raw Starlette `Request` for **the specific incoming HTTP request** is attached to the outgoing `SessionMessage`'s metadata (`ServerMessageMetadata(request_context=request)`). The low-level server's per-message dispatch (`mcp/server/lowlevel/server.py::_handle_request`) then does `request_ctx.set(RequestContext(..., request=request_data, ...))` **fresh, for every single message**, inside the task that is about to invoke the handler -- regardless of which task that is. `FastMCP.get_context()` exposes this as `Context.request_context.request` (typed `starlette.requests.Request | None`; `None` on stdio, since stdio never attaches `ServerMessageMetadata`).
   **Practical implication: no middleware is needed at all.** Phase 10 already wired the tool signature to accept a `Context` parameter (`get_account_evidence(domain: str, ctx: Context[ServerSession, ThinDeps])`); Phase 11's client-IP resolution is a plain read: `ctx.request_context.request` (add the third generic type arg, `Context[ServerSession, ThinDeps, Request]`, for strict-mypy fidelity on `.request`), then `request.headers.get("fly-client-ip")` with the rightmost-XFF fallback, falling closed to the shared bucket when `request is None` (stdio) or headers are missing/malformed.

`uvicorn`, `starlette`, and `sse-starlette` are already direct dependencies of `mcp` (confirmed in `uv.lock`) and already installed in `.venv` -- **no `pyproject.toml` change is needed** for the HTTP transport itself.

For the rate limiter: the in-memory design (rolling last-5-timestamps per IP, fixed UTC-day global counter) requires no new dependency. Because Python's asyncio is single-threaded cooperative scheduling, a synchronous check-and-consume function with no internal `await` point is already atomic with respect to other tasks -- an explicit `asyncio.Lock` is only strictly necessary if the critical section itself awaits (it should not, per D-04's "single point" wording). This is a real, if narrow, design constraint worth stating plainly to the planner, since criterion 4 explicitly demands protection and the natural-feeling design (a synchronous method) already satisfies it without a lock, but is fragile to a future edit that sneaks an `await` into the middle.

**Primary recommendation:** Extend `build_server()`/`__main__.py` to construct `FastMCP(..., host=settings.mcp_http_host, port=settings.mcp_http_port, stateless_http=True, transport_security=TransportSecuritySettings(...))` and dispatch to `asyncio.run(app.run_streamable_http_async())` on `--transport http`; resolve client IP inside `get_account_evidence` (or a small `limits.py` helper it calls) via `ctx.request_context.request`, never via custom middleware or contextvars.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP transport bootstrap (host/port/stateless mode) | API / Backend | -- | `FastMCP` construction + `uvicorn` are server-process concerns; no browser/CDN tier exists in this project |
| DNS-rebinding / Host-Origin validation | API / Backend | -- | Handled inside the SDK's transport layer (`TransportSecuritySettings` threaded through the session manager), not a separate middleware tier |
| Client-IP resolution | API / Backend | -- | Read from the per-message `Context.request_context.request` inside the tool handler; no ASGI middleware tier needed |
| Rate-limit counters (`limits.py`) | API / Backend (in-process memory) | -- | Deliberately not Database/Storage -- in-memory only, single-machine, per design spec and milestone research |
| Demo-mode Exa results clamp | API / Backend | External API (Exa) | Applied at the wiring layer (`src/mcp_server/wiring.py`) before the retrieval call reaches Exa |
| Entry-point transport dispatch (`--transport` flag) | API / Backend | -- | `src/mcp_server/__main__.py`, argparse; no client-side or CDN concern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | 1.28.1 (installed, `pyproject.toml` pin `>=1.28,<2.0`) | FastMCP server, streamable-HTTP transport, `TransportSecuritySettings` | Already the project's locked SDK (Phase 9/10); ships `uvicorn`/`starlette`/`sse-starlette` as direct dependencies -- confirmed `[VERIFIED: uv.lock]` |
| `starlette` (transitive via `mcp`) | resolved by `uv.lock` (py.typed, no mypy override needed) | ASGI `Request` object exposed via `Context.request_context.request`; underlies `streamable_http_app()`'s returned app | Already installed; `[VERIFIED: .venv inspection, starlette/py.typed present]` |
| `uvicorn` (transitive via `mcp`) | 0.51.0 installed | Serves the Starlette app inside `run_streamable_http_async()` | Already installed and used internally by the SDK; no direct project dependency needed. `[VERIFIED: .venv inspection]` |

No new packages need adding to `pyproject.toml` for this phase.

### Supporting
None -- rate limiting is plain-dict/`datetime` state per the design spec and milestone research (no rate-limiting library, no Redis).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Context.request_context.request` for client IP | Custom ASGI middleware + `contextvars.ContextVar` (the milestone's prior research recommendation) | Confirmed broken for repeat requests within a stateful session (see Summary); would need `stateless_http=True` *and* very careful task-boundary reasoning to even approach correctness, and still adds a file for no benefit over the SDK's own per-message threading. Rejected. |
| `asyncio.Lock` guarding a synchronous check-and-consume | No lock, rely on no-await critical section | Both are correct if the critical section never awaits; a lock is one line of defensive insurance against a future edit that adds an await mid-critical-section. Recommend the lock for robustness given CLAUDE.md's "handle more edge cases, not fewer." |
| `stateless_http=True` for HTTP transport | Default stateful sessions (`stateless_http=False`) | Stateful mode is fully compatible with the `Context.request_context.request` mechanism (verified above), but leaves one long-lived task + memory streams per session for the life of the process; a public demo endpoint with no auth has no way to force clients to close sessions. Stateless mode creates and tears down a transport per request (`_handle_stateless_request`), which is simpler to reason about for a single-purpose, one-domain-per-call demo tool and avoids any session-accumulation concern. `[ASSUMED]` -- this is a synthesis/recommendation, not a documented SDK best practice; the planner should confirm no MCP client used in Phase 13's manual test breaks under stateless mode (standard MCP clients, including `mcp-remote`, are spec-compliant with stateless HTTP). |

**Installation:** No new packages. If the planner wants extra certainty, `uv pip show mcp` confirms `1.28.1` and its dependency list matches the above.

**Version verification:** `mcp==1.28.1` confirmed installed via `.venv/lib/python3.12/site-packages/mcp-1.28.1.dist-info/METADATA` and pinned identically in `uv.lock`. No newer/older version drift risk this phase since the project already sits on the pin from Phase 9/10.

## Package Legitimacy Audit

No new external packages are introduced by this phase. `mcp` was already vetted in Phase 10 research (10-01 STATE.md note records the SUS-heuristic false positive resolved via `uv pip show` + Project-URL cross-check). `starlette` and `uvicorn` are transitive dependencies of the already-approved `mcp` package, not new direct installs -- no separate audit required per the Package Legitimacy Gate (it applies to packages this phase adds to `pyproject.toml`; this phase adds none).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
                          ┌─────────────────────────────────────────┐
                          │  src/mcp_server/__main__.py               │
                          │  argparse: --transport {stdio,http}       │
                          └───────────────┬───────────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │ stdio (default)                            │ http (new)
                    ▼                                             ▼
        asyncio.run(app.run_stdio_async())         asyncio.run(app.run_streamable_http_async())
                    │                                             │
                    │                              ┌──────────────┴───────────────┐
                    │                              │ FastMCP(host, port,           │
                    │                              │   stateless_http=True,        │
                    │                              │   transport_security=...)     │
                    │                              │ -> streamable_http_app()      │
                    │                              │    (Starlette, /mcp route)    │
                    │                              └──────────────┬───────────────┘
                    │                                             │  uvicorn serves
                    │                                             ▼
                    │                              incoming HTTP request (headers:
                    │                              Fly-Client-IP / X-Forwarded-For)
                    │                                             │
                    │                              StreamableHTTPSessionManager
                    │                              attaches raw Request to
                    │                              SessionMessage.metadata.request_context
                    │                                             │
                    └─────────────────────┬───────────────────────┘
                                          │  both transports converge here
                                          ▼
                    lowlevel Server._handle_request:
                    request_ctx.set(RequestContext(..., request=<Request|None>))
                    (fresh per message, inside the dispatching task)
                                          │
                                          ▼
                    get_account_evidence(domain, ctx: Context[...])
                      1. Account(domain) validation (fails -> ValueError, no quota charged)
                      2. limits.check_and_consume(client_ip_from(ctx), now())
                           - client_ip_from: ctx.request_context.request is None (stdio)
                             or missing/malformed headers -> SHARED_BUCKET
                           - per-IP rolling 60-min window (last 5 timestamps)
                           - global fixed-UTC-day counter
                           - refused -> raise ValueError("<rationing message w/ reset time>")
                      3. build_evidence_pack(account, exa=<clamped in demo mode>, browserbase)
                      4. return EvidencePack (unchanged wire format, D-07)
```

### Recommended Project Structure
```
src/mcp_server/
├── __init__.py
├── __main__.py     # + argparse --transport dispatch, host/port from Settings
├── server.py        # + Context[ServerSession, ThinDeps, Request] param type;
│                     #   build_server() gains host/port/stateless_http/transport_security kwargs
├── wiring.py         # + demo-mode Exa results clamp wrapper; unchanged ThinDeps shape
├── evidence.py        # unchanged this phase
└── limits.py         # NEW: rolling per-IP window + fixed UTC-day global counter,
                        #      client-IP extraction, injected clock
```

### Pattern 1: Client IP resolution via `Context`, not middleware

**What:** Read the per-request Starlette `Request` the SDK already threads to the tool call.
**When to use:** Any streamable-HTTP tool that needs request-scoped data (headers, client address). This is the SDK's own mechanism, confirmed by reading `mcp/server/lowlevel/server.py` and `mcp/server/streamable_http.py` directly against the installed `mcp==1.28.1`.
**Example:**
```python
# Source: mcp==1.28.1 installed source (.venv/lib/python3.12/site-packages/mcp/...),
# not official docs -- this pattern is undocumented; verified by reading the SDK.
from starlette.requests import Request
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from src.mcp_server.wiring import ThinDeps

SHARED_BUCKET_KEY = "shared"  # fail-closed bucket for stdio / missing / malformed headers


def resolve_client_ip(ctx: Context[ServerSession, ThinDeps, Request]) -> str:
    request = ctx.request_context.request
    if request is None:
        # stdio transport never attaches a Request; also true for any transport
        # where the metadata thread breaks (defensive, matches D-01's fail-closed rule)
        return SHARED_BUCKET_KEY

    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip and _looks_like_ip(fly_ip):
        return fly_ip

    xff = request.headers.get("x-forwarded-for")
    if xff:
        candidate = xff.rsplit(",", 1)[-1].strip()
        if _looks_like_ip(candidate):
            return candidate

    return SHARED_BUCKET_KEY
```
`_looks_like_ip` is a small validator (e.g. `ipaddress.ip_address(candidate)` wrapped in `try/except ValueError`) so a malformed header value fails closed instead of poisoning the bucket keyspace with garbage strings -- matches the locked "malformed headers fail closed" rule and PITFALLS.md pitfall 4's warning against a naive `.split(",")[0]`.

### Pattern 2: `FastMCP` HTTP transport construction (constructor kwargs, not middleware)

**What:** `host`, `port`, `stateless_http`, and `transport_security` are all `FastMCP.__init__` kwargs; `streamable_http_app()` and `run_streamable_http_async()` read them off `self.settings` internally. No ASGI middleware list exists on `streamable_http_app()`.
**When to use:** Any time the HTTP transport needs host/port/security configuration -- this phase's D-08/D-09.
**Example:**
```python
# Source: mcp==1.28.1 installed source, mcp/server/fastmcp/server.py
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

server = FastMCP(
    "poc-scraper",
    lifespan=lifespan,
    host=settings.mcp_http_host,       # default "127.0.0.1" (D-09)
    port=settings.mcp_http_port,        # default 8000 (D-09)
    stateless_http=True,                 # recommended; see Alternatives Considered
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"127.0.0.1:{settings.mcp_http_port}", f"localhost:{settings.mcp_http_port}"],
        allowed_origins=[
            f"http://127.0.0.1:{settings.mcp_http_port}",
            f"http://localhost:{settings.mcp_http_port}",
        ],
    ),
)
# __main__.py:
import asyncio
asyncio.run(server.run_streamable_http_async())
```
Note: `FastMCP` auto-builds an equivalent `TransportSecuritySettings` when `transport_security=None` and `host` is `127.0.0.1`/`localhost`/`::1` (confirmed in source) -- passing it explicitly per D-08 is still correct and makes the localhost allowlist visible/greppable in this project's own code rather than relying on an SDK default the reader has to go look up, and gives Phase 13 a single place to swap in the Fly hostname.

### Pattern 3: Rate limiter as a synchronous check-and-consume, no `await` inside

**What:** `limits.py`'s core operation reads and mutates counters in one call with zero `await` points, so asyncio's cooperative scheduling alone prevents interleaving; an `asyncio.Lock` around it is defense-in-depth, not strictly required, as long as the function body stays synchronous.
**When to use:** `limits.py`'s `check_and_consume(ip, now)` -- the exact seam D-04 specifies (after `Account` validation, before `collect_context`).
**Example:**
```python
# Illustrative shape, not a locked API (Claude's Discretion per CONTEXT.md)
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Callable

ClockFn = Callable[[], datetime]


@dataclass
class DemoLimiter:
    ip_limit: int
    daily_cap: int
    clock: ClockFn
    _ip_calls: dict[str, deque[datetime]] = field(default_factory=dict)
    _day: date | None = field(default=None)
    _day_count: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_and_consume(self, ip: str) -> LimitResult:
        async with self._lock:  # no other await inside; guards the whole read-modify-write
            now = self.clock()
            self._roll_day(now)
            bucket = self._ip_calls.setdefault(ip, deque(maxlen=self.ip_limit))
            cutoff = now - timedelta(hours=1)
            while bucket and bucket[0] < cutoff:
                bucket.popleft()  # prune stale entries for memory hygiene

            if len(bucket) >= self.ip_limit:
                reset_at = bucket[0] + timedelta(hours=1)
                return LimitResult.refused_ip(reset_at)
            if self._day_count >= self.daily_cap:
                return LimitResult.refused_daily()

            bucket.append(now)
            self._day_count += 1
            return LimitResult.allowed()

    def _roll_day(self, now: datetime) -> None:
        today = now.astimezone(UTC).date()
        if today != self._day:
            self._day = today
            self._day_count = 0
```
The `asyncio.Lock` here costs nothing (no other task can be mid-critical-section when this one runs, so it never actually contends) but protects the invariant permanently against a future edit that adds an `await` inside the `async with` block -- CLAUDE.md's "handle more edge cases, not fewer" favors keeping it.

### Anti-Patterns to Avoid
- **Custom ASGI middleware + `contextvars.ContextVar` for client IP:** confirmed broken across the stateful-session task boundary (see Summary). Use `Context.request_context.request` instead.
- **Calling `streamable_http_app()` twice** (once to `add_middleware`, once to serve): each call builds a *new* `Starlette` instance and a lazily-cached `StreamableHTTPSessionManager` the first time only -- calling it twice risks operating on two different session managers or discarding middleware silently. Not needed for this phase since no middleware is required, but worth flagging if a future phase reaches for `add_middleware`.
- **Relying on `FASTMCP_HOST`/`FASTMCP_PORT` env vars:** the SDK's internal `Settings(BaseSettings)` reads its own `FASTMCP_*`-prefixed env vars, a parallel config system to this project's `Settings`. Pass `host=`/`port=` as explicit constructor kwargs sourced from this project's `Settings` (`mcp_http_host`, `mcp_http_port`) so there is exactly one source of truth and no silent double-config surface.
- **`.split(",")[0]` on `X-Forwarded-For`:** trusts the leftmost, client-supplied entry (spoofable). Take the rightmost entry per the locked decision, and validate it looks like an IP before trusting it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Getting the client's HTTP request into a tool call | Custom ASGI middleware + `contextvars.ContextVar` | `ctx.request_context.request` (already threaded per-message by the SDK) | The custom approach is not just extra code, it is subtly wrong across session task boundaries (see Summary); the SDK's own mechanism is both simpler and correct |
| DNS-rebinding / Host-Origin validation | Hand-rolled Starlette middleware checking `Host`/`Origin` headers | `TransportSecuritySettings` passed to `FastMCP(...)` | Already implemented, tested, and covers the exact CVE-2025-66414/66416 gap this milestone's own prior research flagged; a hand-rolled version would duplicate exactly this logic with more risk of a subtle bypass |
| uvicorn/ASGI server bootstrap | Manual `uvicorn.Config`/`uvicorn.Server` wiring | `FastMCP.run_streamable_http_async()` (already does exactly this, reading `self.settings.host/port/log_level`) | One less place to get host/port wiring wrong; matches STACK.md's existing guidance against hand-mounting a separate Starlette/FastAPI app |
| Rate limiting | A rate-limiting library (`slowapi`, etc.) or Redis | Plain `dict`/`deque`/`datetime` state in `limits.py` | Milestone-locked decision (design spec + `.planning/research/STACK.md`): traffic ceiling (25/day) does not justify any dependency; an external store would also violate the explicit "no external storage" milestone constraint |

**Key insight:** every "how do I wire X" question in this phase turns out to already be a constructor kwarg or an existing per-message mechanism inside the SDK. The only code this phase genuinely needs to hand-write is `limits.py` itself (rate-limit state, which is intentionally out of scope for any library per the locked decisions) and a thin IP-extraction helper.

## Common Pitfalls

### Pitfall 1: Assuming a contextvar set in ASGI middleware reaches the tool call
**What goes wrong:** IP resolution silently returns `None`/stale values for every request after the first in a session (stateful mode), or works by accident only in stateless mode with exactly the right timing.
**Why it happens:** Contextvars propagate by value-copy at task-spawn time; the SDK spawns the per-session message-processing task once, before most requests in that session even arrive.
**How to avoid:** Use `ctx.request_context.request` (Pattern 1). Do not build a middleware for this.
**Warning signs:** A `ClientIPMiddleware` class or a module-level `contextvars.ContextVar` appears anywhere in `src/mcp_server/`.

### Pitfall 2: `streamable_http_app(middleware=...)` does not exist
**What goes wrong:** `TypeError: streamable_http_app() got an unexpected keyword argument 'middleware'`.
**Why it happens:** The milestone's prior research (pre-dating this phase) assumed a documented kwarg that isn't present in the installed `mcp==1.28.1`; confirmed by reading the source directly.
**How to avoid:** Pass `transport_security=`, `host=`, `port=`, `stateless_http=` to the `FastMCP(...)` constructor instead (Pattern 2).
**Warning signs:** Any `streamable_http_app(middleware=` call in a draft PLAN.md.

### Pitfall 3: Fly's own XFF semantics make "rightmost" a true fallback, not a peer of `Fly-Client-IP`
**What goes wrong:** Treating XFF-rightmost as equally trustworthy as `Fly-Client-IP` for a Fly-hosted deployment.
**Why it happens:** Per Fly.io's own docs `[CITED: fly.io/docs/networking/request-headers]`, when no other reverse proxy sits in front of Fly, `X-Forwarded-For`'s rightmost entry is populated by Fly's own edge and is generally a reasonable proxy for the connecting client -- but Fly explicitly recommends `Fly-Client-IP` as the primary source specifically for this project's topology (no external proxy in front of Fly), and documents that `Fly-Client-IP` becomes unreliable (reflects the external proxy's IP, not the real client) only if a *different* reverse proxy is later placed in front of Fly. XFF should be read as a documented, secondary fallback (useful mainly for local `make mcp-http` testing where `Fly-Client-IP` is never present), not a co-equal source.
**How to avoid:** Implement exactly the locked order: `Fly-Client-IP` first, `X-Forwarded-For` rightmost only when the first is absent, fail closed on anything malformed. Do not swap the priority.
**Warning signs:** Code that checks XFF before `Fly-Client-IP`, or treats both as equally authoritative in tests.

### Pitfall 4: Missing the third `Context` type parameter breaks strict-mypy typing on `.request`
**What goes wrong:** `ctx.request_context.request` type-checks as `Any` under strict mypy (silently swallowing a real bug class -- e.g. calling `.headers` on `None` without a null check) because `RequestT` defaults to `Any` when only two of `Context`'s three generic parameters are supplied.
**Why it happens:** Phase 10's tool signature is `Context[ServerSession, ThinDeps]` (2 params); `Context` is `Generic[ServerSessionT, LifespanContextT, RequestT]` (3 params, `RequestT` default `Any`).
**How to avoid:** Annotate the tool's `ctx` parameter as `Context[ServerSession, ThinDeps, Request]` (importing `starlette.requests.Request`), so `.request` types as `Request | None` and mypy forces the `None` check.
**Warning signs:** `# type: ignore` near the IP-resolution code, or mypy passing despite a missing `if request is None` branch.

### Pitfall 5: Letting the check-and-consume critical section drift asynchronous
**What goes wrong:** A future edit adds an `await` between the "check" and the "consume" step (e.g., an async log call, an async metrics push) -- reintroducing exactly the race criterion 4 requires protecting against, silently, because the code still "looks" atomic.
**Why it happens:** Nothing in Python's type system flags "this async function now has an await where it didn't before."
**How to avoid:** Keep `check_and_consume` wrapped in an `asyncio.Lock` (Pattern 3) even though the current body doesn't strictly need it -- the lock is what actually survives a future edit; a comment alone does not.
**Warning signs:** A concurrency test (two simultaneous same-IP calls) that passes today but would silently stop protecting the invariant after a refactor with no test failure to catch it.

### Pitfall 6: Rolling-window reset time computed from the wrong end of the deque
**What goes wrong:** Reset time reported to the caller is wrong (either always "now" or the newest, not oldest, timestamp), giving a misleading `resets at HH:MM UTC` message.
**Why it happens:** D-05's reset time is `oldest timestamp + 1h`; a `deque` appended on the right has its oldest entry at index 0 (left) -- easy to compute from the wrong end if the append/prune direction isn't kept straight.
**How to avoid:** Prune expired entries from the left (`bucket.popleft()` while `bucket[0] < cutoff`) before checking length, and compute reset time as `bucket[0] + timedelta(hours=1)` -- the *remaining* oldest entry after pruning, not the raw first-ever call.
**Warning signs:** A unit test that only ever appends one call to a bucket won't catch this; the phase's tests need a fixture with several calls at different times inside the window.

## Code Examples

### `__main__.py` transport dispatch (illustrative, not locked)
```python
# Source: derived from installed mcp==1.28.1 (run_stdio_async / run_streamable_http_async
# both exist as methods on FastMCP; asyncio.run matches this file's existing stdio pattern)
import argparse
import asyncio

from src.config import get_settings
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import make_thin_lifespan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    args = parser.parse_args()

    settings = get_settings()
    resolve_and_log_tier(settings)
    app = build_server(
        lifespan=make_thin_lifespan(settings),
        settings=settings if args.transport == "http" else None,
    )
    if args.transport == "http":
        asyncio.run(app.run_streamable_http_async())
    else:
        asyncio.run(app.run_stdio_async())
    return 0
```

### Fixed-UTC-day rollover (reuses the codebase's existing `datetime.now(UTC)` convention)
```python
# Source: matches existing convention in src/clients/exa_client.py (datetime.now(UTC))
from datetime import UTC, datetime

def current_utc_day(now: datetime) -> "date":
    return now.astimezone(UTC).date()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| DNS-rebinding protection opt-in / undocumented | Auto-enabled `TransportSecuritySettings` for localhost binds; still requires explicit `allowed_hosts` for non-localhost (e.g. Fly hostname, Phase 13) | `mcp` 1.23.0 (per CVE-2025-66414/66416 fix, corroborated by milestone research) | This project is already on `mcp==1.28.1`, past the fix; front-loading explicit `TransportSecuritySettings` now (D-08) still matters for the local `127.0.0.1` case being visible in code rather than implicit |
| `middleware=` kwarg assumed on `streamable_http_app()` | No such kwarg exists; `transport_security`/`host`/`port`/`stateless_http` are constructor-level | Confirmed this research pass against installed 1.28.1 (not a version change -- a research correction) | Removes an entire planned component (`ClientIPMiddleware`) from the phase's scope |

**Deprecated/outdated:**
- The standalone `fastmcp` PyPI package's `get_http_request()`/`get_http_headers()` helpers do not exist in the official `mcp` SDK this project uses -- do not reach for them or add the `fastmcp` package alongside `mcp` (milestone research already flagged this; confirmed still true).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `stateless_http=True` is the better default for the demo HTTP transport (vs. the SDK's stateful default) | Architecture Patterns (Alternatives Considered) | Low -- both modes are confirmed compatible with the `Context.request_context.request` IP-resolution mechanism; if stateless mode causes friction with a specific MCP client during manual verification, switching back to stateful (`stateless_http=False`, the SDK default) requires only a one-line change, no redesign |
| A2 | Fly's own edge-appended XFF rightmost entry is a reasonable (if secondary) proxy for the client IP in this project's topology (no proxy in front of Fly) | Common Pitfalls #3 | Low -- this only affects the fallback path used when `Fly-Client-IP` is absent; the locked fail-closed behavior on malformed/ambiguous headers already bounds the damage of a wrong assumption here to "falls into the shared bucket," never a security gap |

**If this table is empty:** N/A -- two low-risk assumptions logged above; everything else in this research (the middleware/contextvar finding, the constructor-kwarg shape, the transitive-dependency finding) was verified by directly reading the installed `mcp==1.28.1` source and `uv.lock`, not inferred from training data.

## Open Questions

1. **Does the manual Phase 13 real-client verification (Claude Desktop / `npx mcp-remote`) behave identically under `stateless_http=True` vs the SDK default?**
   - What we know: both modes are spec-compliant and the client-IP mechanism works identically in both (verified from source).
   - What's unclear: whether any specific MCP client this project will demo against (Claude Desktop, `mcp-remote`) has an undocumented preference for session affinity.
   - Recommendation: ship `stateless_http=True` for `make mcp-http`/`make mcp-demo` this phase; if Phase 13's live verification surfaces a client-compatibility issue, flip the one kwarg -- low switching cost, so this is not worth blocking on now.

2. **Exact clamp-injection shape for the Exa results-count limit (D-03).**
   - What we know: `collect_context()` is shared by both the full BYOK pipeline and the MCP thin tier (Phase 9 D-05/D-06), and currently calls `exa.search_about(domain)` / `exa.search_news(domain)` with no explicit `num_results`, relying on `ExaClient`'s own defaults (5 and 8 respectively).
   - What's unclear: whether the planner threads a `num_results` parameter through `collect_context()`'s signature (touching the shared pipeline code) or wraps `ExaLike` in a small demo-clamping adapter constructed only in `make_thin_lifespan` when `settings.mcp_demo_mode` is true (touching only `src/mcp_server/wiring.py`).
   - Recommendation: prefer the wrapper-at-the-wiring-layer approach -- it keeps `collect_context()`'s signature and the full BYOK pipeline completely untouched by a demo-only concern, consistent with Phase 9's existing pattern of deciding `NullBrowserbase` vs real `BrowserbaseClient` entirely inside `make_thin_lifespan`.

3. **Does `Settings` need a new `mcp_http_host` field, or is `127.0.0.1` a module constant?**
   - What we know: D-09 says "Local HTTP defaults: bind `127.0.0.1`, port `8000`, **both env-overridable**." The design spec's own "Config and wiring changes" section (quoted in canonical refs) only lists `mcp_http_port` as a new `Settings` field, not a host field.
   - What's unclear: this looks like a real gap between the original design spec and D-09's explicit requirement -- D-09 requires the host to be env-tunable too, which needs its own `Settings` field (e.g. `mcp_http_host: str = "127.0.0.1"`) not present in the design spec's enumerated field list.
   - Recommendation: the planner should add `mcp_http_host` as a new defaulted `Settings` field (same pattern as `mcp_http_port`) to satisfy D-09 literally; flagging this explicitly so it isn't missed as "not in the design spec's list."

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` (with bundled `FastMCP`, streamable-HTTP transport) | HOST-02, HOST-04 | Yes | 1.28.1 (pinned `>=1.28,<2.0`) | -- |
| `starlette` | `Context.request_context.request`, DNS-rebinding checks | Yes (transitive via `mcp`) | resolved by `uv.lock`, `py.typed` present | -- |
| `uvicorn` | Serves the streamable-HTTP ASGI app | Yes (transitive via `mcp`) | 0.51.0 | -- |
| Fly.io platform (for `Fly-Client-IP` header) | HOST-04's primary IP source | N/A this phase (local dev only; Phase 13 deploys) | -- | Local `make mcp-http`/`make mcp-demo` testing never receives `Fly-Client-IP`; the XFF-rightmost fallback (or fail-closed shared bucket) is what's actually exercised locally -- worth an explicit test case, not just the Fly path |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `Fly-Client-IP` is unavailable in every local test run by construction (no Fly edge locally); this is expected and already covered by the locked fail-closed / XFF-fallback design, not a gap to fix.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 8.2+, `pytest-asyncio` (auto mode), `respx` for httpx mocking |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_limits.py tests/functional/test_mcp_server.py -x` |
| Full suite command | `make test` (`uv run pytest -m "not smoke"`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HOST-02 | `make mcp-http` serves the same tool over streamable HTTP as stdio | functional | `uv run pytest tests/functional/test_mcp_server.py -k http -x` | Wave 0 (extend existing file, or new `tests/functional/test_mcp_http_transport.py`) |
| HOST-04 | Per-IP hourly limit, rolling window, injected clock | unit | `uv run pytest tests/unit/test_limits.py -x` | Wave 0 -- new file |
| HOST-04 | Global UTC-day cap, rollover at midnight | unit | `uv run pytest tests/unit/test_limits.py -k daily -x` | Wave 0 -- same new file |
| HOST-04 | Client IP resolution: `Fly-Client-IP`, XFF rightmost, missing/malformed fail-closed, stdio `None` | functional | `uv run pytest tests/functional/test_mcp_server.py -k client_ip -x` | Wave 0 -- new test cases; use `httpx.AsyncClient(transport=httpx.ASGITransport(app=server.streamable_http_app()))` for the HTTP header path, in-memory client (`mcp.shared.memory`) for the stdio/`None` path |
| HOST-04 | Concurrent same-IP calls: exactly one refusal at the boundary | functional | `uv run pytest tests/functional/test_mcp_server.py -k concurrent -x` | Wave 0 -- `asyncio.gather` of N simultaneous `check_and_consume` calls against one `DemoLimiter` instance |
| HOST-04 | Rationing errors carry reset time, `isError: true`, plain-message style | functional | `uv run pytest tests/functional/test_mcp_server.py -k rationing -x` | Wave 0 |
| HOST-04 | Exa exhaustion (402/429 post-retry) borrows the daily-cap wording in demo mode only | functional | `uv run pytest tests/functional/test_mcp_server.py -k exhaustion -x` | Wave 0 |
| HOST-04 | Demo-mode Exa results clamp applied regardless of transport | unit/functional | `uv run pytest tests/functional/test_mcp_server.py -k demo_clamp -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_limits.py tests/functional/test_mcp_server.py -x`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green (`make test`) plus `make typecheck` (strict mypy, no new overrides) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_limits.py` -- covers HOST-04's window math, injected clock, UTC-day rollover, reset-time computation
- [ ] New test cases in `tests/functional/test_mcp_server.py` (or a new `tests/functional/test_mcp_http_transport.py`) -- covers HOST-02's HTTP-transport parity, and HOST-04's client-IP resolution, concurrency, and rationing-message paths
- [ ] No new fixtures needed -- `httpx.ASGITransport` (already a transitive capability of the existing `httpx>=0.27.0` pin) plus the existing `FakeExa`/`NullBrowserbase`/`mcp.shared.memory` patterns cover every new test surface

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Explicitly out of scope per REQUIREMENTS.md ("OAuth 2.1 on hosted endpoint" listed Out of Scope); rate limits are the only gate (design spec, confirmed unchanged) |
| V3 Session Management | Partial | Streamable-HTTP session IDs are SDK-managed (`mcp_session_id`, UUID4); `stateless_http=True` (recommended) sidesteps most session-lifecycle concerns entirely by not maintaining sessions across requests |
| V4 Access Control | No | Read-only, single-tool public surface; no per-user access control this milestone |
| V5 Input Validation | Yes | `Account` validator (Phase 10, unchanged) for `domain`; new: client-IP header parsing must validate the extracted string is a plausible IP (`ipaddress.ip_address`) before using it as a dict key, per Pitfall/Pattern 1 above |
| V6 Cryptography | No | No cryptographic operations in this phase |
| V13 API and Web Service (rate limiting, DNS rebinding) | Yes | `TransportSecuritySettings` (DNS-rebinding, D-08) and `limits.py` (rate limiting, HOST-04) are exactly this category's controls |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DNS rebinding (CVE-2025-66414/66416 class) against a browser reaching `localhost`/the public HTTP endpoint | Spoofing | `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[...])` explicit allowlist (D-08); already the SDK's own fix from 1.23.0, front-loaded explicitly here |
| `X-Forwarded-For` spoofing to bypass per-IP rate limiting | Tampering | Prefer `Fly-Client-IP`; rightmost-XFF-only fallback; fail closed on malformed/absent headers into the shared bucket (HOST-04, Pattern 1) |
| Rate-limit counter race under concurrent requests undercounting refusals | Tampering (of the rationing invariant) | Synchronous check-and-consume critical section, optionally `asyncio.Lock`-guarded (Pattern 3, criterion 4) |
| Error payload leaking stack traces/env names/key fragments on the new rationing error paths | Information Disclosure | Reuse Phase 10's existing sanitizing except-chain (D-06/D-07 here explicitly route rationing refusals through the same `isError: true` plain-message path, no new error-handling surface) |
| Exa credit-pool exhaustion masquerading as a broken server instead of a rationed one | Denial of Service (economic) | D-07: exhaustion (402/429 post-tenacity-retry) in demo mode reuses the daily-cap wording so the public URL "looks rationed, never broken" |

## Sources

### Primary (HIGH confidence)
- `.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py` (mcp==1.28.1, read directly) -- `FastMCP.__init__` kwargs (`host`, `port`, `stateless_http`, `transport_security`), `Settings(BaseSettings)` env-prefix `FASTMCP_`, `streamable_http_app()` body (no `middleware=` kwarg), `run_streamable_http_async()`/`run_stdio_async()`/`run()` bodies, `Context`/`get_context()` generic typing (`Context[ServerSession, LifespanResultT, Request]`)
- `.venv/lib/python3.12/site-packages/mcp/server/transport_security.py` -- `TransportSecuritySettings` fields, `TransportSecurityMiddleware` internal validation logic
- `.venv/lib/python3.12/site-packages/mcp/server/streamable_http_manager.py` -- `_handle_stateful_request`/`_handle_stateless_request`, confirming the persistent per-session `run_server` task spawned once via `task_group.start(...)`
- `.venv/lib/python3.12/site-packages/mcp/server/streamable_http.py` -- both message-handling branches attaching `ServerMessageMetadata(request_context=request)` per HTTP request
- `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` -- `request_ctx: contextvars.ContextVar[RequestContext]`, `_handle_request`'s per-message `request_ctx.set(...)` using `message.message_metadata.request_context`
- `.venv/lib/python3.12/site-packages/mcp/shared/context.py` -- `RequestContext` dataclass shape (`request: RequestT | None = None`)
- `uv.lock` (project file) -- `mcp` 1.28.1 pin, and its direct dependency list including `starlette`, `uvicorn`, `sse-starlette`
- Existing project source: `src/mcp_server/server.py`, `__main__.py`, `wiring.py`, `evidence.py`, `src/config.py`, `src/enrich.py`, `src/clients/exa_client.py`, `src/clients/protocols.py`, `Makefile`, `tests/functional/test_mcp_server.py` (all read directly this session)

### Secondary (MEDIUM confidence)
- [Request headers -- Fly.io Docs](https://fly.io/docs/networking/request-headers/) `[CITED]` -- `Fly-Client-IP` vs `X-Forwarded-For` semantics, rightmost-entry behavior on Fly's platform

### Tertiary (LOW confidence)
- None used this session beyond the one cited Fly.io doc lookup above; all SDK-behavior claims were verified against the installed package source rather than left as web-search-only claims.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- confirmed by direct inspection of `.venv` and `uv.lock`, not training-data assumption
- Architecture (client-IP resolution, transport construction): HIGH -- confirmed by reading the exact dispatch path across four SDK source files; this is the phase's core uncertainty and it is now source-verified, not inferred
- Pitfalls: HIGH for SDK-mechanism pitfalls (1, 2, 4, 6 -- source-verified); MEDIUM for the Fly XFF nuance (pitfall 3 -- one official doc page, not independently cross-checked against a second source)
- Rate-limiter concurrency reasoning (asyncio single-thread cooperative scheduling guarantee): HIGH -- this is a well-established CPython/asyncio property, not project-specific

**Research date:** 2026-07-16
**Valid until:** 30 days for the SDK-mechanism findings (tied to the pinned `mcp>=1.28,<2.0`; a major-version bump to 2.0 could change internals -- re-verify against source if the pin ever moves), 90 days for the Fly.io header-semantics finding (platform docs, slower-moving)
</content>
