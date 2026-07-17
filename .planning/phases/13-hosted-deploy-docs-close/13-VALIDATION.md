---
phase: 13
slug: hosted-deploy-docs-close
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-17
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ / pytest-asyncio (auto mode), already configured |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (no changes needed) |
| **Quick run command** | `uv run pytest tests/unit/test_mcp_main_guard.py tests/functional/test_mcp_http_transport.py -q` |
| **Full suite command** | `make test` (`uv run pytest -m "not smoke"`) |
| **Estimated runtime** | quick ~10s, full ~60-90s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command plus `uv run mypy src evals`
- **After every plan wave:** Run `make test`
- **Before `/gsd-verify-work`:** Full suite green, `make typecheck` and `make lint` clean, D-14 live checkpoint recorded
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | HOST-06 | T-13-01 | Public hostname allowlisted; 0.0.0.0 bind never allowlisted | functional | `uv run pytest tests/functional/test_mcp_http_transport.py -q` | created in-task (tdd) | pending |
| 13-01-02 | 01 | 1 | HOST-06 | T-13-02 | Non-loopback bind without hostname refuses to start | unit | `uv run pytest tests/unit/test_mcp_main_guard.py -q` | created in-task (tdd) | pending |
| 13-02-01 | 02 | 1 | HOST-03 | — | N/A (dry-run observations recorded) | manual+grep | `grep -qi "dry run" docs/DEPLOY.md` | new file | pending |
| 13-02-02 | 02 | 1 | HOST-03/HOST-06 | T-13-04/T-13-05 | No secrets in committed artifacts; suspend/single-region posture | static grep | Dockerfile/fly.toml grep gate in plan | new files | pending |
| 13-02-03 | 02 | 1 | HOST-03/HOST-06 | T-13-05 | Runbook documents fly scale count 1 and forbids higher counts | static grep | DEPLOY.md grep gate in plan | new file | pending |
| 13-03-01 | 03 | 2 | HOST-05 | T-13-07 | Error payloads never contain banned substrings | integration | `uv run pytest tests/integration/test_mcp_error_sanitization.py -q` | created in-task (tdd) | pending |
| 13-03-02 | 03 | 2 | TEST-01 | — | Strict mypy clean, no new overrides | full gate | `make test && make typecheck && make lint` | existing gates | pending |
| 13-04-02 | 04 | 2 | HOST-03/HOST-06 | T-13-10/T-13-11 | Live URL accepts real Host header; single machine; thin tier logged | live curl | initialize POST gate in plan (non-421) | live check | pending |
| 13-05-01 | 05 | 3 | DOCS-02 | T-13-13 | Snippets/URLs only public hostnames; no em-dashes | static grep | README grep gate in plan | edit | pending |
| 13-05-02 | 05 | 3 | DOCS-01 | T-13-13 | Charter sync additive, hand-authored sections only | static grep | CLAUDE.md grep gate in plan | edit | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The three RESEARCH-identified test gaps are created inside tdd-marked tasks (tests written before implementation within the same task):

- [x] `tests/functional/test_mcp_http_transport.py::test_public_hostname_allowed_but_bare_bind_address_is_not` — created in plan 13-01 task 1 (RED first)
- [x] D-06 guard unit tests in `tests/unit/test_mcp_main_guard.py` — created in plan 13-01 task 2 (RED first)
- [x] `tests/integration/test_mcp_error_sanitization.py` — created in plan 13-03 task 1
- [x] Framework install: none needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stranger connects via real client and retrieves cited evidence | HOST-03 | D-14 locks live verification as a one-time human real-client checkpoint; no scripted live-smoke target allowed | Plan 13-04 task 3: `claude mcp add --transport http` or `npx mcp-remote`, call get_account_evidence for one domain |
| Live failure payload leak inspection | HOST-05 | Same D-14 lock; offline tests carry the repeatable coverage | Plan 13-04 task 3: call with domain "not-a-domain", inspect payload for traces/env names/key fragments |
| EXA_API_KEY secret set on Fly | HOST-03 | Secret value unreadable to the executor by permission policy | Plan 13-04 task 1: `fly secrets set EXA_API_KEY=...` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (checkpoint tasks use how-to-verify by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (in-task tdd creation)
- [x] No watch-mode flags
- [x] Feedback latency < 90s for offline gates
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-17 (planner)
