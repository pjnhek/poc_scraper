---
phase: 12-full-tier-tool-resources-prompt
plan: 01
subsystem: api
tags: [pipeline, mcp, asyncio, pydantic, tdd]

# Dependency graph
requires:
  - phase: 09-pipeline-extraction-supporting-models
    provides: open_deps() wiring seam, frozen Deps dataclass, build_deps single construction site
provides:
  - "process_account(account, deps, *, run_eval=True, on_stage=None) -> ScoredAccount: additive keyword-only seam for the full-tier MCP tool"
  - "D-02 honesty semantics: run_eval=False never produces judge_failed/low_groundedness, only the pipeline's already-determined clean/hook_suppressed outcome"
  - "D-05 progress seam: on_stage(str) fires after enrich/score/contacts/outreach, and after eval when run_eval=True, with no try/except swallowing a raising callback"
  - "Deps.exa / Deps.browserbase / Deps.limiter fields mirroring ThinDeps' shape for a future single covariant Protocol"
affects: [12-02, 12-03, 12-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive keyword-only parameters with defaults reproducing prior behavior (Phase 5 max_tokens precedent) extended to run_eval/on_stage"
    - "Deps.limiter typed bare None (not Optional[SomeLimiterType]) to keep src/pipeline.py free of any src.mcp_server import, preserving the one-directional dependency arrow"

key-files:
  created:
    - tests/integration/test_pipeline_run_eval.py
  modified:
    - src/pipeline.py

key-decisions:
  - "elif not run_eval: branch inserted between the hook_suppressed check and the eval_score is None -> judge_failed check (Pitfall 3 precedence), so a deliberate skip can never be read as either failure state"
  - "on_stage callbacks fire strictly after each stage's try/except completes without an early return, before the next stage's early-return check; eval's callback lives inside the if run_eval: guard so it never fires on a skip"
  - "No try/except wraps on_stage calls; a raising callback (e.g. a disconnected MCP client) propagates and tears down the call rather than being silently swallowed"
  - "Deps.exa/browserbase are populated from build_deps' existing exa/browserbase parameters at its single construction site; limiter stays at its None default for the full tier"

patterns-established:
  - "Stage-boundary progress hooks belong in the pipeline itself, not re-composed in a calling layer, so per-stage exception isolation and status precedence stay single-sourced"

requirements-completed: [MCP-05]

coverage:
  - id: D1
    description: "process_account gains run_eval keyword parameter; run_eval=False skips the judge and never yields judge_failed/low_groundedness"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_run_eval_false_happy_path_yields_clean_without_judge_call"
        status: pass
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_run_eval_false_with_empty_hooks_yields_hook_suppressed_not_clean"
        status: pass
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_run_eval_false_status_is_never_judge_failed_or_low_groundedness"
        status: pass
    human_judgment: false
  - id: D2
    description: "process_account gains on_stage keyword parameter firing at five stage boundaries in order, omitting eval when run_eval=False, and staying empty on an early enrich failure"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_on_stage_fires_in_order_and_omits_eval_when_run_eval_false"
        status: pass
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_on_stage_stays_empty_on_early_enrich_failure"
        status: pass
    human_judgment: false
  - id: D3
    description: "process_account stays backward compatible when called positionally with neither new argument; Deps gains exa/browserbase/limiter fields without importing from src.mcp_server"
    requirement: "MCP-05"
    verification:
      - kind: integration
        ref: "tests/integration/test_pipeline_run_eval.py#test_process_account_positional_call_stays_backward_compatible"
        status: pass
      - kind: other
        ref: "make test (465 passed) && make typecheck (mypy strict, 33 files clean)"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-17
status: complete
---

# Phase 12 Plan 01: Pipeline run_eval / on_stage Seams Summary

**process_account gains additive run_eval and on_stage keyword-only parameters (D-02/D-05) and Deps exposes exa/browserbase/limiter, all with zero behavior change for existing callers**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-17T04:20:03Z
- **Completed:** 2026-07-17T04:24:28Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `process_account` accepts `run_eval: bool = True` and `on_stage: Callable[[str], Awaitable[None]] | None = None`, both keyword-only and additive
- D-02 honesty semantics locked in code: `run_eval=False` can only ever resolve to `clean` or `hook_suppressed`, never `judge_failed`/`low_groundedness`
- D-05 progress seam: `on_stage` fires "enrich", "score", "contacts", "outreach", and (when `run_eval=True`) "eval" at the exact stage boundaries, in order, with no exception swallowing
- `Deps` extended with `exa`/`browserbase`/`limiter` fields mirroring `ThinDeps`' shape, keeping `src/pipeline.py` free of any `src.mcp_server` import (verified by grep)
- All 6 pre-existing pipeline integration tests pass with zero source changes (`git diff --stat` empty), proving `make run` behavior is untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Add run_eval and on_stage keyword parameters to process_account with D-02 status honesty** - TDD cycle:
   - RED: `d31e229` (`test(12-01): add failing tests for run_eval and on_stage seams`)
   - GREEN: `4c6350f` (`feat(12-01): add run_eval and on_stage keyword parameters to process_account`)
2. **Task 2: Extend Deps with exa/browserbase/limiter fields, keeping pipeline.py MCP-free** - `0cfd31b` (`feat(12-01): extend Deps with exa/browserbase/limiter fields`)

_Note: Task 1 used the TDD RED/GREEN cycle per its `tdd="true"` marker; no REFACTOR commit was needed._

## Files Created/Modified
- `tests/integration/test_pipeline_run_eval.py` - 6 new integration tests covering D-02 honesty semantics, D-05 on_stage ordering, early-failure short-circuit, and positional-call backward compatibility
- `src/pipeline.py` - `process_account` signature extended with `run_eval`/`on_stage`; five `on_stage` call sites inserted at stage boundaries; D-02/D-03 precedence chain gains the `elif not run_eval:` branch; `Deps` dataclass gains `exa`/`browserbase`/`limiter` fields; `build_deps` passes `exa`/`browserbase` through

## Decisions Made
- `elif not run_eval:` sits strictly between the `hook_suppressed` check and the `eval_score is None -> judge_failed` check, matching the plan's Pitfall 3 precedence exactly
- The eval-stage `on_stage("eval")` call lives inside the `if run_eval:` guard rather than after it, so a skip never fires a phantom "eval" progress event
- `Deps.limiter` is bare `None` (not `SomeLimiterType | None`) — the full tier is never demo mode, and typing it this way means no MCP-package import is ever needed in `src/pipeline.py`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Task 1's TDD RED phase failed as expected (`TypeError: process_account() got an unexpected keyword argument 'run_eval'`) before any implementation existed, confirming the tests genuinely exercised new behavior.

## TDD Gate Compliance

Task 1 (`tdd="true"`): RED commit `d31e229` (test-only, all 6 new tests failing) precedes GREEN commit `4c6350f` (all 6 passing, zero pre-existing test regressions). Gate sequence verified via `git log --oneline`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`process_account`'s `run_eval`/`on_stage` seam and `Deps.exa`/`browserbase`/`limiter` fields are ready for Plan 12-02/12-03 to build the full-tier MCP tool (`research_account_full`) as a thin wrapper: validate via `Account`, forward a progress closure to `ctx.report_progress`/`ctx.info`, call `process_account(account, deps, run_eval=run_eval, on_stage=closure)`, and `model_dump()` the result verbatim (D-01). No blockers identified.

---
*Phase: 12-full-tier-tool-resources-prompt*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: src/pipeline.py
- FOUND: tests/integration/test_pipeline_run_eval.py
- FOUND: .planning/phases/12-full-tier-tool-resources-prompt/12-01-SUMMARY.md
- FOUND: d31e229 (test commit)
- FOUND: 4c6350f (feat commit, Task 1)
- FOUND: 0cfd31b (feat commit, Task 2)
