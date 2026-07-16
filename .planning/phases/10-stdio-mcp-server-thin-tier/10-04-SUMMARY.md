---
phase: 10-stdio-mcp-server-thin-tier
plan: 4
subsystem: mcp-security
tags: [mcp, evidence-budget, utf-8, hostname-validation, tdd]

requires:
  - phase: 10-stdio-mcp-server-thin-tier
    plan: 2
    provides: thin-tier evidence composition and get_account_evidence tool
  - phase: 10-stdio-mcp-server-thin-tier
    plan: 3
    provides: real stdio transport and client verification
provides:
  - Exact 24000-byte UTF-8 serialization ceiling for every returned EvidencePack
  - Frozen MCP-safe Citation and NewsItem copies with bounded client-visible text
  - Deterministic evidence reduction that preserves valid provenance URLs and numbering
  - Shared strict hostname normalization before any MCP provider access
affects: [11-rate-limits-streamable-http-transport, 12-full-tier-tool-resources-prompt]

tech-stack:
  added: []
  patterns:
    - "Wire budgets are enforced against final model_dump_json UTF-8 bytes, not estimated character counts"
    - "Untrusted domains are normalized once in Account using urlsplit plus explicit ASCII DNS-label validation"

key-files:
  created: []
  modified:
    - src/mcp_server/evidence.py
    - tests/unit/test_evidence.py
    - src/models.py
    - tests/unit/test_models.py
    - tests/functional/test_mcp_server.py

key-decisions:
  - "Citation URLs are indivisible provenance: evidence units above the 2048-byte URL cap are dropped rather than rewritten or sliced"
  - "MCP-safe citations clear redundant title and snippet fields while preserving URL, source, and retrieved_at"
  - "Account accepts only bare ASCII or punycode hostnames and root HTTP(S) URLs; every other URL component is rejected before retrieval"

patterns-established:
  - "Deterministic pack reduction removes tail news first, then shrinks about text on Unicode code-point and word boundaries, then removes tail about provenance"
  - "Malformed MCP input tests assert both sanitized isError output and zero FakeExa calls"

requirements-completed: [MCP-01, MCP-07]

coverage:
  - id: D1
    description: "Every EvidencePack is serialized within the exact UTF-8 byte ceiling while nested text is bounded and retained citation URLs remain unchanged"
    requirement: "MCP-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_evidence.py (nested text, multibyte, escaping, long URL, deterministic reduction, honest status)"
        status: pass
      - kind: integration
        ref: "uv run pytest tests/unit/test_evidence.py tests/unit/test_models.py tests/functional/test_mcp_server.py -q (81 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Malformed hostname input returns a sanitized MCP tool error before any Exa request"
    requirement: "MCP-07"
    verification:
      - kind: unit
        ref: "tests/unit/test_models.py::TestAccount"
        status: pass
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_invalid_domain_sanitized_error_before_provider_access"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-16
status: complete
---

# Phase 10 Plan 4: Evidence and Hostname Boundary Gap Closure Summary

**Exact serialized EvidencePack budgeting and strict shared hostname validation close the two Phase 10 verifier gaps without changing the wire schema or adding dependencies.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-16T20:56:30Z
- **Completed:** 2026-07-16T21:06:27Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments

- Added frozen MCP-safe evidence copies, exact UTF-8 serialization measurement, indivisible provenance caps, and deterministic reduction to guarantee every returned `EvidencePack` is at most 24,000 bytes.
- Added adversarial coverage for four-byte Unicode, JSON escaping, long valid URLs, over-limit URLs, nested citation fields, source-order reduction, sequential renumbering, honest status, and caller immutability.
- Replaced permissive domain cleanup with shared root HTTP(S) parsing and ASCII DNS-label validation, then proved malformed MCP input returns a sanitized tool error before `FakeExa` records a call.

## Task Commits

Each task followed RED then GREEN and was committed atomically:

1. **Task 1: Enforce the serialized EvidencePack byte budget**
   - `0ae9fff` (test, RED)
   - `e83ce50` (feat, GREEN)
2. **Task 2: Reject malformed hostnames before provider access**
   - `aea4000` (test, RED)
   - `2a1cfbd` (feat, GREEN)

## Files Created/Modified

- `src/mcp_server/evidence.py` - Safe nested copies, exact serialized-size checks, URL-unit filtering, and deterministic reducer.
- `tests/unit/test_evidence.py` - Adversarial wire-budget, provenance-integrity, reduction-order, status, and immutability regressions.
- `src/models.py` - Standard-library URL parsing and strict shared ASCII hostname validation.
- `tests/unit/test_models.py` - Supported normalization and malformed-hostname matrices.
- `tests/functional/test_mcp_server.py` - In-memory MCP proof that malformed input never reaches Exa.

## Decisions Made

- Retained citation URLs are never shortened or rewritten. An evidence unit with an over-limit URL is discarded completely.
- Citation title and snippet are cleared only on frozen MCP copies because bounded justification summaries and news fields are the canonical client-visible text.
- Domain parsing remains in `Account`, so CSV, pipeline, and MCP callers share one trust boundary rather than duplicating MCP-only validation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cleared strict-mypy failures in the modified model test file**
- **Found during:** Task 2 acceptance verification
- **Issue:** File-scoped strict mypy exposed pre-existing direct `Citation(url=str)` construction errors and now-unused assignment ignores in `tests/unit/test_models.py`.
- **Fix:** Switched valid fixtures to the existing typed `Citation.make` factory and removed unused ignores. Test behavior is unchanged.
- **Files modified:** `tests/unit/test_models.py`
- **Verification:** The task-scoped strict mypy command and full `make typecheck` both pass.
- **Committed in:** `2a1cfbd`

---

**Total deviations:** 1 auto-fixed (1 blocking issue)
**Impact on plan:** The fix was required by the plan's strict-mypy acceptance gate and stayed within the already modified test file.

## Issues Encountered

- The sandbox could not open the existing uv cache. The offline verification commands were rerun with scoped cache access and passed. No network or paid live smoke was used.

## User Setup Required

None. No dependency, environment variable, or external service change was introduced.

## Verification Results

- `uv run pytest tests/unit/test_evidence.py tests/unit/test_models.py tests/functional/test_mcp_server.py -q` - 81 passed
- `make test` - 398 passed, 3 smoke tests deselected
- `make typecheck` - strict mypy clean across 32 source files
- `make lint` - Ruff clean; Black would leave all 76 files unchanged
- Paid `make smoke-mcp` - intentionally not run

## Next Phase Readiness

- Both actionable findings from `10-VERIFICATION.md` now have production fixes and adversarial regressions.
- Phase 10 is ready for canonical re-verification. Existing real-client and subprocess evidence remains unchanged.

## Self-Check: PASSED

- All five modified task files exist.
- Commits `0ae9fff`, `e83ce50`, `aea4000`, and `2a1cfbd` exist in git history.
- The full offline test, strict type, Ruff, and Black gates pass.
- No unrelated worktree changes were staged, restored, deleted, or committed.

---
*Phase: 10-stdio-mcp-server-thin-tier*
*Completed: 2026-07-16*
