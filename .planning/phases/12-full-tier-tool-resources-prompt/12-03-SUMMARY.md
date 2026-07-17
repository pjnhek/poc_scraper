---
phase: 12-full-tier-tool-resources-prompt
plan: 03
subsystem: api
tags: [mcp, fastmcp, python, pydantic, tiered-access, protocol-typing]

# Dependency graph
requires:
  - phase: 12-01
    provides: "Deps extended with exa/browserbase/limiter fields; process_account(run_eval=, on_stage=) additive params; open_deps() wiring seam"
  - phase: 12-02
    provides: "icp://rubric and icp://eval-report resources; research_account prompt; resolve_and_log_tier"
provides:
  - "EvidenceDeps structural Protocol (src/mcp_server/wiring.py) letting get_account_evidence type-check against both ThinDeps and the extended pipeline Deps"
  - "make_full_lifespan(settings) — full-tier lifespan delegating entirely to open_deps, one shared httpx pool, replay/record inherited for free"
  - "research_account_full MCP tool: full grounded pipeline with per-stage progress reporting, run_eval toggle, and D-06-compliant description"
  - "tier-gated tool registration in build_server via explicit tier: Literal['thin','full'] parameter, independent of the settings kwarg"
  - "tier threading in __main__.py from resolve_and_log_tier through lifespan selection and build_server, independent of transport"
affects: [13-hosted-demo-deploy-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural Protocol with @property members for covariant lifespan-context typing under strict mypy (EvidenceDeps)"
    - "Additive-parameter-with-default tier gating on build_server (tier: Literal['thin','full'] = 'thin')"
    - "Progress-reporting closure over ctx.report_progress computing index/total from run_eval, passed as process_account's on_stage"

key-files:
  created: []
  modified:
    - src/mcp_server/wiring.py
    - src/mcp_server/server.py
    - src/mcp_server/__main__.py
    - tests/functional/test_mcp_server.py

key-decisions:
  - "EvidenceDeps uses @property members (not plain attributes) so both ThinDeps (limiter: DemoLimiter | None) and the extended Deps (limiter: bare None) satisfy it covariantly under strict mypy without inheritance"
  - "make_full_lifespan is a one-line delegation to open_deps rather than an independent second Exa/Browserbase construction, so the full-tier server runs one httpx pool and inherits replay/record branching"
  - "tier is threaded through build_server as an explicit parameter, never re-derived from the settings=None/not-None check, so MCP_DEMO_MODE hides research_account_full even with full keys present regardless of transport"
  - "research_account_full's only try/except wraps process_account as a catch-all; process_account's internal per-stage isolation already handles domain failures, so no stage re-composition happens in the MCP layer"

patterns-established:
  - "Tier-gated MCP tool registration: gate at server.tool() registration time (hidden from list_tools), not at call time (visible-but-refusing)"

requirements-completed: [MCP-05]

coverage:
  - id: D1
    description: "Full-tier server (tier='full') registers both get_account_evidence and research_account_full; a thin-tier server registers only get_account_evidence"
    requirement: "MCP-05"
    verification:
      - kind: unit
        ref: "tests/functional/test_mcp_server.py#test_full_tool_registered_and_described_over_stdio"
        status: pass
      - kind: unit
        ref: "tests/functional/test_mcp_server.py#test_build_server_default_tier_registers_thin_tool_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "MCP_DEMO_MODE=1 with all four full-tier keys present resolves to thin tier and hides research_account_full from list_tools (roadmap success criterion 2)"
    requirement: "MCP-05"
    verification:
      - kind: unit
        ref: "tests/functional/test_mcp_server.py#test_demo_hides_full_tool_even_with_full_keys_present"
        status: pass
    human_judgment: false
  - id: D3
    description: "research_account_full carries readOnlyHint=True/destructiveHint=False annotations and a description containing the 30-60s runtime warning, run_eval=False latency hint, and [N] citation contract"
    requirement: "MCP-05"
    verification:
      - kind: unit
        ref: "tests/functional/test_mcp_server.py#test_full_tool_registered_and_described_over_stdio"
        status: pass
    human_judgment: false
  - id: D4
    description: "The full-tier lifespan is a thin wrapper around open_deps, sharing one httpx pool with get_account_evidence and inheriting replay/record branching"
    requirement: "MCP-05"
    verification:
      - kind: unit
        ref: "tests/functional/test_mcp_server.py#test_make_full_lifespan_delegates_to_open_deps"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live pipeline exercise of research_account_full through an actual multi-stage call (progress closure firing, run_eval semantics, ScoredAccount round-trip) — deferred to Plan 12-04's behavioral tests per this plan's scope"
    verification: []
    human_judgment: true
    rationale: "Plan explicitly scopes this plan to registration/wiring-level tests; Plan 12-04 owns the behavioral full-tool tests that exercise process_account through the tool"

# Metrics
duration: 15min
completed: 2026-07-17
status: complete
---

# Phase 12 Plan 3: Full-Tier Tool Wiring & Registration Summary

**Gated `research_account_full` MCP tool wired through a shared `open_deps` lifespan, tier-gated at registration time so `MCP_DEMO_MODE` provably hides it even with full BYOK keys present**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-17T04:36:00Z (approx.)
- **Completed:** 2026-07-17T04:44:00Z (approx.)
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `EvidenceDeps` structural Protocol in `src/mcp_server/wiring.py` lets `get_account_evidence` type-check against both `ThinDeps` and the extended pipeline `Deps` without either inheriting from the other, using `@property` members for covariant `limiter` typing under strict mypy
- `make_full_lifespan(settings)` delegates entirely to `open_deps(settings)` — one shared httpx connection pool for the full-tier server, replay/record branching inherited automatically
- `research_account_full(domain, ctx, run_eval=True) -> ScoredAccount` runs the complete grounded pipeline via `process_account`, reporting per-stage progress (`enrich`/`score`/`contacts`/`outreach`/`eval`) through a closure over `ctx.report_progress`
- `build_server` gains an explicit `tier: Literal["thin", "full"] = "thin"` parameter, independent of the pre-existing `settings` kwarg (which stays HTTP-transport-only), gating `research_account_full`'s registration so it is absent from `list_tools()` on thin/demo servers rather than merely refusing calls
- `__main__.py` captures `resolve_and_log_tier`'s return value once and threads it into both lifespan selection and `build_server`'s `tier` param, independent of `--transport`
- Roadmap success criterion 2 proven by a functional test: `MCP_DEMO_MODE=1` with all four full-tier keys present still resolves `mcp_tier() == "thin"` and `research_account_full` is absent from `list_tools()`

## Task Commits

Each task was committed atomically:

1. **Task 1: EvidenceDeps protocol and make_full_lifespan wrapping open_deps** - `dcc4126` (feat)
2. **Task 2: research_account_full tool, tier-gated registration, and tier threading in __main__** - `5cf58b3` (test, RED) then `8256027` (feat, GREEN)

_TDD task: RED (failing tests for tier gating) landed first, GREEN (implementation) immediately after; no REFACTOR commit needed._

## Files Created/Modified
- `src/mcp_server/wiring.py` - `EvidenceDeps(Protocol)` with read-only `exa`/`browserbase`/`limiter` properties; `make_full_lifespan(settings)` delegating to `open_deps`
- `src/mcp_server/server.py` - `_sanitized_validation_message` helper extracted from `get_account_evidence` and reused; `research_account_full` tool; `build_server`'s `tier` parameter and tier-gated registration branch; `get_account_evidence`/`build_server` annotations widened to `EvidenceDeps`
- `src/mcp_server/__main__.py` - captures `tier = resolve_and_log_tier(settings)`, selects `make_full_lifespan` vs `make_thin_lifespan`, passes `tier=tier` to `build_server`
- `tests/functional/test_mcp_server.py` - `test_make_full_lifespan_delegates_to_open_deps` (Task 1); `test_demo_hides_full_tool_even_with_full_keys_present`, `test_full_tool_registered_and_described_over_stdio`, `test_build_server_default_tier_registers_thin_tool_only` (Task 2)

## Decisions Made
- `EvidenceDeps` uses `@property` members rather than plain attributes specifically so `ThinDeps.limiter: DemoLimiter | None` and `Deps.limiter: None` satisfy the protocol structurally under strict mypy's covariant property-return-type check, rather than failing the invariant match plain-attribute Protocol members would require
- `research_account_full`'s progress closure computes `total`/index itself from `run_eval` in the MCP layer, keeping `process_account`'s `on_stage` callback a plain `Callable[[str], Awaitable[None]] | None` — no stage metadata crosses back into the pipeline-layer contract
- No key validation added to `__main__.py` for the full-tier path: `mcp_tier() == "full"` already implies the required keys are present, and `open_deps` defers key checks by existing design

## Deviations from Plan

None - plan executed exactly as written. All three tasks' acceptance-criteria greps, `uv run pytest tests/functional/test_mcp_server.py -x`, `make typecheck`, `make lint`, and the full `make test` (480 passed) all pass.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full-tier tool, resources, and prompt are all wired and registration-tested; Plan 12-04 (per the plan's `<tasks>` consumption note) owns the behavioral tests that actually exercise `research_account_full` through a scripted multi-stage `process_account` call (progress-closure invocation counts, `run_eval=False` status honesty end-to-end, `ScoredAccount` JSON round-trip through the wire format)
- No blockers. `EvidenceDeps`, `make_full_lifespan`, and the tier-gated `build_server` are stable seams for Plan 12-04 and Phase 13's hosted-deploy work to build on

---
*Phase: 12-full-tier-tool-resources-prompt*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files present on disk; all three task commit hashes (`dcc4126`, `5cf58b3`, `8256027`) found in git log.
