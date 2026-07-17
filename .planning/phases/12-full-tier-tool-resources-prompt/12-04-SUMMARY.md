---
phase: 12-full-tier-tool-resources-prompt
plan: 04
subsystem: testing
tags: [mcp, fastmcp, pytest-asyncio, in-memory-transport, groundedness]

# Dependency graph
requires:
  - phase: 12-full-tier-tool-resources-prompt (12-03)
    provides: research_account_full tool, tier-gated registration, make_full_lifespan, EvidenceDeps
provides:
  - Functional test coverage locking research_account_full's wire contract (complete ScoredAccount JSON, D-01/D-02/D-03/D-04 behaviors)
  - _full_lifespan_factory test harness for future full-tier functional tests
  - Green phase gate (make test / make typecheck / make lint) over the merged Wave 1-3 changeset
affects: [13-hosted-deploy-and-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Separate fake writer/judge LLM objects per test (HappyWriterLLM/HappyJudgeLLM) so judge invocation counts are independently assertable"
    - "_full_lifespan_factory yields a caller-prepared Deps, mirroring the existing _lifespan_factory pattern for ThinDeps"

key-files:
  created: []
  modified:
    - tests/functional/test_mcp_server.py

key-decisions:
  - "Reused the title=None about-text pattern from tests/integration/test_pipeline_failures.py::_exa_about so the justification summary is snippet-derived and reliably clears the rapidfuzz citation-coverage gate at the default 0.4 threshold"
  - "Progress test asserts the exact 5-notification contract (values 1.0..5.0, total 5.0, enrich/score/contacts/outreach/eval order) since the in-memory session shares real Session machinery end-to-end, no fallback weakening needed"

patterns-established:
  - "Full-tier functional tests build Deps directly via src.pipeline.build_deps with stub writer/judge/exa, never touching live network or the ThinDeps/limiter path"

requirements-completed: [MCP-05]

coverage:
  - id: D1
    description: "Full happy path: research_account_full returns isError=False with complete ScoredAccount JSON (account, status, enrichment, score, contacts, hooks, eval_score, error) and every hook's cited_indices resolves within enrichment.justifications indices"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_full_tool_happy_path_returns_complete_scored_account"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_eval=False yields eval_score null, status clean, and zero judge invocations (D-02 honesty)"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_full_tool_run_eval_false_skips_judge"
        status: pass
    human_judgment: false
  - id: D3
    description: "Empty retrieval is a successful result (isError=False) with status hook_suppressed and error='empty enrichment' (D-03 degraded mirroring)"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_full_tool_empty_retrieval_mirrors_sheet_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "Invalid domain returns isError=True with sanitized 'invalid domain' text, no traceback/filesystem leakage, and no provider access"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_full_tool_invalid_domain_sanitized_error"
        status: pass
    human_judgment: false
  - id: D5
    description: "Per-stage progress notifications: exactly 5 events over the real JSON-RPC round-trip, progress 1.0..5.0 with total 5.0, in enrich/score/contacts/outreach/eval order (D-04)"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_full_tool_reports_five_stage_progress_notifications"
        status: pass
    human_judgment: false
  - id: D6
    description: "Phase gate green on the merged Wave 1-3 changeset: make test, make typecheck, make lint all exit 0"
    verification:
      - kind: other
        ref: "make test && make typecheck && make lint"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-07-17
status: complete
---

# Phase 12 Plan 04: Full-Tier Wire Contract Tests + Phase Gate Summary

**Five new in-memory MCP functional tests lock research_account_full's complete ScoredAccount JSON payload, run_eval honesty, degraded-stage mirroring, sanitized errors, and per-stage progress; phase gate green after one black-formatting fix.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-17T04:47:00Z (STATE.md last-activity baseline)
- **Completed:** 2026-07-17T04:53:53Z
- **Tasks:** 2
- **Files modified:** 1 (`tests/functional/test_mcp_server.py`)

## Accomplishments

- Added `_full_lifespan_factory`, `HappyWriterLLM`, `HappyJudgeLLM`, `_full_about`, and `_build_full_test_deps` test scaffolding to `tests/functional/test_mcp_server.py`, reusing the CLAUDE.md functional-test convention of stubs at the API boundary (fake writer/judge LLMs, `FakeExa`, `NullBrowserbase`) via `build_deps`.
- `test_full_tool_happy_path_returns_complete_scored_account` proves roadmap success criterion 1: `structuredContent` carries all eight `ScoredAccount` field names, and every hook's `cited_indices` is a subset of `enrichment.justifications` indices (D-01).
- `test_full_tool_run_eval_false_skips_judge` proves D-02: `eval_score` is `None`, `status` is `"clean"`, and the judge fake records zero `synthesize` calls.
- `test_full_tool_empty_retrieval_mirrors_sheet_row` proves D-03: empty Exa retrieval returns `isError=False` with `status="hook_suppressed"`, `error="empty enrichment"`, `score=None`, and no hooks — never promoted to a tool error.
- `test_full_tool_invalid_domain_sanitized_error` extends the thin tool's leak-proof assertions (T-12-11) to `research_account_full`: sanitized "invalid domain" text, no traceback, no filesystem path, and zero Exa calls (validation precedes provider access).
- `test_full_tool_reports_five_stage_progress_notifications` proves D-04 over the real JSON-RPC round-trip: exactly 5 notifications, progress 1.0 through 5.0 with total 5.0, messages ending in "complete" for enrich/score/contacts/outreach/eval in order — no fallback weakening needed, confirming the in-memory harness propagates progress end-to-end as expected.
- Ran the full merged-changeset gate (`make test && make typecheck && make lint`); fixed the sole failure (black formatting on the new test code) and reconfirmed all three gates green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Behavioral functional tests for research_account_full over the in-memory transport** - `28692cc` (test)
2. **Task 2: Phase gate — full offline suite, strict mypy, lint** - `7a8f533` (style)

**Plan metadata:** (this commit)

## Files Created/Modified

- `tests/functional/test_mcp_server.py` - Added `_full_lifespan_factory`, `_full_about`, `HappyWriterLLM`, `HappyJudgeLLM`, `_build_full_test_deps`, and five new `test_full_tool_*` functional tests covering the full tool's happy path, run_eval=False, empty retrieval, invalid domain, and progress notifications

## Decisions Made

- Kept `HappyWriterLLM` and `HappyJudgeLLM` as two separate fake objects (rather than one shared fake dispatching on system-prompt marker) specifically so `judge.calls == 0` is independently assertable for the D-02 test without also depending on writer call counts.
- Used `title=None` on the fake about-page `ExaResult` (mirroring `tests/integration/test_pipeline_failures.py::_exa_about`) so the justification summary is derived from the repeated snippet text, guaranteeing the writer's claim clears the `rapidfuzz` `groundedness_suppress_threshold` (0.4) gate in `src/citations.py::check_claim_coverage` without hand-tuning fuzzy-match scores.
- Progress test asserts the full 5-notification contract (not a weakened count-only fallback) since `mcp.shared.memory.create_connected_server_and_client_session` shares the real `BaseSession` progress-callback machinery (`send_request`'s auto `progressToken` attachment plus `Context.report_progress`'s notification), confirmed by reading the installed SDK before writing the test per the plan's `read_first` instruction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] black reformatting on the new test file**
- **Found during:** Task 2 (phase gate run)
- **Issue:** `make lint`'s `black --check` step failed on two spots in the newly added tests (a long tuple literal and a call-tool line exceeding the wrap point black prefers) — cosmetic only, `ruff check` and `mypy` were already clean.
- **Fix:** Ran `uv run black tests/functional/test_mcp_server.py`; no logic changed, confirmed via `black --check` passing afterward and the full test suite still green.
- **Files modified:** tests/functional/test_mcp_server.py
- **Verification:** `make test && make typecheck && make lint` all exit 0 after the fix
- **Committed in:** `7a8f533` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/formatting)
**Impact on plan:** Cosmetic only, no scope creep. Matches the plan's explicit allowance for "formatting, import ordering, unused imports, type annotations, and test adjustments."

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 12 (full-tier tool, resources & prompt) is complete: all four plans landed, MCP-05's functional wire contract is proven, and the merged changeset passes the full offline gate (485 tests, strict mypy over `src`/`evals`, ruff + black clean).
- `git diff --stat tests/integration/test_pipeline_failures.py tests/integration/test_pipeline.py` and `pyproject.toml` confirmed empty — no pre-existing pipeline tests or mypy overrides were touched across the phase.
- Ready to hand off to Phase 13 (hosted deploy & docs), which owns HOST-06 (`TransportSecuritySettings` + `fly.toml` pin) and the cross-cutting TEST-01 coverage gate per STATE.md's accumulated decisions.

---
*Phase: 12-full-tier-tool-resources-prompt*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: tests/functional/test_mcp_server.py
- FOUND: .planning/phases/12-full-tier-tool-resources-prompt/12-04-SUMMARY.md
- FOUND: commit 28692cc (Task 1)
- FOUND: commit 7a8f533 (Task 2)
