---
phase: 10-stdio-mcp-server-thin-tier
plan: 5
subsystem: mcp-security
tags: [mcp, provenance, hostname-validation, idna, tdd]

requires:
  - phase: 10-stdio-mcp-server-thin-tier
    plan: 4
    provides: exact EvidencePack byte budgeting and the shared strict hostname boundary
provides:
  - Filter-before-cap news provenance selection that preserves later valid cited evidence
  - IP-literal and semantic IDNA A-label rejection at the shared Account boundary
  - Constant bounded invalid-domain MCP errors with zero provider access
affects: [11-rate-limits-streamable-http-transport, 12-full-tier-tool-resources-prompt]

tech-stack:
  added: []
  patterns:
    - "Filter indivisible invalid provenance before applying collection count caps"
    - "Validate xn-- labels through standard-library IDNA decode and exact re-encode"

key-files:
  created: []
  modified:
    - src/mcp_server/evidence.py
    - tests/unit/test_evidence.py
    - src/models.py
    - tests/unit/test_models.py
    - tests/functional/test_mcp_server.py

key-decisions:
  - "News provenance validity is resolved across the full source tuple before NEWS_ITEM_MCP_CAP selects the first ten retained units"
  - "Account remains the only domain-validation boundary and returns constant invalid domain wording without reflecting client input"
  - "Punycode A-labels are accepted only when standard-library IDNA decode and lowercase ASCII re-encode exactly reproduce the normalized label"

patterns-established:
  - "Collection limits count retained evidence units, not rejected provider units"
  - "MCP invalid-input tests assert isError, bounded sanitized text, and zero FakeExa calls together"

requirements-completed: [MCP-01, MCP-07]

coverage:
  - id: D1
    description: "Later valid cited news survives invalid provenance prefixes in original relative order with honest status and sequential numbering"
    requirement: "MCP-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_evidence.py::test_pack_from_context_filters_invalid_news_before_count_cap"
        status: pass
      - kind: unit
        ref: "tests/unit/test_evidence.py::test_pack_from_context_keeps_first_ten_valid_news_in_source_order"
        status: pass
    human_judgment: false
  - id: D2
    description: "Empty delimiters, IP literals, and invalid A-labels return bounded invalid-domain MCP errors before provider access"
    requirement: "MCP-07"
    verification:
      - kind: unit
        ref: "tests/unit/test_models.py::TestAccount"
        status: pass
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_invalid_domain_sanitized_error_before_provider_access"
        status: pass
      - kind: integration
        ref: "tests/functional/test_mcp_server.py::test_invalid_domain_error_is_bounded_without_raw_input_reflection"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-07-16
status: complete
---

# Phase 10 Plan 5: Final Evidence and Domain Boundary Gap Closure Summary

**Filter-before-cap evidence selection, semantic hostname validation, and fixed-size invalid-domain errors close the final deterministic Phase 10 gaps.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-16T21:33:01Z
- **Completed:** 2026-07-16T21:36:35Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments

- Filtered invalid news provenance across the full ordered source tuple before applying the ten-item cap, preserving later safe evidence, unchanged URLs, sequential numbering, honest status, and the exact wire budget.
- Rejected empty query and fragment delimiters, IPv4 and IPv6 literals, and semantically invalid IDNA A-labels at the shared `Account` boundary.
- Replaced raw-input-reflecting validation details with constant `invalid domain` wording and proved a roughly one-million-character input produces a client result under 256 UTF-8 bytes with zero Exa calls.

## Task Commits

Each TDD task was committed as RED then GREEN:

1. **Task 1: Filter invalid news provenance before the count cap**
   - `4d3f15f` (test, RED)
   - `ac5e477` (fix, GREEN)
2. **Task 2: Complete hostname validation and bound invalid-domain errors**
   - `871a4d1` (test, RED)
   - `9c30397` (fix, GREEN)
3. **Plan cleanup**
   - `b108fdd` (refactor, Black-only formatting)

## Files Created/Modified

- `src/mcp_server/evidence.py` - Filters URL-safe news units before selecting the retained count.
- `tests/unit/test_evidence.py` - Covers invalid-prefix valid-tail recovery and first-ten retained ordering.
- `src/models.py` - Adds delimiter, IP-literal, and semantic IDNA validation with constant error wording.
- `tests/unit/test_models.py` - Extends the supported and rejected hostname matrix.
- `tests/functional/test_mcp_server.py` - Proves bounded sanitized errors and zero provider calls for residual invalid families.

## Decisions Made

- Count caps apply only after indivisible provenance validation because rejected units must not consume the client-visible evidence allowance.
- Domain validation remains centralized in `Account`; `server.py` continues to translate its first stable validation message without duplicating policy.
- Standard-library `ipaddress` and IDNA codecs are sufficient for this boundary, so no dependency or DNS resolution was added.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The sandbox could not open the existing uv cache, so offline verification ran with scoped cache access.
- The first full lint pass found Black-only formatting drift in the two Task 1 files. Black was applied only to those files, the focused tests were rerun, and the cleanup was committed separately.

## User Setup Required

None. No dependencies, configuration, environment variables, or external service changes were introduced.

## Verification Results

- `uv run pytest tests/unit/test_evidence.py -x -q` - 13 passed
- `uv run mypy src/mcp_server/evidence.py tests/unit/test_evidence.py` - clean
- `uv run pytest tests/unit/test_models.py tests/functional/test_mcp_server.py -x -q` - 91 passed
- `uv run mypy src/models.py tests/unit/test_models.py tests/functional/test_mcp_server.py` - clean
- `make test` - 421 passed, 3 smoke tests deselected
- `make typecheck` - strict mypy clean across 32 source files
- `make lint` - Ruff clean; Black would leave all 76 files unchanged
- Paid `make smoke-mcp` - intentionally not run

## Next Phase Readiness

- The two blockers and directly related error-size warning from `10-VERIFICATION.md` now have production fixes and adversarial offline regressions.
- Phase 10 is ready for canonical re-verification. Existing real-client and subprocess transport evidence remains unchanged.

## Self-Check: PASSED

- All five modified task files exist.
- Commits `4d3f15f`, `ac5e477`, `871a4d1`, `9c30397`, and `b108fdd` exist in git history.
- The final full offline test, strict type, Ruff, and Black gates pass.
- Stub scans and `git diff --check` are clean for the modified task surface.
- No unrelated worktree changes were staged, restored, deleted, or committed.

---
*Phase: 10-stdio-mcp-server-thin-tier*
*Completed: 2026-07-16*
