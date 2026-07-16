# Phase 11: Rate Limits & Streamable HTTP Transport - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

The same `get_account_evidence` surface served over streamable HTTP from the same entry point (`python -m src.mcp_server --transport http`, `make mcp-http`), plus demo-mode rationing in `src/mcp_server/limits.py`: 5 evidence calls per IP per hour, 25 per UTC day globally (both env-tunable), the Exa results clamp (5), structured rationing errors with reset times, client-IP resolution from `Fly-Client-IP` with rightmost-XFF fallback failing closed into one shared bucket, race-safe counters, and an injected clock for tests. Requirements: HOST-02, HOST-04.

Out of this phase: full-tier tool / resources / prompt (Phase 12); Fly.io deploy, Dockerfile, `fly.toml`, and the production-hostname half of HOST-06 (Phase 13). Note HOST-06's *local* discipline is front-loaded here per D-08.

</domain>

<decisions>
## Implementation Decisions

### Limit activation scope
- **D-01:** `MCP_DEMO_MODE=1` enables `limits.py` on ANY transport. Stdio in demo mode has no client IP and falls into the fail-closed shared bucket HOST-04 already requires. One mental model; demo behavior is locally testable over stdio.
- **D-02:** `make mcp-http` WITHOUT demo mode is unlimited. Limits are a demo-mode concern only; a local BYOK user self-rations. The hosted deploy always sets the flag (Phase 13 guarantees it), so the public URL stays protected.
- **D-03:** The Exa results clamp (5, env-tunable) follows the same gate: demo mode only, any transport (per the design spec's "demo scope clamps").

### Counting semantics
- **D-04:** A quota unit is consumed only by calls that reach retrieval: check-and-consume happens after `Account` validation passes, immediately before `collect_context`. Invalid domains and rate-limit refusals cost nothing (they burn no Exa credit). A retrieval that fails mid-flight still counts because Exa was hit. Per-IP and global counters are consumed together at that single point; a call refused by either limit consumes neither.
- **D-05:** The per-IP hourly limit uses a rolling 60-minute window: keep the last-5 call timestamps per IP; allow when fewer than 5 fall in the trailing hour; reset time = oldest timestamp + 1h. No burst-at-boundary loophole; bounded state (max `ip_limit` timestamps per IP). The global cap stays a fixed UTC day per HOST-04's wording ("25 per UTC day").

### Rationing error UX
- **D-06:** Distinct refusal messages per limit, both as `isError: true` tool results in Phase 10's plain-message style (no machine codes): per-IP roughly "rate limit reached, resets at HH:MM UTC"; global roughly "demo budget spent for today, resets at 00:00 UTC". Exact strings are Claude's discretion; each MUST carry its reset time.
- **D-07:** No quota disclosure on successful calls. `EvidencePack` stays the pure evidence wire format Phase 10 locked (D-02 there: one model, `model_dump()` single serialization path); rationing info appears only in refusals. In demo mode, Exa credit exhaustion (402/429 surviving tenacity retries) borrows the global daily-cap wording so the public URL looks rationed, never broken; non-demo mode keeps Phase 10's "retrieval unavailable, try again".

### HTTP hardening front-load
- **D-08:** Front-load HOST-06's transport-security half now: configure `TransportSecuritySettings` explicitly with a localhost allowlist (covering `127.0.0.1:<port>` / `localhost:<port>`). Phase 13 only swaps in the Fly hostname and verifies. Mirrors the Phase 10 precedent of front-loading HOST-05 (sanitized errors) so protection is never "off between phases".
- **D-09:** Local HTTP defaults: bind `127.0.0.1`, port `8000` (the spec's `mcp_http_port`), both env-overridable. Phase 13's Dockerfile explicitly overrides the host to `0.0.0.0`; exposure is a deliberate deploy-time act, never a local default.
- **D-10:** `make mcp-demo` (HTTP + `MCP_DEMO_MODE=1`, what the Dockerfile will run) lands THIS phase alongside `make mcp-http`, so the rationed server can be exercised locally (e.g. the 6th-call refusal by hand) and Phase 13 invokes an already-tested target.

### Locked by prior phases / requirements (do not re-litigate)
- `limits.py` lives in `src/mcp_server/` (package layout locked in Phase 10); entry point stays `python -m src.mcp_server`, stdio default, `--transport http` added now.
- Demo mode forces thin tier and `NullBrowserbase` unconditionally (Phases 9/10; `Settings.mcp_tier()` already implements the thin force).
- Rationing errors are `isError: true` tool results (raise through the existing sanitizing wrapper), never protocol errors (MCP-07, Phase 10 D-07/D-08).
- Env-tunable caps (`MCP_DEMO_IP_LIMIT`, `MCP_DEMO_DAILY_CAP`, `MCP_DEMO_EXA_RESULTS` naming per the design spec) are a requirement-locked exception to Phase 10 D-03's "no new env knobs" principle — HOST-04 explicitly demands env-tunable.
- In-memory counters only; no Redis or external store (design spec + research both explicitly exclude it). Single-machine globality is Phase 13's `fly.toml` concern.
- Client IP: prefer `Fly-Client-IP`; XFF fallback takes the RIGHTMOST entry; missing or malformed headers fail closed into one shared bucket (HOST-04 verbatim; research pitfall 4).
- Injected clock for all limit tests (roadmap criterion 3; TEST-01); counters protected against read-modify-write races under concurrent requests (roadmap criterion 4).
- Stack pin `mcp>=1.28,<2.0`; strict mypy, no new overrides.

### Claude's Discretion
- Exact refusal-message strings (within D-06's constraints) and the reset-time formatting details.
- Concurrency-protection mechanism for the counters (e.g. `asyncio.Lock` vs relying on no-await critical sections) — criterion 4 demands protection; the mechanism is the planner/executor's call.
- Per-IP bucket pruning of stale entries (memory hygiene for a demo server), internal `limits.py` API shape, and how the injected clock is threaded (callable vs protocol).
- How the client-IP middleware mounts given the SDK finding below (wrap the returned Starlette app via `add_middleware`, a pure-ASGI wrapper, or equivalent) and how the IP reaches the tool (e.g. `contextvars.ContextVar` per research).
- Startup log wording for demo-mode/limit state (extending the Phase 10 tier log).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design authority
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md` — Approved MCP server design. §"Hosted demo safety rails (MCP_DEMO_MODE=1)" defines the caps, cost basis, env names, and rationing-error behavior; §"Transports" defines `--transport http --port <n>` from the same registered app; §"Config and wiring changes" lists the `Settings` fields (`mcp_demo_ip_limit`, `mcp_demo_daily_cap`, `mcp_demo_exa_results`, `mcp_http_port`) and Makefile targets (`mcp-http`, `mcp-demo`). NOTE: its naive "Client IP from X-Forwarded-For" wording is superseded by HOST-04's Fly-Client-IP/rightmost-XFF/fail-closed rule.
- `.planning/research/SUMMARY.md` — Milestone research. Phase-5 section (= this phase) is the named highest-uncertainty step; pitfalls 2 (multi-machine counters), 3 (DNS rebinding / `TransportSecuritySettings`), 4 (XFF spoofing) land here; prescribes a custom ASGI middleware + `contextvars.ContextVar` for client IP.

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — HOST-02, HOST-04 are this phase's requirements; HOST-04 carries the Exa clamp and the fail-closed IP rule verbatim.
- `.planning/ROADMAP.md` — Phase 11 goal and 4 success criteria; research flag on the `streamable_http_app(middleware=...)` kwarg shape (resolved: see SDK finding below).

### Prior phase decisions
- `.planning/phases/10-stdio-mcp-server-thin-tier/10-CONTEXT.md` — D-03 (caps as constants; demo clamps deferred here), D-07/D-08 (sanitized `isError` results, plain messages), locked package layout and entry-point shape.
- `.planning/phases/09-pipeline-extraction-supporting-models/09-CONTEXT.md` — D-04 (thin tier wires itself), D-07 (`NullBrowserbase` returns `None`).

### Code seams consumed
- `src/mcp_server/server.py` — `build_server()` + `get_account_evidence` wrapper where the limit check-and-consume slots in (after `Account` validation, before `build_evidence_pack`); the sanitizing except-chain the rationing errors join.
- `src/mcp_server/__main__.py` — stderr-first logging then `run_stdio_async()`; gains the `--transport http` dispatch.
- `src/mcp_server/wiring.py` — `make_thin_lifespan(settings)` / `ThinDeps`; demo mode must force `NullBrowserbase` and thread the Exa results clamp here.
- `src/mcp_server/evidence.py` — `build_evidence_pack`; existing MCP-boundary caps live here.
- `src/config.py` — `mcp_demo_mode` + `mcp_tier()` exist; this phase adds `mcp_demo_ip_limit`, `mcp_demo_daily_cap`, `mcp_demo_exa_results`, `mcp_http_port` (defaulted, per the spec).
- `src/clients/exa_client.py` — where the results-count clamp must be injectable.

### SDK finding (resolves the roadmap research flag)
- `.venv/.../mcp/server/fastmcp/server.py` (mcp==1.28.1): `streamable_http_app(self)` takes NO `middleware=` kwarg — it builds only auth middleware internally and returns a `Starlette` app. The client-IP middleware must mount another way (e.g. `app.add_middleware(...)` on the returned app or a pure-ASGI wrapper). `TransportSecuritySettings` (with `enable_dns_rebinding_protection: bool = True` and `allowed_hosts`) lives at `mcp/server/transport_security.py`. Planner should confirm how `FastMCP` accepts transport-security settings and how host/port are configured (`FastMCP` settings vs uvicorn args) against the installed source.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_account_evidence` (`src/mcp_server/server.py`): the single tool both transports serve; the limit gate is a small insertion between its validation and retrieval steps — no new tool surface.
- Sanitizing except-chain in the same function: rationing refusals reuse the raise-`ValueError`-for-`isError` pattern instead of inventing a new error path.
- `make_thin_lifespan` (`src/mcp_server/wiring.py`): demo-mode wiring (forced `NullBrowserbase`, clamped Exa results) is a variation of this factory, not a parallel one.
- `Settings` + `mcp_tier()` (`src/config.py`): the new demo fields follow the existing defaulted-field + `SettingsConfigDict(env_file=".env")` pattern; env names per the spec.
- Injected-clock precedent: tests already monkeypatch time-adjacent seams (Phase 5 intercepted `asyncio.sleep` for tenacity); `limits.py` should take the clock as a constructor arg instead, per the design spec's "injectable clock".
- In-memory functional-test harness (`mcp.shared.memory`, `FakeExa`, `NullBrowserbase`): extends to limit-behavior tests without network; HTTP-transport tests need a real (local) ASGI exercise for the header path.

### Established Patterns
- Frozen models / `extra="forbid"`; `EvidencePack` wire format unchanged this phase (D-07).
- Logging: stderr-only, `%` placeholders, WARNING for recoverable failures, truncate untrusted strings — header values are untrusted input and must be truncated if logged.
- Module constants SCREAMING_SNAKE for non-tunable internals; env-tunable knobs go through `Settings` (D-03 exception is requirement-locked).
- Strict mypy, fully annotated; 5-layer test strategy with smoke opt-in.

### Integration Points
- `src/mcp_server/__main__.py` gains argument parsing (`--transport`, port/host from settings) dispatching `run_stdio_async()` vs the streamable-HTTP app under uvicorn.
- `Makefile` gains `mcp-http` and `mcp-demo` targets.
- `pyproject.toml` unchanged (uvicorn/starlette are `mcp` transitives; research says do not pin them explicitly).
- Dependency arrow stays one-directional: `src/mcp_server/` imports from `src/`, never the reverse.

</code_context>

<specifics>
## Specific Ideas

- The user again consistently chose the recommended, spec-faithful option on all 10 questions — convention preservation over novelty, and front-loading safety discipline (D-08) exactly as Phase 10 did with HOST-05.
- The cost model is the design intent behind counting: caps exist to protect the ~$14 Exa credit pool, so quota consumption tracks Exa spend (D-04), not request volume.
- "Rationed, never broken" is the public-URL story: credit exhaustion masquerades as the daily cap (D-07) by design.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Fly deploy, `fly.toml` single-machine pin, production `TransportSecuritySettings` hostname, and README/CLAUDE.md docs were kept in Phase 13; resources/prompt and the full-tier tool stay in Phase 12.)

</deferred>

---

*Phase: 11-Rate Limits & Streamable HTTP Transport*
*Context gathered: 2026-07-16*
