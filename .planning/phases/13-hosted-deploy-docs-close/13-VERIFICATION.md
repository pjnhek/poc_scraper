---
phase: 13-hosted-deploy-docs-close
verified: 2026-07-17T18:45:00Z
status: passed
score: 6/6 must-haves verified (6 requirements: HOST-03, HOST-05, HOST-06, DOCS-01, DOCS-02, TEST-01)
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The HTTP transport is configured with an explicit TransportSecuritySettings allowed-hosts allowlist sourced from a public-hostname setting distinct from the bind address, and fly.toml pins exactly one machine so in-memory rate limits stay truly global"
    reason: "Deploy target was pivoted mid-phase: Fly.io -> Hugging Face Spaces -> Oracle Cloud Always Free, because both Fly.io and HF Spaces gate Docker/container hosting behind a payment method or PRO subscription and Oracle Always Free is $0/mo. The live hosted URL is https://170.9.7.144.sslip.io/mcp (a single Oracle Cloud VM), not a Fly.io URL. fly.toml, the Dockerfile, and the HF push script remain committed as documented, unverified-live alternatives in docs/DEPLOY.md's appendix, and continue to encode the single-machine/suspend-on-idle posture for an operator who chooses that target. The single-global-limiter intent behind 'fly.toml pins exactly one machine' is satisfied on the live target by construction (exactly one Oracle VM, one Docker container, no scale-out mechanism), independently confirmed live (oci compute instance list = 1 result, docker ps -a = 1 container, per 13-04-SUMMARY.md and re-confirmed by this verification's fresh live probe below)."
    accepted_by: "STATE.md decision log (13-04 entries) + 13-CONTEXT.md pivot framing supplied to this verification run"
    accepted_at: "2026-07-17T18:21:41Z"
---

# Phase 13: Hosted Deploy & Docs Close Verification Report

**Phase Goal:** A stranger can connect to a public, safely-configured hosted MCP URL with zero setup, and the project charter/README reflect the new MCP surface.
**Verified:** 2026-07-17T18:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria, mapped to requirement IDs)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A stranger connects to the hosted URL (directly or via `npx mcp-remote`) with zero setup and retrieves cited evidence (HOST-03) | VERIFIED (live half verified-by-record; offline scaffolding confirmed fresh) | D-14 human checkpoint recorded in `.planning/phases/13-hosted-deploy-docs-close/13-04-SUMMARY.md` and `STATE.md` (`stopped_at`/`last_activity_desc`): official MCP Python SDK client retrieved `get_account_evidence("notion.so")` with `retrieval_status: "ok"`, real `about_text`, 7+ numbered justifications each with a citation URL from source `exa`. Independently re-confirmed live by this verification run: `curl -X POST https://170.9.7.144.sslip.io/mcp` with a valid `initialize` JSON-RPC body returned HTTP 200 with a real MCP `initialize` response (`serverInfo.name: "poc-scraper", version: "1.28.1"`), and `curl -sI http://170.9.7.144.sslip.io/mcp` returned `308 Permanent Redirect` to HTTPS. |
| 2 | The HTTP transport carries an explicit `TransportSecuritySettings` allowlist sourced from a public-hostname setting distinct from the bind address, `0.0.0.0` never appears in `allowed_hosts`, verified by an integration test pairing a `0.0.0.0` bind with an external Host header; the single-machine deploy pin keeps in-memory limits global (HOST-06) | VERIFIED (offline half fully proven; live half verified-by-record + PASSED (override) on the literal "fly.toml" wording) | `src/config.py:148` defines `mcp_public_hostname: str = ""` with a D-05-citing WHY comment. `src/mcp_server/server.py:277-295` builds `allowed_hosts`/`allowed_origins` as local lists, excludes wildcard binds (`0.0.0.0`, `::`) from the bind-derived entry (line 285: `if settings.mcp_http_host not in ("0.0.0.0", "::")`), and appends the public hostname (bare + `:443`) only when `mcp_public_hostname` is set. `tests/functional/test_mcp_http_transport.py::test_public_hostname_allowed_but_bare_bind_address_is_not` (line 188) exercises exactly the described pairing and is present and passing (see TEST-01 evidence below). D-06 fail-fast guard `guard_non_loopback_requires_public_hostname` exists in `src/mcp_server/__main__.py:47-72` and is called at `main()` line 83, immediately after `guard_full_tier_http_exposure`. Live single-instance/global-limiter half: `13-04-SUMMARY.md` records `oci compute instance list` = 1 result, `docker ps -a` = 1 container, and a forged Host header rejected at both the Caddy edge (empty response) and the app's own allowlist (421 hit directly). This verification re-confirmed the Caddy-edge half live: a request with `Host: evil.example.com` against `https://170.9.7.144.sslip.io/mcp` returned HTTP 200 with **0 bytes** body (never reached the app), while the correctly-hosted request returned a full JSON-RPC `initialize` response — matching the SUMMARY's claim exactly. The literal "fly.toml pins exactly one machine" wording is satisfied via override (see frontmatter): the live target is Oracle Cloud, not Fly.io, per the documented pivot. |
| 3 | Tool error payloads never contain stack traces, env names, or key fragments, verified against a deliberately triggered failure (HOST-05) | VERIFIED (offline half re-run fresh and green; live half verified-by-record) | `tests/integration/test_mcp_error_sanitization.py` exists with `BANNED_SUBSTRINGS` (line 17) checked in a loop (line 62) against `result.content[0].text` across three tests: `test_invalid_domain_error_is_sanitized`, `test_provider_failure_error_is_sanitized`, `test_unexpected_internal_error_is_sanitized`. Fresh full-suite run by this verification (`uv run pytest -q`, 503 passed, 0 failed, includes this file) confirms they currently pass. Live half: D-14 checkpoint (`13-04-SUMMARY.md`, `STATE.md`) recorded `get_account_evidence("not-a-domain")` over `https://170.9.7.144.sslip.io/mcp` returning `isError: true` with exactly one line, `"Error executing tool get_account_evidence: invalid domain"` — no stack trace, env names, key fragments, or file paths. |
| 4 | CLAUDE.md lists `mcp>=1.28,<2.0` in the locked stack with the MCP surface noted in scope; README gains an MCP section with client config snippets (Claude Desktop, Claude Code, `npx mcp-remote`) and the grounding-by-instruction vs grounding-by-construction contrast (DOCS-01, DOCS-02) | VERIFIED | `CLAUDE.md:33` contains the literal `mcp>=1.28,<2.0`; `CLAUDE.md:13` notes the hosted rationed thin tier + BYOK full tier as in-scope; `CLAUDE.md:82-87` lists `src/mcp_server/`'s five modules; `CLAUDE.md:59-61` lists the three new MCP failure-mode bullets (rationing, fail-closed IP, sanitized errors); `CLAUDE.md:43` lists the new Makefile targets. Confirmed additive-only via `git show 51f46a5 --stat` (17 insertions, 1 deletion, all inside hand-authored sections). README: `## Try it live` at line 16, before `## Demo` at line 26; three client snippets present (`mcp-remote` line 21/167, `claude mcp add --transport http` line 173, `mcpServers` JSON block line 180); grounding contrast at lines 156-160 naming `get_account_evidence`, `research_account`, `research_account_full`; BYOK subsection (line 200) names `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`; `docs/DEPLOY.md` link present (line 202); Loom scope note present (line 30). Confirmed additive via `git show c3af73c --stat` (63 insertions only). Zero em-dashes in either file's phase-13 diff (`grep -c '—'` on README.md returns 0; the 8 em-dashes in CLAUDE.md are all in pre-existing, GSD-managed sections untouched by this phase's commit). |
| 5 | The full offline test suite (unit, functional via in-memory MCP client, integration) covers tiering, limits with an injected clock, evidence construction, and error paths; strict mypy stays clean with no new overrides (TEST-01) | VERIFIED | Independently re-run by this verification (not trusting SUMMARY claims): `uv run pytest -q` → **503 passed, 0 failed** (188.91s). `uv run mypy src evals` → **Success: no issues found in 33 source files**. `uv run ruff check src tests evals` → **All checks passed**. `uv run black --check src tests evals` → **83 files would be left unchanged**. `grep -n "ignore_errors\|ignore_missing_imports" pyproject.toml` shows only the pre-existing Google API `ignore_missing_imports` block (line 69) — no new mypy overrides. |

**Score:** 6/6 requirements verified (5/5 roadmap success criteria; one truth carries a documented, pre-approved override on its literal "fly.toml"/"Fly.io URL" wording).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/config.py` | `mcp_public_hostname` field, empty default, D-05 WHY comment | VERIFIED | Line 148: `mcp_public_hostname: str = ""`, preceded by comment block citing D-05/HOST-06 and the 11-SECURITY scope correction |
| `src/mcp_server/server.py` | Public-hostname-parametrized allowlist with wildcard-bind exclusion | VERIFIED | Lines 277-295: local list composition, `0.0.0.0`/`::` exclusion, public-hostname append |
| `src/mcp_server/__main__.py` | `guard_non_loopback_requires_public_hostname` fail-fast guard | VERIFIED | Lines 47-72, called at line 83 in `main()` |
| `tests/functional/test_mcp_http_transport.py` | D-07 bind-vs-Host test | VERIFIED | `test_public_hostname_allowed_but_bare_bind_address_is_not` at line 188, passing |
| `tests/unit/test_mcp_main_guard.py` | D-06 guard unit tests (4 new) | VERIFIED | `test_refuses_non_loopback_http_bind_without_public_hostname`, `test_allows_non_loopback_http_bind_with_public_hostname`, `test_loopback_http_bind_is_unaffected_by_hostname_guard`, `test_stdio_is_unaffected_by_hostname_guard` all present and passing |
| `tests/integration/test_mcp_error_sanitization.py` | HOST-05 banned-substring coverage | VERIFIED | `BANNED_SUBSTRINGS` constant + 3 tests, all passing |
| `Dockerfile`, `.dockerignore`, `fly.toml` | Secret-free deploy artifacts | VERIFIED (kept as documented alternative) | Present at repo root; `grep -qi EXA_API_KEY` returns no hits in either file |
| `deploy/oracle/setup.sh`, `deploy/oracle/provision.sh` | Live deploy target artifacts (post-pivot) | VERIFIED | Present; `setup.sh` builds the Caddy reverse-proxy + Docker container flow actually running the live endpoint |
| `Makefile` | `deploy-oracle`, `provision-oracle`, `deploy-hf`, `deploy-fly`, `mcp`, `mcp-http`, `mcp-demo`, `smoke-mcp` targets | VERIFIED | All present (`grep -n` confirms each target line) |
| `docs/DEPLOY.md` | Complete operator runbook, deploy-target decision chain, D-14 live verification results | VERIFIED | Contains `MCP_PUBLIC_HOSTNAME` documentation, the Fly→HF→Oracle decision chain, and the "Live real-client verification (13-04 Task 3, D-14)" section |
| `README.md` | Try it live hook, MCP section, BYOK subsection, Loom scope note | VERIFIED | All present per truth #4 evidence above |
| `CLAUDE.md` | Charter sync per D-11 | VERIFIED | All present per truth #4 evidence above |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `src/config.py` | `src/mcp_server/server.py` | `build_server` reads `settings.mcp_public_hostname` when composing `allowed_hosts`/`allowed_origins` | WIRED | Line 288: `if settings.mcp_public_hostname:` directly reads the field |
| `src/mcp_server/__main__.py` | `src/config.py` | Guard reads `settings.mcp_http_host` and `settings.mcp_public_hostname` in `main()` before `build_server` | WIRED | Guard call at line 83 precedes `build_server` call later in `main()`; guard function reads both settings fields at lines 63-64 |
| `tests/integration/test_mcp_error_sanitization.py` | `src/mcp_server/server.py` | In-memory MCP client calling `get_account_evidence` against raising stubs | WIRED | Confirmed passing in fresh full-suite run |
| `deploy/oracle/setup.sh` | `src/mcp_server/__main__.py` | Container CMD runs `python -m src.mcp_server --transport http`; `MCP_PUBLIC_HOSTNAME` in `mcp.env` feeds `Settings.mcp_public_hostname`, making the D-06 guard pass on the live `0.0.0.0` bind | WIRED | Live-confirmed: the deployed endpoint accepts the real Fly-style hostname Host header and serves valid MCP responses (fresh curl check above) |
| `README.md` | `docs/DEPLOY.md` | MCP section links to the operator runbook | WIRED | Line 202 |
| `README.md` | `https://170.9.7.144.sslip.io/mcp` | Try it live hook and all three client snippets use the confirmed live URL | WIRED | Fresh live curl confirms the URL is currently serving valid MCP protocol responses |

### Behavioral Spot-Checks (fresh, run by this verification)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full offline test suite | `uv run pytest -q` | 503 passed, 0 failed, 188.91s | PASS |
| Strict mypy, no new overrides | `uv run mypy src evals` | Success: no issues found in 33 source files | PASS |
| Lint clean | `uv run ruff check src tests evals && uv run black --check src tests evals` | All checks passed; 83 files unchanged | PASS |
| Live endpoint reachable, valid MCP response | `curl -X POST https://170.9.7.144.sslip.io/mcp` (initialize) | HTTP 200, `serverInfo.name: "poc-scraper", version: "1.28.1"` | PASS |
| HTTP→HTTPS redirect | `curl -sI http://170.9.7.144.sslip.io/mcp` | `308 Permanent Redirect` to https | PASS |
| Forged Host header rejected at Caddy edge | `curl -X POST https://170.9.7.144.sslip.io/mcp -H 'Host: evil.example.com'` (initialize) | HTTP 200 but **0 bytes** body — request never reached the app (matches `13-04-SUMMARY.md`'s recorded observation exactly) | PASS |
| Anti-pattern scan on all phase-touched files | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` across `src/config.py`, `src/mcp_server/{server,__main__}.py`, all 3 new/modified test files, `Dockerfile`, `fly.toml`, `Makefile`, `docs/DEPLOY.md`, `README.md`, `CLAUDE.md`, `deploy/oracle/{setup,provision}.sh` | Zero hits in every file | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HOST-03 | 13-02, 13-04 | Stranger connects to hosted URL with zero setup, retrieves cited evidence | SATISFIED | D-14 record (`13-04-SUMMARY.md`, `STATE.md`) + fresh live curl re-confirmation |
| HOST-05 | 13-03, 13-04 | Tool error payloads never leak stack traces/env names/key fragments | SATISFIED | Offline: `tests/integration/test_mcp_error_sanitization.py` (fresh pass). Live: D-14 record |
| HOST-06 | 13-01, 13-02, 13-04 | Public-hostname allowlist distinct from bind address; single-machine global limits | SATISFIED | Offline: `src/config.py`, `src/mcp_server/server.py`, `src/mcp_server/__main__.py`, `tests/functional/test_mcp_http_transport.py` (fresh pass). Live: D-14 record + fresh live Caddy-edge Host-header probe. "fly.toml" literal wording carried via documented override (deploy-target pivot) |
| DOCS-01 | 13-05 | CLAUDE.md lists `mcp>=1.28,<2.0`, MCP surface in scope | SATISFIED | `CLAUDE.md:33,13,82-87,59-61,43` |
| DOCS-02 | 13-05 | README MCP section with client snippets + grounding contrast | SATISFIED | `README.md:16,152-202` |
| TEST-01 | 13-01, 13-03 | Full offline test coverage; strict mypy clean, no new overrides | SATISFIED | Fresh `uv run pytest -q` (503 passed), `uv run mypy src evals` (clean), no new `pyproject.toml` mypy overrides |

No orphaned requirements: all six phase-13 requirement IDs (HOST-03, HOST-05, HOST-06, DOCS-01, DOCS-02, TEST-01) are claimed across the five plans' `requirements:` frontmatter, matching `.planning/REQUIREMENTS.md`'s Phase 13 traceability table exactly.

### Anti-Patterns Found

None. Zero `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers and zero "not yet implemented"/"coming soon" strings across every file this phase created or modified.

### Human Verification Required

None additional. The live real-client halves of HOST-03, HOST-05, and HOST-06 were already verified via the human-approved D-14 checkpoint on 2026-07-17 and are recorded (not re-runnable in this session, since the Oracle VM requires the operator's real `EXA_API_KEY`). Per the task instructions, these are marked **verified-by-record** rather than re-requested:
- `STATE.md` "Decisions" (13-04 entries) and "Current Position"
- `.planning/phases/13-hosted-deploy-docs-close/13-04-SUMMARY.md`
- `docs/DEPLOY.md`, section "Live real-client verification (13-04 Task 3, D-14)"

This verification independently corroborated the currently-observable parts of that record with fresh, non-quota-consuming live probes (MCP `initialize` handshake, HTTPS redirect, forged-Host-header edge rejection) — all matched the recorded claims exactly.

### Gaps Summary

No gaps. All six phase requirements are satisfied against the actual codebase, with one documented, pre-approved override covering the literal "Fly.io URL"/"fly.toml pins exactly one machine" roadmap wording, which was intentionally superseded mid-phase by a deploy-target pivot to Oracle Cloud Always Free (recorded in `STATE.md` and `13-04-SUMMARY.md`, matching the critical context supplied for this verification run). The pivot preserves the underlying security/cost intent (single global rate-limit domain, near-zero cost, secret-free committed artifacts) on the actual live target, independently re-confirmed live by this verification.

---

_Verified: 2026-07-17T18:45:00Z_
_Verifier: Claude (gsd-verifier)_

## Verification Complete

**Status:** passed
**Score:** 6/6 requirements verified (HOST-03, HOST-05, HOST-06, DOCS-01, DOCS-02, TEST-01)
**Report:** .planning/phases/13-hosted-deploy-docs-close/13-VERIFICATION.md

All must-haves verified. Phase goal achieved. Ready to proceed.

Notable: one override applied for the deploy-target pivot (Fly.io → Hugging Face Spaces → Oracle Cloud Always Free), documented in this report's frontmatter and matching the pre-approved context supplied for this verification. The D-14 live real-client checkpoint (HOST-03, HOST-05 live half, HOST-06 live half) was human-approved on 2026-07-17 and is treated as verified-by-record per the task instructions; this verification additionally re-confirmed the currently-observable live behavior fresh (MCP initialize handshake, HTTPS redirect, forged-Host-header edge rejection) and it matched the recorded results exactly. The full offline gate (pytest, mypy strict, ruff, black) was independently re-run by this verification, not just cited from SUMMARY.md, and is green with zero failures and zero new mypy overrides.
