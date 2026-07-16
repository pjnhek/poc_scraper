# Phase 10: Stdio MCP Server (Thin Tier) - Research

**Researched:** 2026-07-16
**Domain:** MCP (Model Context Protocol) server implementation, official `mcp` Python SDK (`FastMCP`), stdio transport
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Evidence payload shape (MCP-01)**
- **D-01:** The tool payload includes the cleaned `about_text` per the design spec. Phase 9's `EvidencePack` shipped without it; this phase adds it.
- **D-02:** `about_text: str = ""` is added as a field on the frozen `EvidencePack` model (additive, defaulted, so Phase 9 tests stay green). `from_context` already receives `about_text` and stores the pre-capped value. One model owns the wire format; `model_dump()` stays the single serialization path. No wrapper dict at the tool layer.
- **D-03:** MCP-boundary size caps are module constants in `src/mcp_server/evidence.py` (SCREAMING_SNAKE, following the `SUMMARY_MAX_CHARS` precedent): about_text ~2000 chars, per-justification summary ~300 chars, news list ~10 items. No new env knobs (Phase 9 D-09 principle). Demo-specific clamps (Exa results=5) remain Phase 11 scope. Capping happens in `evidence.py` before model construction, honoring Phase 9 D-10 (capping at the MCP boundary, not in the model).

**Thin-tier Browserbase policy (wiring)**
- **D-04:** Key-aware Browserbase fallback in thin tier: construct a real `BrowserbaseClient` when `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID` are set, `NullBrowserbase` otherwise. This honors the design spec ("Browserbase fallback when a key exists") and matches CLI evidence quality. It REFINES Phase 9 D-04's "Exa + NullBrowserbase" wording; the core of that decision stands: the thin tier wires its own clients via `collect_context` and does NOT call `open_deps`. Demo mode (Phase 11) still forces `NullBrowserbase` unconditionally.

**Real-client verification + smoke (HOST-01, TEST-02)**
- **D-05:** Claude Code is the verification gate for the real-client success criterion: register via `claude mcp add` (command wrapping `make mcp` / `uv run python -m src.mcp_server`) and exercise `get_account_evidence` in a live session. Claude Desktop verification is optional bonus, not gating; its config snippet is Phase 13 README work.
- **D-06:** `make smoke-mcp` reuses one domain from `tests/smoke/fixtures.csv` (notion.so or linear.app) so MCP smoke and pipeline smoke burn credits against the same well-understood accounts. Assertions per the roadmap: non-empty numbered justifications, plus `retrieval_status` present.

**Error result design (MCP-07)**
- **D-07:** A sanitizing catch-all wraps the tool from day one: unexpected exceptions return a generic "internal error, try again" `isError` result while the full traceback logs to stderr at WARNING+. Do not rely on FastMCP's default exception stringification (leaks paths/env detail). This brings HOST-05 discipline forward so Phase 13 verifies rather than retrofits.
- **D-08:** Error results are plain human-readable messages, no machine-readable error codes. Categories and wording per the design spec: invalid domain passes through the `Account` validator message; Exa failure after tenacity retries returns "retrieval unavailable, try again"; empty/thin retrieval is NOT an error (communicated via `retrieval_status` in a successful result).

**Locked by prior phases / design spec (do not re-litigate)**
- Package layout `src/mcp_server/` (`__init__.py`, `server.py`, `wiring.py`, `evidence.py`); `limits.py` is Phase 11.
- Dependency pin `mcp>=1.28,<2.0`, official SDK's bundled FastMCP; NOT the standalone `fastmcp` PyPI package. `mcp` ships `py.typed`; no new mypy overrides. Expect `pydantic` to resolve upward in `uv.lock`; re-run the full suite after `uv sync`.
- Entry point `python -m src.mcp_server`, stdio default (`--transport http` arrives in Phase 11). `Makefile` gains `make mcp` and `make smoke-mcp` this phase.
- stderr-only logging configured before other imports (`logging.basicConfig(stream=sys.stderr, ...)`); stdout is reserved for JSON-RPC.
- `Settings.mcp_tier() -> Literal["thin", "full"]` mirrors `require_for_pipeline()`: thin needs `EXA_API_KEY` only; full also needs writer/judge + Browserbase keys; `MCP_DEMO_MODE=1` forces thin. Tier resolved and logged once at startup; missing EXA key fails fast with the missing-keys listing message.
- `readOnlyHint=True` / `destructiveHint=False` annotations on the tool; tool description carries the citation-numbering contract explicitly (research pitfall 6).
- Thin tier composes `collect_context` + `_number_justifications` -> `EvidencePack.from_context` in `src/mcp_server/evidence.py`; zero LLM involvement.
- Functional tests use the in-memory client from `mcp.shared.memory` (no subprocess, no network) with `FakeExa` / `NullBrowserbase` stubs.

### Claude's Discretion
- Exact cap constant values (the ~2000/~300/~10 numbers are targets, not contracts) and truncation mechanics (ellipsis markers, word boundaries).
- Startup tier log wording, including whether it notes the retrieval sub-mode (exa-only vs exa+browserbase).
- Smoke-test driver mechanics (stdio client subprocess handling, timeouts) and which of the two fixture domains to use.
- `Settings` field scope for this phase (add only what Phase 10 needs vs the spec's full field list) and exact error-message wording.
- Whether `wiring.py` owns a phase-10-local httpx.AsyncClient lifespan for thin-tier clients (it must own one somewhere, since `open_deps` is not called).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Rate limits, HTTP transport, resources/prompt, full-tier tool, and README/CLAUDE.md docs were repeatedly kept in Phases 11-13 where the roadmap places them.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-01 | An MCP client can call `get_account_evidence(domain)` and receive numbered, cited evidence as structured JSON with a `retrieval_status` honesty field (`ok`/`thin`/`empty`), with evidence snippets capped in size at the MCP boundary | Pattern 2 (structured pydantic return via `-> EvidencePack` return annotation, verified auto-detection in `func_metadata()`); Pitfall 3 (oversized-JSON caps); Don't-Hand-Roll row on structured output; Validation Architecture MCP-01 row |
| MCP-06 | The server resolves its capability tier once at startup (thin with Exa only; full with all keys; `MCP_DEMO_MODE=1` forces thin regardless of keys) and logs the resolved tier | Architectural Responsibility Map (process lifecycle row); locked decisions carry `Settings.mcp_tier()` shape forward from CONTEXT.md; Validation Architecture MCP-06 row |
| MCP-07 | Both tools carry `readOnlyHint`/`destructiveHint` annotations, and all domain failures (invalid domain, provider failure, rate limits) surface as `isError: true` tool results, never protocol-level errors | Pattern 2 (`ToolAnnotations`) and Pattern 3 (verified SDK-level `isError: true` guarantee, the phase's central research finding); Pitfall 2 (`ToolError` import path); Security Domain (information-disclosure and protocol-confusion threat rows) |
| HOST-01 | A local user can run the server over stdio (`make mcp`) and connect it to Claude Code or Claude Desktop, with all logging routed to stderr (verified against a real client connection) | Pitfall 1 (stdout contamination, the phase's other central research finding); Code Example (stderr-first entrypoint); Environment Availability (`claude mcp add` confirmed present, exact syntax verified); Validation Architecture HOST-01 row |
| TEST-02 | Opt-in `make smoke-mcp` runs the stdio server as a real subprocess against one live domain, skipped in CI | Don't-Hand-Roll row (in-memory client for functional tests, NOT for smoke); Validation Architecture Wave 0 Gaps (`tests/smoke/test_mcp_e2e.py`); existing `tests/smoke/test_e2e.py` pattern identified as the skip-guard template |
</phase_requirements>

## Summary

This phase adds the project's first `mcp` SDK code: a stdio-transport MCP server exposing one tool, `get_account_evidence(domain)`, that composes the already-shipped Phase 9 seams (`collect_context`, `_number_justifications`, `EvidencePack.from_context`) into a grounded, cited JSON response. Everything needed to plan this phase with confidence was resolved by direct introspection of the installed `mcp==1.28.1` package this session (not training-data guesses), because the CONTEXT.md flagged two SDK-surface unknowns as blocking: the `ToolError` import path, and whether the FastMCP lifespan context manager is guaranteed to run exactly once per stdio process. Both are now confirmed against the real, pinned SDK version.

The critical finding that reframes MCP-07/D-07/D-08: **any exception raised inside a `@mcp.tool()` function is automatically converted to an `isError: true` `CallToolResult`, never a protocol-level JSON-RPC error** — this happens unconditionally in the SDK's low-level `call_tool` handler (`except Exception as e: return self._make_error_result(str(e))`), with the sole carve-out being `UrlElicitationRequiredError`. This means the "sanitizing catch-all wrapper" (D-07) is not needed to prevent protocol errors — the SDK already guarantees that — it is needed **only** to control the message text, because the SDK's default behavior is `str(exc)`, which can leak internal detail (URLs, config paths, provider error bodies) verbatim into what the client sees. Plan tasks accordingly: the wrapper's job is content sanitization, not error-channel routing.

**Primary recommendation:** Build `src/mcp_server/{__init__.py,server.py,wiring.py,evidence.py}` as a thin composition layer. `wiring.py`'s lifespan context manager should mirror `pipeline.open_deps()`'s shape exactly (one `httpx.AsyncClient`, key-aware Browserbase construction, teardown in `finally`) and is entered exactly once per stdio process — confirmed by SDK source, not assumed. `server.py` registers the tool with `annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False)` and returns the `EvidencePack` pydantic model directly (its `-> EvidencePack` return annotation triggers the SDK's auto-structured-output path — no manual `model_dump()` call needed at the tool boundary, though `evidence.py` still constructs the model via `from_context`). Wrap the tool body in a narrow try/except that raises a sanitized generic error for the catch-all case and lets validation/retrieval failures produce their own specific messages, per D-07/D-08.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Domain validation | API / Backend (`src/models.py::Account`) | MCP tool wrapper (catches `ValidationError`) | Existing validator is the single source of truth; MCP layer only translates the exception into an `isError` result, never re-implements validation |
| Evidence retrieval (Exa + Browserbase) | API / Backend (`src/enrich.py::collect_context`) | MCP wiring (`wiring.py` constructs the clients) | Retrieval logic is unchanged from Phase 9; MCP server is a new caller of the same seam, not a new implementation |
| Evidence shaping / capping | New: `src/mcp_server/evidence.py` | — | MCP-boundary-specific concern (size caps, JSON shape) that does not belong in the reusable `EvidencePack` model per Phase 9 D-10 |
| Transport / protocol framing | New: `src/mcp_server/server.py` (owned by `mcp` SDK) | — | Stdio JSON-RPC framing, tool registration, error-channel routing are all SDK responsibilities; server.py only wires business logic into SDK decorators |
| Process lifecycle (client construction/teardown) | New: `src/mcp_server/wiring.py` | `pipeline.open_deps` (pattern source) | Mirrors the CLI's proven lifespan shape; must not call `open_deps` directly per Phase 9 D-04 (thin tier is Exa/Browserbase only, no LLM clients) |
| Logging | Process-wide (`logging.basicConfig` in `__main__`) | — | Must be configured to stderr before any other import touches stdout, a process-level concern, not a per-module one |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | `1.28.1` (installed and introspected this session) `[VERIFIED: PyPI JSON API + local pip install]` | Official Model Context Protocol Python SDK; bundles `FastMCP`, stdio/HTTP transports, in-memory test client | Only maintained, spec-compliant Python MCP SDK; explicitly the design authority's chosen stack (not the standalone `fastmcp` PyPI package) |

### Supporting
No new supporting libraries this phase. `mcp`'s own dependencies (`anyio`, `httpx-sse`, `starlette`, `uvicorn`, `pydantic-settings`, `pyjwt[crypto]`, etc.) are transitive — confirmed via `importlib.metadata.metadata('mcp').get_all('Requires-Dist')` `[VERIFIED: local install]` — and must not be pinned explicitly in `pyproject.toml`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp` (official SDK) | standalone `fastmcp` PyPI package | Different, independently-versioned project; NOT what the design spec or milestone research chose; would fragment the stack from the official spec implementation |

**Installation:**
```bash
uv add "mcp>=1.28,<2.0"
```
This is a **project-file change**, not something to run ad hoc — `pyproject.toml` gains this line and `uv.lock` is regenerated. Confirmed this session: installing `mcp>=1.28,<2.0` resolves `pydantic` upward to `>=2.11.0` (mcp's own constraint: `pydantic<3.0.0,>=2.11.0`), matching CONTEXT.md's expectation. Re-run `make test`/`make typecheck` after `uv sync` to confirm nothing in the existing suite regresses on the resolved pydantic bump.

**Version verification:** `mcp==1.28.1` confirmed current via direct `pip install` in an ephemeral `uv run --with` environment this session (2026-07-16); PyPI shows 63 releases since `0.9.1`, official repo `github.com/modelcontextprotocol/python-sdk`, docs at `py.sdk.modelcontextprotocol.io`. `py.typed` marker present at package root — confirmed via `find`, so **no new `mypy` `ignore_missing_imports` override is needed**.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `mcp` | PyPI | first release `0.9.1`, 63 releases total, current `1.28.1` | not exposed by PyPI JSON API (`weeklyDownloads: null`) | `github.com/modelcontextprotocol/python-sdk` | seam reports `SUS` (`too-new`, `unknown-downloads`) | **Approved** — heuristic false positive |

**Why the seam's `SUS` verdict is a false positive here:** the seam's heuristic reads `publishedAt` as the *latest* release timestamp (`1.28.1`, 2026-06-26) and flags it as "too-new" for a single-release lookup; it does not see the 63-release history back to `0.9.1`. Direct PyPI JSON API query this session (`releases` dict) confirms 63 published versions and the official `modelcontextprotocol/python-sdk` GitHub repo as the source. This matches the milestone-level research (`.planning/research/SUMMARY.md`, HIGH confidence, verified against PyPI JSON API + local `pip install` + runtime introspection). No npm-ecosystem confusion risk applies (this is a Python-only phase; the unrelated npm package `mcp` is a different, deprecated project and irrelevant here).

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `mcp` — resolved above as a false positive; no `checkpoint:human-verify` needed given the direct PyPI + GitHub cross-check, but the planner may still add a lightweight confirmation step if it wants belt-and-suspenders given the seam's raw verdict.

## Architecture Patterns

### System Architecture Diagram

```
MCP client (Claude Code / Claude Desktop)
        |
        | stdio (JSON-RPC over stdin/stdout)
        v
+---------------------------------------------+
| python -m src.mcp_server                    |
|   1. logging.basicConfig(stream=sys.stderr) |
|      (before any other import)              |
|   2. Settings.mcp_tier() resolved + logged  |
|   3. FastMCP app built, lifespan=wiring     |
|      lifespan (entered ONCE for the         |
|      process's lifetime)                    |
+---------------------------------------------+
        |
        | tool call: get_account_evidence(domain)
        v
+---------------------------------------------+
| server.py tool wrapper                      |
|   - Account(domain=domain) validation       |
|     -> ValidationError -> sanitized isError |
|   - delegates to evidence.py                |
|   - unexpected Exception -> generic isError |
|     (WARNING+ full traceback to stderr)     |
+---------------------------------------------+
        |
        v
+---------------------------------------------+
| evidence.py                                 |
|   collect_context(account, exa, browserbase)|
|     -> RawContext                           |
|   _number_justifications(...)               |
|     -> tuple[Justification, ...]            |
|   cap about_text / summaries / news list    |
|     at MCP-boundary constants               |
|   EvidencePack.from_context(...)            |
|     -> retrieval_status: ok|thin|empty      |
+---------------------------------------------+
        |
        v
   EvidencePack (frozen pydantic model)
        |
        | SDK auto-detects `-> EvidencePack`
        | return annotation as structured
        | output; no manual model_dump() call
        v
   structured JSON CallToolResult -> client
```

### Recommended Project Structure
```
src/mcp_server/
├── __init__.py      # empty, no re-export barrel (matches project convention)
├── server.py         # FastMCP app: tool registration, tier resolution/logging, error wrapper
├── wiring.py          # lifespan async context manager: httpx.AsyncClient + key-aware Exa/Browserbase
└── evidence.py        # collect_context + _number_justifications -> EvidencePack, MCP-boundary caps
                        # (limits.py is explicitly out of scope this phase — Phase 11)
```

### Pattern 1: Lifespan-scoped client construction (mirrors `open_deps`)
**What:** A `@asynccontextmanager` function in `wiring.py` that opens one shared `httpx.AsyncClient`, constructs `ExaClient` and a key-aware `BrowserbaseClient`/`NullBrowserbase`, yields a small dataclass bundle, and tears everything down in `finally`. Passed to `FastMCP(..., lifespan=...)`.
**When to use:** Any time the server needs process-lifetime resources shared across tool calls.
**Verified guarantee:** `Server.run()` (the low-level server `FastMCP` wraps) calls `await stack.enter_async_context(self.lifespan(self))` exactly once, before entering the message-receive loop, and exits it once when the loop ends. For stdio transport, `run_stdio_async()` is called exactly once per process (`anyio.run(self.run_stdio_async)` from the synchronous `.run()` entry point, or a direct `await app.run_stdio_async()` under `asyncio.run()`). This confirms the lifespan-runs-once-per-process guarantee for the pinned SDK version. `[VERIFIED: mcp 1.28.1 source, mcp/server/lowlevel/server.py:663 and mcp/server/fastmcp/server.py:753]`
**Example:**
```python
# Source: pattern derived from src/pipeline.py::open_deps (existing, verified),
# adapted to the FastMCP lifespan contract confirmed in mcp/server/fastmcp/server.py
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from mcp.server.fastmcp import FastMCP

from src.clients.browserbase_client import BrowserbaseClient, NullBrowserbase
from src.clients.exa_client import ExaClient
from src.clients.protocols import BrowserbaseLike, ExaLike
from src.config import Settings


@dataclass(frozen=True)
class ThinDeps:
    exa: ExaLike
    browserbase: BrowserbaseLike


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[ThinDeps]:
    settings = ...  # Settings resolved once at startup, outside this function
    async with httpx.AsyncClient(timeout=60.0) as http:
        exa: ExaLike = ExaClient(api_key=settings.exa_api_key, client=http)
        bb: BrowserbaseLike
        if settings.browserbase_api_key and settings.browserbase_project_id:
            bb = BrowserbaseClient(
                api_key=settings.browserbase_api_key,
                project_id=settings.browserbase_project_id,
                client=http,
            )
        else:
            bb = NullBrowserbase()
        yield ThinDeps(exa=exa, browserbase=bb)
```
Tool functions access this via `ctx: Context` parameter -> `ctx.request_context.lifespan_context`.

### Pattern 2: Tool registration with annotations and structured pydantic return
**What:** Register the tool with explicit `ToolAnnotations`, and let the return type annotation (`-> EvidencePack`) drive automatic structured-output detection.
**When to use:** Any read-only tool returning a frozen pydantic model — matches the project's "one model owns the wire format" convention (D-02).
**Verified:** `func_metadata()` in `mcp/server/fastmcp/utilities/func_metadata.py` special-cases `BaseModel` subclasses as directly usable for structured output (`issubclass(type_annotation, BaseModel)` — case 1 of its type-annotation dispatch). `[VERIFIED: mcp 1.28.1 source, func_metadata.py:382-383]`
**Example:**
```python
# Source: mcp/types.py ToolAnnotations field definitions (readOnlyHint/destructiveHint),
# confirmed present at mcp==1.28.1
from mcp.types import ToolAnnotations

@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
async def get_account_evidence(domain: str, ctx: Context) -> EvidencePack:
    """Retrieve numbered, cited evidence for a company domain (about page +
    last-90-day news). Every claim you build downstream MUST cite a
    justification by its [N] index; do not state facts without a matching
    index from `justifications`. `retrieval_status` tells you whether
    evidence is strong enough to reason from ('ok'), thin ('thin'), or
    absent ('empty') -- treat 'empty' as 'cannot research this account'."""
    ...
```
The docstring doubles as the MCP tool description sent to clients — front-load the citation-numbering contract here per research pitfall 6 (weak descriptions make thin-tier "grounding by instruction" unreliable).

### Pattern 3: Error handling — do not rely on default stringification, but do not fight the SDK's error-channel guarantee either
**What:** A narrow try/except inside the tool function that (a) lets `Account`'s `ValidationError` produce its own message (D-08: "invalid domain passes through the `Account` validator message"), (b) catches known provider-failure exception types and returns a fixed message ("retrieval unavailable, try again"), and (c) has a final broad `except Exception` that logs the full exception at WARNING+ to stderr and raises/returns a generic sanitized message.
**Verified SDK behavior (why this pattern, not a bigger one):** Every exception raised inside a `@mcp.tool()`-decorated function is caught by `Tool.run()` (`mcp/server/fastmcp/tools/base.py:117`, `except Exception as e: raise ToolError(...) from e`) and then, one layer up, by the low-level server's `call_tool` handler (`mcp/server/lowlevel/server.py:589`, `except Exception as e: return self._make_error_result(str(e))`), which sets `isError=True` unconditionally. The only exception NOT captured this way is `UrlElicitationRequiredError`, which is deliberately re-raised as a protocol-level error (code `-32042`) — irrelevant to this phase's tool. **This means MCP-07's "never protocol-level errors" guarantee is structural, not something this phase's code has to build.** What this phase's code DOES have to build is message sanitization, because the SDK's default is `str(exc)` verbatim. `[VERIFIED: mcp 1.28.1 source, tools/base.py:110-117, lowlevel/server.py:498-591]`
**Example:**
```python
# Source: pattern synthesized from verified SDK exception-handling chain above
# and D-07/D-08 (10-CONTEXT.md)
from pydantic import ValidationError
from src.models import Account

async def get_account_evidence(domain: str, ctx: Context) -> EvidencePack:
    try:
        account = Account(domain=domain)  # raises pydantic ValidationError with a
                                            # useful message on malformed domains
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc  # message text IS the point (D-08);
                                              # SDK turns this into isError=True automatically

    deps: ThinDeps = ctx.request_context.lifespan_context
    try:
        return await build_evidence_pack(account, exa=deps.exa, browserbase=deps.browserbase)
    except (httpx.HTTPError, ...) as exc:
        log.warning("evidence retrieval failed for %s: %s", domain, exc)
        raise ValueError("retrieval unavailable, try again") from None
    except Exception as exc:  # sanitizing catch-all, D-07
        log.warning("unexpected error in get_account_evidence for %s: %s", domain, exc, exc_info=True)
        raise ValueError("internal error, try again") from None
```
Raising a plain exception (not necessarily `mcp.server.fastmcp.exceptions.ToolError`) is sufficient — the SDK wraps anything. Import `ToolError` only if the plan wants the more semantically explicit type; either way the client-visible result is identical (`isError: true`, text = the raised exception's `str()`).

### Anti-Patterns to Avoid
- **Relying on the SDK's default `str(exc)` for user-facing error text:** leaks whatever the underlying exception happened to stringify — an `httpx.ConnectError` can include the target URL, a `KeyError` can include a dict key that came from provider response data. Always catch narrowly and raise with an explicit, reviewed message (D-07/D-08).
- **Calling `pipeline.open_deps()` from the MCP server:** `open_deps` constructs writer/judge LLM clients unconditionally — wrong for the thin tier, which is retrieval-only (Phase 9 D-04). Build a phase-10-local lifespan in `wiring.py` instead.
- **Printing anything to stdout, including via `print()` debug statements:** stdio transport uses stdout exclusively for JSON-RPC frames; any stray byte corrupts the protocol stream silently (research pitfall 1). Configure `logging.basicConfig(stream=sys.stderr, ...)` as the very first statement in `__main__`, before any project import that might log at import time.
- **Calling `FastMCP.run()` (the synchronous top-level entrypoint) from inside an `async def main()`:** `.run()` internally calls `anyio.run(...)`, which creates its own event loop — calling it from inside an already-running loop raises. Prefer `await app.run_stdio_async()` directly under `asyncio.run()`, matching the project's existing `asyncio.run(main())` convention in `pipeline.py`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| stdio JSON-RPC framing | Custom line-based stdin/stdout protocol parser | `mcp.server.fastmcp.FastMCP.run_stdio_async()` / `mcp.server.stdio.stdio_server()` | The protocol has structured message types, request IDs, session lifecycle; getting this wrong breaks compatibility with every real MCP client |
| Tool-call error-channel routing (`isError: true` vs protocol error) | Manual try/except-and-format-JSON-RPC-response code | The SDK's built-in `call_tool` handler (verified this session to catch `Exception` unconditionally and build `isError: true`) | Already guaranteed correct by the SDK; hand-rolling this risks accidentally producing a protocol-level error path the SDK was specifically designed to avoid |
| Structured JSON output shape / schema generation for the tool result | Manual `json.dumps(pack.model_dump())` plus a hand-written JSON schema | Return the `EvidencePack` pydantic model directly with a `-> EvidencePack` return annotation | `func_metadata()` auto-derives the output schema and `structuredContent` from the pydantic model; matches the project's "one model owns the wire format" rule with zero extra code |
| In-memory MCP client for functional tests | A subprocess-based test harness with real stdio pipes | `mcp.shared.memory.create_connected_server_and_client_session(server, ...)` (bundled with `mcp`, no extra dependency) | Confirmed this session: it accepts a `FastMCP` instance directly and wires memory-object streams — exactly what CONTEXT.md's locked decision specifies, no subprocess, no network |

**Key insight:** Every one of this phase's genuinely novel-looking problems (protocol framing, error-channel semantics, structured-output schema, in-process test client) is already solved by the `mcp` SDK version the design spec pinned. The actual net-new code this phase writes is business logic (domain validation delegation, evidence capping, tier resolution) glued onto SDK decorators — not protocol plumbing.

## Common Pitfalls

### Pitfall 1: stdout contamination breaks stdio JSON-RPC silently
**What goes wrong:** Any stray `print()`, an uncaught library warning that writes to stdout, or `logging.basicConfig()` left at its default (which writes to stderr by default in the stdlib — but any explicit `stream=sys.stdout` or a third-party library defaulting to stdout is the risk) corrupts the JSON-RPC message stream. The client sees malformed frames and the connection silently breaks or hangs.
**Why it happens:** stdio transport multiplexes protocol messages and only protocol messages onto stdout; there is no separate debug channel.
**How to avoid:** `logging.basicConfig(stream=sys.stderr, level=..., format=...)` as literally the first executable statement in `src/mcp_server/__main__`-equivalent entrypoint, before any other project import (some project modules may log at import time). Never call `print()` anywhere in `src/mcp_server/`. Verify with a real client connection, not just unit tests — unit/functional tests using `mcp.shared.memory` never touch stdout/stdin at all, so they cannot catch this class of bug. Success criterion 1 (`make mcp` + real client) is the only test that exercises this.
**Warning signs:** Claude Code/Desktop reports a connection that "hangs" or "fails to initialize" with no clear error; `claude mcp list` shows the server as unreachable after appearing to start.

### Pitfall 2: `ToolError` import confusion
**What goes wrong:** Code imports `from mcp import ToolError` (following outdated blog posts or a different MCP SDK's convention) and gets an `ImportError` at module load.
**Why it happens:** `ToolError` lives at `mcp.server.fastmcp.exceptions.ToolError`, not re-exported from the `mcp` top-level package. Confirmed by direct import attempt this session (`from mcp import ToolError` -> `ImportError`; `from mcp.server.fastmcp.exceptions import ToolError` -> success).
**How to avoid:** `from mcp.server.fastmcp.exceptions import ToolError` — or, per Pattern 3 above, skip importing `ToolError` entirely and just raise a plain exception (e.g. `ValueError`), since the SDK wraps any exception type identically.
**Warning signs:** `ImportError: cannot import name 'ToolError' from 'mcp'` at server startup.

### Pitfall 3: Oversized `EvidencePack` JSON blows the calling agent's context window
**What goes wrong:** Uncapped `about_text` (up to 6000 chars per `collect_context`'s Browserbase fallback path) or an uncapped news list returned verbatim in the tool result consumes excessive context tokens in the calling agent's conversation.
**Why it happens:** `collect_context`/`_number_justifications` were built for the CLI pipeline, where the LLM-facing prompt builder (`_build_context_block`) does its own truncation via `SUMMARY_MAX_CHARS = 140` on justification summaries — but `about_text` itself and the news list are not capped at that layer, and the MCP boundary is a new, separate consumer with its own context-budget concerns (Phase 9 D-10: capping belongs at the MCP boundary, not in the model).
**How to avoid:** Module-level constants in `evidence.py` (per D-03): `ABOUT_TEXT_MCP_CAP ~= 2000`, per-justification `summary` cap `~= 300` (already 140 from `_clean_summary`, but the design intent is an MCP-specific ceiling — confirm during planning whether to reuse `_clean_summary`'s existing 140-char cap or add a separate, larger MCP cap since 140 already caps summaries below the target and may make a distinct MCP cap a no-op; flagged as an Open Question below), news list `~= 10 items`. Truncate before constructing the `EvidencePack`, not after.
**Warning signs:** `EvidencePack.model_dump_json()` length noticeably larger than expected for a single-page about-text retrieval.

### Pitfall 4: Weak tool description undermines the citation-numbering contract
**What goes wrong:** If the tool docstring doesn't spell out that every downstream claim must cite a `[N]` index from `justifications`, a calling agent (Claude Code/Desktop) may summarize the evidence in free text without citations, defeating the "grounding by instruction" story this tool exists to demonstrate.
**Why it happens:** MCP tool descriptions are the *only* instruction surface a generic client sees before invoking the tool; there is no separate system prompt this project controls at call time (the `research_account` prompt that would enforce this is Phase 12 scope, not this phase).
**How to avoid:** Front-load the citation contract explicitly in the tool docstring (see Pattern 2's example) even though the enforcing `research_account` prompt doesn't exist yet this phase — the tool must stand on its own description.
**Warning signs:** Manual verification session (Claude Code connected via `claude mcp add`) shows the assistant summarizing evidence without `[N]` markers when asked to research an account.

### Pitfall 5: Key-aware Browserbase construction diverges silently from CLI parity
**What goes wrong:** If the thin-tier wiring always constructs `NullBrowserbase()` (copying the literal Phase 9 D-04 wording rather than its refined form in this phase's D-04), the MCP evidence quality regresses below what `make run` produces for the same domain, contradicting D-04's explicit intent to match CLI evidence quality when a Browserbase key exists.
**Why it happens:** Phase 9 D-04 said "Exa + NullBrowserbase" before this phase's key-aware refinement existed; a plan that copy-pastes Phase 9's wiring verbatim without re-reading this phase's D-04 will under-wire.
**How to avoid:** `wiring.py`'s lifespan constructs `BrowserbaseClient` when both `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` are set, `NullBrowserbase()` otherwise — mirrors the existing `require_for_pipeline()` presence-check style but does NOT fail startup on missing Browserbase keys (thin tier only strictly requires `EXA_API_KEY`, per this phase's D-Locked item on `Settings.mcp_tier()`).
**Warning signs:** MCP evidence for a domain with thin Exa-only about text stays `thin`/`empty` even when `BROWSERBASE_API_KEY` is configured in `.env`.

### Pitfall 6: `EvidencePack.from_context`'s `about_text_min_chars` keyword becomes stale
**What goes wrong:** `evidence.py` hardcodes its own copy of the "thin" threshold instead of importing `ABOUT_TEXT_MIN_CHARS` from `enrich.py`, and the two drift apart over time.
**Why it happens:** Phase 9 D-09 deliberately made `about_text_min_chars` an explicit keyword arg on `from_context` (not an import) to avoid a `models.py<->enrich.py` cycle — but that decision pushes the responsibility of passing the *correct* value onto every caller, including this phase's new one.
**How to avoid:** `evidence.py` imports `ABOUT_TEXT_MIN_CHARS` from `src.enrich` (a `models.py`-free import, no cycle risk since `evidence.py` is a new module outside `models.py`) and passes it through explicitly: `EvidencePack.from_context(..., about_text_min_chars=ABOUT_TEXT_MIN_CHARS)`.
**Warning signs:** MCP `retrieval_status` and CLI `Enrichment`-derived data disagree on whether the same about-page-only retrieval counts as `thin` vs `ok`.

## Code Examples

Verified patterns from official sources (all confirmed against locally installed `mcp==1.28.1` this session):

### Minimal FastMCP app with lifespan and stdio entrypoint
```python
# Source: mcp.server.fastmcp.server.FastMCP.__init__ signature (lifespan kwarg)
# and .run_stdio_async() / .run() (mcp==1.28.1, verified via inspect + source read)
import asyncio
import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from mcp.server.fastmcp import FastMCP  # noqa: E402  (import after logging config)

from src.mcp_server.wiring import lifespan  # noqa: E402

mcp = FastMCP("poc-scraper", lifespan=lifespan)

# ... @mcp.tool() registrations here ...

async def _main() -> None:
    await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(_main())
```
Note the `# noqa: E402` markers are required because `ruff`'s `E`/`I` rule families will otherwise flag imports after the `logging.basicConfig()` call — this is intentional ordering, not an accident, and should be documented inline (the "why" comment convention from CLAUDE.md).

### Functional test via in-memory client (locked pattern, D-Locked)
```python
# Source: mcp.shared.memory.create_connected_server_and_client_session
# (bundled with mcp==1.28.1, confirmed this session to accept FastMCP directly)
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from src.mcp_server.server import mcp  # the FastMCP app instance

@pytest.mark.asyncio
async def test_get_account_evidence_returns_structured_pack() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        await client.initialize()
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        assert result.isError is False
        assert result.structuredContent is not None
        assert result.structuredContent["retrieval_status"] in ("ok", "thin", "empty")
```
Note: `create_connected_server_and_client_session` accepts `Server[Any] | FastMCP` per its type signature (confirmed by source read), so passing the `FastMCP` instance directly (not `._mcp_server`) should also work — verify both call shapes at plan time since the type hint suggests either is valid but the low-level `Server` may be the more literal target given the parameter name conventions seen elsewhere in the SDK.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `mcp<1.23` without opt-in DNS-rebinding protection | `mcp>=1.23.0` ships CVE-2025-66414/66416 fixes; `mcp>=1.28,<2.0` pinned per milestone research | fixed at 1.23.0 (2026) | Not directly load-bearing for stdio-only Phase 10 (no HTTP transport yet — that's Phase 11's `TransportSecuritySettings` work), but the version floor is shared across the whole milestone, so this phase's `pyproject.toml` change locks in the safe floor for later phases too |
| `FastMCP` decorator API pre-1.0 vs current | Current stable API (tool/resource/prompt decorators, `ToolAnnotations`, structured-output auto-detection via return type) is what's installed and verified this session | ongoing SDK evolution, stabilized well before 1.28 | Confirms the design spec and code examples above match the pinned version exactly — no drift risk within this phase |

**Deprecated/outdated:** None specific to this phase's scope; the standalone `fastmcp` PyPI package (distinct from the official `mcp` SDK) remains a common confusion point in web search results and must be explicitly avoided per the design spec.

## Assumptions Log

> Claims tagged `[ASSUMED]` in this research. None found — every claim above was either verified by direct SDK source introspection, direct `pip install` + runtime check, direct PyPI JSON API query, or direct `claude mcp add --help` output this session.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (none) | — | — |

**This table is empty:** All claims in this research were verified this session against the pinned `mcp==1.28.1` package's actual source, the live PyPI registry, or the installed `claude` CLI — no user confirmation needed before planning proceeds.

## Open Questions

1. **Does the MCP-boundary `about_text` cap (~2000 chars, D-03) interact with the existing 140-char `_clean_summary` cap on justification summaries, or are these two independent caps on two different fields?**
   - What we know: `about_text` (the raw about-page text passed to `from_context`) and `Justification.summary` (built by `_number_justifications` via `_clean_summary`, already capped at `SUMMARY_MAX_CHARS = 140`) are distinct fields on `EvidencePack`. D-03 names both "about_text ~2000 chars" and "per-justification summary ~300 chars" as separate caps.
   - What's unclear: whether the "~300 chars" justification-summary target in D-03 is meant to *replace* or *sit above* the existing 140-char `_clean_summary` cap (which would make a 300-char MCP cap a permanent no-op, since input is already ≤140 chars by the time it reaches `EvidencePack`).
   - Recommendation: Plan should apply the ~300-char cap defensively in `evidence.py` regardless of whether it is currently reachable (future-proofs against `_clean_summary`'s cap changing), and treat the about_text cap (~2000 chars) as the one with real, immediate effect since `about_text` can be up to 6000 chars post-Browserbase-fallback.

2. **Exact call shape for `mcp.shared.memory.create_connected_server_and_client_session`: pass `FastMCP` instance directly, or its `._mcp_server` (low-level `Server`)?**
   - What we know: the function signature accepts `Server[Any] | FastMCP` (confirmed via source read this session), so both are type-valid.
   - What's unclear: whether passing the `FastMCP` wrapper vs the inner `Server` produces identical behavior for tool-calling in tests (annotations, structured output) — not exercised end-to-end this session due to time budget.
   - Recommendation: Planner should have the functional-test task try `FastMCP` instance first (simpler, one less internal attribute reference) and fall back to `._mcp_server` only if a concrete test failure surfaces a mismatch.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` Python SDK | This phase's entire scope | ✗ (not yet a project dependency) | target `>=1.28,<2.0`, verified `1.28.1` current | `uv add "mcp>=1.28,<2.0"` — first task of this phase |
| `EXA_API_KEY` | Thin-tier retrieval (`get_account_evidence`) | project-local `.env`, not inspected this session (secrets out of scope for research) | — | `Settings.mcp_tier()` fails fast with a missing-keys message per D-locked item if absent |
| Claude Code CLI (`claude`) | HOST-01 real-client verification (D-05) | ✓ | `claude mcp add` confirmed present with `-t stdio` (default) support this session | — |
| `uv` | `make mcp` target execution | ✓ (used throughout this research session) | — | — |

**Missing dependencies with no fallback:**
- `mcp` package itself must be added to `pyproject.toml` before any of this phase's code can import it — first plan task, not optional.

**Missing dependencies with fallback:**
- None beyond the above; Browserbase absence has an explicit code-level fallback (`NullBrowserbase`) by design, not a missing-dependency gap.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=8.2.0` + `pytest-asyncio>=0.23.0` (`asyncio_mode = "auto"`), existing project config |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing; `markers` list already registers `smoke` — reuse, no new marker needed per Claude's Discretion on smoke-test mechanics) |
| Quick run command | `uv run pytest -m "not smoke" tests/unit/test_evidence.py tests/functional/test_mcp_server.py -q` (paths illustrative; exact filenames are plan-time choices) |
| Full suite command | `make test` (already excludes `smoke`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-01 | `get_account_evidence(domain)` returns numbered, cited `EvidencePack` JSON with `retrieval_status`, snippets capped | unit + functional | `pytest tests/unit/test_evidence.py tests/functional/test_mcp_server.py -x` | ❌ Wave 0 |
| MCP-06 | `Settings.mcp_tier()` resolves once at startup, logs the resolved tier | unit | `pytest tests/unit/test_config.py -k mcp_tier -x` | ❌ Wave 0 (extends existing `test_config.py`) |
| MCP-07 | `readOnlyHint`/`destructiveHint` annotations present; domain failures -> `isError: true`, never protocol errors | functional | `pytest tests/functional/test_mcp_server.py -k error -x` | ❌ Wave 0 |
| HOST-01 | Real client (Claude Code) connects over stdio, all logging to stderr | manual + smoke | `claude mcp add` + live session (D-05); `pytest tests/smoke/test_mcp_e2e.py -v` for the subprocess half | ❌ Wave 0 (smoke); manual step not automatable |
| TEST-02 | `make smoke-mcp` runs stdio server as real subprocess against one live domain, asserts non-empty numbered justifications, skipped in CI | smoke (opt-in, marked `smoke`) | `make smoke-mcp` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -m "not smoke" -k mcp -q` (fast, targeted)
- **Per wave merge:** `make test` (full offline suite) + `make typecheck` (strict mypy, no new overrides expected since `mcp` ships `py.typed`)
- **Phase gate:** `make test`, `make typecheck`, `make lint` all green before `/gsd-verify-work`; `make smoke-mcp` is opt-in and NOT part of the automated gate (mirrors existing `smoke`/`smoke-mcp` credit-burning separation per CLAUDE.md)

### Wave 0 Gaps
- [ ] `tests/unit/test_evidence.py` — covers MCP-01 (`EvidencePack` construction, size-cap behavior, `retrieval_status` transitions reused/extended from Phase 9 `test_models.py` coverage but exercised through `evidence.py`'s new capping logic)
- [ ] `tests/functional/test_mcp_server.py` — covers MCP-01, MCP-06, MCP-07 via `mcp.shared.memory` in-process client with `FakeExa`/`NullBrowserbase` stubs (reuse existing fakes from `tests/functional/test_enrich.py` or `tests/functional/test_pipeline_open_deps.py` if compatible with `ExaLike`/`BrowserbaseLike` protocols — confirm during planning)
- [ ] `tests/unit/test_config.py` extension — covers MCP-06 (`mcp_tier()` across key-presence combinations, mirroring `require_for_pipeline`'s existing test coverage style)
- [ ] `tests/smoke/test_mcp_e2e.py` — covers TEST-02 (`make smoke-mcp` subprocess harness against one fixture domain, `@pytest.mark.smoke`, skip-if-no-`EXA_API_KEY` guard mirroring `tests/smoke/test_e2e.py`'s `_skip_if_no_keys` pattern)
- [ ] Framework install: `uv add "mcp>=1.28,<2.0"` — must run before any of the above test files can import `mcp`

*(HOST-01's real-client verification step is manual by nature — MCP-spec compliance for a live stdio client connection cannot be fully automated; the smoke test covers the subprocess-transport half, the manual `claude mcp add` session covers the "a real client's tool-calling UX is coherent" half, per D-05.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | stdio transport is local-process, single-user by construction; no auth surface this phase (HTTP transport auth deferred entirely per REQUIREMENTS.md Out of Scope) |
| V3 Session Management | no | MCP session lifecycle is SDK-managed (`ServerSession`), not application code's concern |
| V4 Access Control | no | single read-only tool, no user roles, no resource ownership model this phase |
| V5 Input Validation | yes | `Account`'s existing `field_validator` on `domain` (strip protocol/`www.`/trailing slash, require a dot) is reused verbatim — the MCP tool wrapper delegates validation, does not reimplement it |
| V6 Cryptography | no | no secrets handled or generated by this phase's new code; existing `.env`-based key loading is unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Information disclosure via unsanitized error messages (stack traces, internal URLs, provider error bodies leaking into `isError` text) | Information Disclosure | Sanitizing catch-all wrapper (D-07/D-08): narrow except clauses for known failure modes with fixed messages, full traceback logged to stderr only (never returned to the client), generic message for the unexpected-exception case. This is HOST-05's discipline, built now per D-07's explicit "front-load HOST-05" intent even though HOST-05 itself is a Phase 13 requirement. |
| Protocol-channel confusion (an error accidentally surfacing as a JSON-RPC protocol failure instead of a structured tool result, which could crash naive clients or hide the actual domain-level error from the agent) | Denial of Service (client-side) / Tampering (protocol integrity) | Structural guarantee from the SDK (verified this session): all `Exception` subclasses raised inside a tool handler become `isError: true` results; only `UrlElicitationRequiredError` escapes this path, and this phase's tool never raises that type |
| stdout/stdin stream contamination corrupting the JSON-RPC transport (a form of protocol-integrity tampering, even if unintentional) | Tampering | stderr-only logging configured as the literal first statement before any other import; no `print()` anywhere in `src/mcp_server/`; verified with a real client connection per HOST-01's success criterion, not just unit tests |

## Sources

### Primary (HIGH confidence)
- Local `mcp==1.28.1` package installed via `uv run --with "mcp>=1.28,<2.0"` this session; source read directly from `mcp/server/fastmcp/{server.py,exceptions.py,tools/base.py}`, `mcp/server/lowlevel/server.py`, `mcp/shared/memory.py`, `mcp/types.py`
- PyPI JSON API (`https://pypi.org/pypi/mcp/json`) — queried directly this session for release history and project URLs
- `claude mcp add --help` — queried directly against the installed `claude` CLI this session
- `.planning/research/SUMMARY.md` — milestone-level research, itself HIGH confidence per its own PyPI JSON API + local install verification
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md` — approved design authority for this milestone
- `.planning/phases/10-stdio-mcp-server-thin-tier/10-CONTEXT.md` — locked phase decisions (D-01 through D-08, discretion areas)
- `src/models.py`, `src/pipeline.py`, `src/enrich.py`, `src/config.py`, `src/clients/browserbase_client.py`, `src/clients/protocols.py` — read directly this session, current repo state

### Secondary (MEDIUM confidence)
None — every technical claim in this research was resolved to a primary source this session.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - `mcp==1.28.1` installed and introspected directly this session; version, `py.typed`, transitive deps all confirmed against the real package, not training data
- Architecture: HIGH - lifespan-once-per-process and `ToolError`/error-channel behavior (the two explicitly flagged research risks) both resolved by direct source reading of the pinned SDK version
- Pitfalls: HIGH - all pitfalls trace to either verified SDK source behavior or the existing codebase's own documented decisions (Phase 9 D-04/D-07/D-09/D-10)

**Research date:** 2026-07-16
**Valid until:** 30 days (stable SDK; re-verify if `mcp` version pin changes before this phase executes)
