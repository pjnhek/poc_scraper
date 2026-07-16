# Phase 11: Rate Limits & Streamable HTTP Transport - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 11-Rate Limits & Streamable HTTP Transport
**Areas discussed:** Limit activation scope, Counting semantics, Rationing error UX, HTTP hardening front-load

---

## Limit activation scope

### Q1: What turns the rate limiter on?

| Option | Description | Selected |
|--------|-------------|----------|
| Demo flag, any transport (Recommended) | MCP_DEMO_MODE=1 enables limits wherever the server runs; stdio+demo falls into the fail-closed shared bucket; one mental model, locally testable | ✓ |
| Demo + HTTP only | Limits exist only on the HTTP transport; demo semantics differ by transport | |
| You decide | Claude picks at planning time | |

**User's choice:** Demo flag, any transport

### Q2: `make mcp-http` without demo mode: limited or unlimited?

| Option | Description | Selected |
|--------|-------------|----------|
| Unlimited (Recommended) | Limits are a demo-mode concern only; local BYOK user self-rations; hosted deploy always sets the flag | ✓ |
| Always limited over HTTP | Defense in depth against a Phase 13 misconfiguration, but punishes legitimate local use | |
| You decide | Claude picks at planning time | |

**User's choice:** Unlimited

---

## Counting semantics

### Q1: What consumes a quota unit?

| Option | Description | Selected |
|--------|-------------|----------|
| Only calls reaching retrieval (Recommended) | Consume after Account validation, before collect_context; invalid domains and refusals cost nothing; mid-flight retrieval failures still count | ✓ |
| Every tool call counts | Increment on entry; simpler but typos burn quota with no Exa spend | |
| Count + refund on failure | Most precise but adds a refund path to the race-safety story | |

**User's choice:** Only calls reaching retrieval

### Q2: Window shape for the per-IP hourly limit?

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling 60-min window (Recommended) | Last-5 timestamps per IP; reset = oldest + 1h; no burst-at-boundary loophole | ✓ |
| Fixed clock-hour bucket | Simplest math, matches daily-cap style, but allows 10-call boundary burst | |
| You decide | Claude picks, keeping injected-clock tests simple | |

**User's choice:** Rolling 60-min window (global cap stays fixed UTC day per HOST-04 wording)

---

## Rationing error UX

### Q1: Should the refusal message say which limit was hit?

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct messages per limit (Recommended) | Per-IP: "rate limit reached, resets at HH:MM UTC"; global: "demo budget spent for today"; actionable for the caller's agent | ✓ |
| One generic rationing message | Reveals less but gives nothing actionable | |
| You decide | Claude drafts exact strings at planning time | |

**User's choice:** Distinct messages per limit

### Q2: Disclose remaining quota on successful calls?

| Option | Description | Selected |
|--------|-------------|----------|
| Silent until refusal (Recommended) | EvidencePack wire format untouched (Phase 10 D-02); refusals carry the reset time | ✓ |
| Quota hint on success | Friendlier but widens EvidencePack or wraps the payload | |
| You decide | Claude picks at planning time | |

**User's choice:** Silent until refusal

### Q3: Which wording does Exa credit exhaustion borrow in demo mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Global daily-cap wording (Recommended) | Semantically honest; public URL looks rationed, never broken; non-demo keeps "retrieval unavailable, try again" | ✓ |
| Keep "retrieval unavailable" | Simpler but the public URL looks broken instead of rationed | |
| You decide | Claude picks at planning time | |

**User's choice:** Global daily-cap wording

---

## HTTP hardening front-load

### Q1: Front-load HOST-06's TransportSecuritySettings now or defer to Phase 13?

| Option | Description | Selected |
|--------|-------------|----------|
| Front-load safe local config (Recommended) | Explicit localhost allowlist now; Phase 13 swaps in the Fly hostname; mirrors Phase 10's HOST-05 front-load | ✓ |
| SDK defaults now, configure in 13 | Less Phase 11 surface but local HTTP runs unhardened and Phase 13 retrofits | |
| You decide | Claude picks after the planner confirms SDK default behavior | |

**User's choice:** Front-load safe local config

### Q2: Local HTTP bind defaults?

| Option | Description | Selected |
|--------|-------------|----------|
| 127.0.0.1:8000, env-overridable (Recommended) | Loopback-only by default; Phase 13 Dockerfile overrides host explicitly | ✓ |
| 0.0.0.0:8000 from the start | Fly-ready but exposes every local run on all interfaces | |
| You decide | Claude picks at planning time | |

**User's choice:** 127.0.0.1:8000, env-overridable

### Q3: Add `make mcp-demo` now or in Phase 13?

| Option | Description | Selected |
|--------|-------------|----------|
| Add mcp-demo now (Recommended) | One Makefile line; needed to exercise the rationed server locally this phase | ✓ |
| Phase 13 with the Dockerfile | Tighter scope but no convenient local way to run the limiter | |
| You decide | Claude picks at planning time | |

**User's choice:** Add mcp-demo now

---

## Claude's Discretion

- Exact refusal-message strings and reset-time formatting details (within D-06 constraints)
- Concurrency-protection mechanism for counters (asyncio.Lock vs no-await critical sections)
- Per-IP bucket pruning, internal limits.py API shape, clock-injection mechanics
- Client-IP middleware mount path given the SDK finding (no middleware kwarg on streamable_http_app) and how the IP reaches the tool
- Startup log wording for demo-mode/limit state

## Deferred Ideas

None — discussion stayed within phase scope. (Fly deploy artifacts and production hostname allowlist stay in Phase 13; resources/prompt and full-tier tool stay in Phase 12.)
