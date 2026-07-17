---
phase: 12
slug: full-tier-tool-resources-prompt
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Filled from 12-RESEARCH.md's Validation Architecture section and the tasks defined in
> Plans 12-01 through 12-04.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ with pytest-asyncio (`asyncio_mode = "auto"`) and pytest-cov |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/functional/test_mcp_server.py -x` |
| **Full suite command** | `make test` (runs `uv run pytest -m "not smoke"`; smoke excluded by default) |
| **Estimated runtime** | ~2 seconds quick (45 tests today, in-memory); ~15 seconds full offline suite (459+ tests as of Phase 11 close) |

---

## Sampling Rate

- **After every task commit:** Run that task's `<automated>` command from the map below; the
  baseline quick probe is `uv run pytest tests/functional/test_mcp_server.py -x` (measured ~1.5s)
- **After every plan wave:** Run `make test && make typecheck` (Waves 2-3 add `make lint` per
  their plan verify blocks)
- **Before `/gsd-verify-work`:** `make test && make typecheck && make lint` must be green
  (Plan 12-04 Task 2 is this gate, matching the Phase 10/11 precedent)
- **Max feedback latency:** 60 seconds (heaviest per-task command is the combined
  `make test && make typecheck && make lint` gate, ~30s; all pytest-only commands are under 15s)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 run_eval + on_stage on process_account | 01 | 1 | MCP-05 (D-02, D-05) | T-12-01 | Deliberate judge skip yields only clean/hook_suppressed; never reads as judge_failed and never masks hook_suppressed (Pitfall 3 canary) | integration (TDD, RED-first) | `uv run pytest tests/integration/test_pipeline_run_eval.py -x` | ❌ RED-first in-task | ⬜ pending |
| 12-01-02 Deps exa/browserbase/limiter fields | 01 | 1 | MCP-05 | — (T-12-02/T-12-03 accepted) | pipeline.py stays free of MCP-package imports (one-directional dependency, anchored grep gate in acceptance criteria) | regression + typecheck | `make test && make typecheck` | ✅ existing suite | ⬜ pending |
| 12-02-01 icp://rubric + icp://eval-report resources | 02 | 1 | MCP-02, MCP-03 (D-07, D-08) | T-12-04 | OSError caught inside the resource function; sanitized non-empty "resource unavailable" text; no filesystem path or exception text leaks (sentinel-path assertion) | unit + functional (TDD, RED-first) | `uv run pytest tests/unit/test_mcp_resources.py tests/functional/test_mcp_server.py -x` | ❌ RED-first in-task (unit file new; functional file exists) | ⬜ pending |
| 12-02-02 research_account prompt | 02 | 1 | MCP-04 (D-09, D-10, D-11) | T-12-05 (accepted) | Prompt is advisory client-side text; hard [N]-citation/drop/never-fabricate rules present; never names research_account_full (D-11 tier-leak gate) | functional (TDD, RED-first) | `uv run pytest tests/functional/test_mcp_server.py -k "research_account_prompt or list_prompts" -x` | ✅ extends existing file | ⬜ pending |
| 12-03-01 EvidenceDeps protocol + make_full_lifespan | 03 | 2 | MCP-05 | — | Single client stack via open_deps delegation (one httpx pool; replay/record inherited, no silent fixture bypass) | functional + strict mypy | `uv run pytest tests/functional/test_mcp_server.py -x && make typecheck` | ✅ extends existing file | ⬜ pending |
| 12-03-02 research_account_full + tier gating + __main__ threading | 03 | 2 | MCP-05 (D-01, D-04, D-05, D-06) | T-12-07, T-12-08, T-12-09 | Demo mode with full keys hides the tool at registration (ASVS V4; roadmap criterion 2); sanitized error payloads (HOST-05); domain validated through Account before any provider access (ASVS V5) | functional (TDD, RED-first) | `uv run pytest tests/functional/test_mcp_server.py -x && make typecheck && make lint` | ✅ extends existing file | ⬜ pending |
| 12-04-01 wire-level behavioral tests for the full tool | 04 | 3 | MCP-05 criterion 1 (D-01, D-02, D-03, D-04) | T-12-11, T-12-12 | Invalid-domain payload leak-proof at the JSON-RPC level (no traceback, no filesystem paths); run_eval honesty pinned over the wire (eval_score null + clean + zero judge calls) | functional | `uv run pytest tests/functional/test_mcp_server.py -x` | ✅ extends existing file | ⬜ pending |
| 12-04-02 phase gate | 04 | 3 | MCP-05 (phase close) | — | No new mypy overrides (pyproject.toml diff empty); pre-existing pipeline tests unmodified (git diff --stat empty) | full offline gate | `make test && make typecheck && make lint` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*File Exists legend: "❌ RED-first in-task" means the test file does not exist yet and is written
as the FIRST step of its owning `tdd="true"` task (tests fail, then implementation lands). No task
carries a `MISSING — Wave 0` automated reference, so no standalone Wave 0 pass precedes Wave 1.*

---

## Wave 0 Requirements

Existing infrastructure covers Wave 0. pytest, pytest-asyncio (auto mode), strict mypy, Ruff,
Black, the in-memory MCP harness (`mcp.shared.memory` via
`create_connected_server_and_client_session`), `_lifespan_factory`, and the
`FakeExa`/`FakeBrowserbase`/fake-LLM stub patterns in `tests/integration/test_pipeline_failures.py`
all predate this phase. RESEARCH.md's Wave 0 gap list is absorbed into RED-first TDD tasks rather
than a separate scaffold pass:

- `tests/integration/test_pipeline_run_eval.py` — created RED-first by Plan 12-01 Task 1
  (subsumes RESEARCH's proposed `tests/unit/test_pipeline_status.py`; RESEARCH offered "new file,
  or extend" and the plan chose the integration-level file so D-02 precedence is tested through
  the real `process_account` path)
- `tests/unit/test_mcp_resources.py` — created RED-first by Plan 12-02 Task 1 (D-08 sanitization,
  isolated from SDK error-wrapping)
- `_full_lifespan_factory` + full-tool behavioral tests in `tests/functional/test_mcp_server.py` —
  added by Plan 12-04 Task 1 (file already exists)
- Framework install: none — no new packages this phase (RESEARCH Package Legitimacy Audit)

---

## Manual-Only Verifications

All phase behaviors have automated verification. Functional tests stub at the API boundary
(fake writer/judge LLMs, FakeExa, Null/Fake Browserbase) per the CLAUDE.md 5-layer strategy; a
live BYOK exercise of `research_account_full` is deliberately out of this phase's scope
(RESEARCH Environment Availability — the replay/record `DEMO_BUNDLE` infrastructure is the
established no-keys fallback, and a live smoke extension would follow the Phase 10 `make smoke-mcp`
precedent in a later phase if wanted).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands (map above; zero `MISSING — Wave 0` references)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (all 8 tasks have one)
- [x] Wave 0 covers all MISSING references (none exist; RESEARCH gaps absorbed into RED-first TDD tasks)
- [x] No watch-mode flags (all commands use `-x`/`-k` one-shot invocations)
- [x] Feedback latency < 60s (quick probe measured ~1.5s; full offline suite ~15s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-16
