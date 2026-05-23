---
phase: 06-sheet-polish
plan: 01
subsystem: sheets
tags: [google-sheets, account-status, legend, polish, tests]

requires:
  - phase: 02-groundedness-fix
    provides: AccountStatus enum and STATUS_LEGEND precedence contract
provides:
  - AccountStatus-driven whole-row tinting for Sheet result rows
  - ACCOUNT_STATUS_COLORS as the single palette source for result rows and Legend tab tinting
  - Persistent Legend tab refreshed every run with all four states, color names, meanings, and precedence
  - Unit and integration coverage for the POLISH-01 visual contract
affects: [phase-06-sheet-polish, phase-08-readme-and-loom]

tech-stack:
  added: []
  patterns:
    - "Single AccountStatus palette dict feeds both result row tinting and Legend tab repeatCell requests."
    - "Clean result rows are omitted from background repeatCell requests; the Legend clean row is explicitly white."
    - "Integration tests filter repeatCell requests by sheetId so persistent Legend formatting does not mask result-tab formatting assertions."

key-files:
  created:
    - .planning/phases/06-sheet-polish/06-01-SUMMARY.md
  modified:
    - src/sheets.py
    - tests/unit/test_sheets_rows.py
    - tests/integration/test_sheets_writer.py

key-decisions:
  - "Phase 06 Plan 01: clean result rows use the no-fill convention by omitting them from account_status_row_colors output; the Legend clean row still receives explicit white RGB so the palette is visible."
  - "Phase 06 Plan 01: low_groundedness uses RGB 1.00/0.97/0.80, hook_suppressed uses RGB 1.00/0.90/0.78, and judge_failed uses RGB 0.88/0.88/0.88."
  - "Phase 06 Plan 01: judge_failed is gray, not red or orange, because it represents an out-of-band judge failure rather than writer fabrication."
  - "Phase 06 Plan 01: Rubric tab explanatory text now points readers to AccountStatus and the Legend tab instead of the removed verdict-color behavior."

patterns-established:
  - "Legend tab rows are pure data from build_legend_rows(); all visual tinting is applied separately with batchUpdate repeatCell requests."
  - "Result-tab background assertions must scope repeatCell requests to the run tab sheetId because persistent tabs may have their own repeatCell formatting."

requirements-completed: [POLISH-01]

duration: 7min
completed: 2026-05-23
---

# Phase 06 Plan 01: AccountStatus Visual Contract + Legend Tab Summary

**Google Sheet row backgrounds now tell the AccountStatus story directly, with clean rows white/no-fill, low groundedness yellow, hook suppression orange, judge failure gray, and a persistent Legend tab explaining the palette and precedence.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-23T05:13:57Z
- **Completed:** 2026-05-23T05:21:29Z
- **Tasks:** 2
- **Files changed:** 4 (1 created, 3 modified)

## Accomplishments

- Replaced verdict-driven row coloring with `ACCOUNT_STATUS_COLORS` and `account_status_row_colors(scored)`, keyed by the four `AccountStatus` members.
- Added `LEGEND_TAB_TITLE = "Legend"` and `build_legend_rows()` with status, color, meaning, and the verbatim `STATUS_LEGEND` precedence string on every data row.
- Wired `SheetsWriter.write()` to refresh the Legend tab every run, independent of optional Rubric or Inputs kwargs, then tint all four Legend data rows from the shared palette.
- Preserved `_apply_eval_flag_text` unchanged: flagged `eval_groundedness` cells still receive bold red text, separate from the row-level status color.
- Replaced verdict-color unit tests and extended integration tests to inspect FakeService value writes and repeatCell requests by sheetId.

## Task Commits

1. **Task 1 RED: AccountStatus/Legend unit tests** - `5e56a5d` (test)
2. **Task 1 GREEN: AccountStatus palette, row tinting, and Legend tab writer** - `36bd02d` (feat)
3. **Task 2 RED: Legend and AccountStatus integration assertions** - `7f711ef` (test)
4. **Task 2 GREEN: status-aware integration fixture support** - `d3cff0e` (test)

## Palette Values

| AccountStatus | Color | RGB |
|----------------|-------|-----|
| clean | white | 1.00 / 1.00 / 1.00 |
| low_groundedness | yellow | 1.00 / 0.97 / 0.80 |
| hook_suppressed | orange | 1.00 / 0.90 / 0.78 |
| judge_failed | gray | 0.88 / 0.88 / 0.88 |

## Files Created/Modified

- `src/sheets.py` - Adds AccountStatus palette, Legend tab rows, Legend tab tinting, and rewires result row tinting away from score verdicts.
- `tests/unit/test_sheets_rows.py` - Replaces verdict-color tests with palette completeness, clean no-fill, gray judge-failure, hook-suppressed distinction, and Legend row tests.
- `tests/integration/test_sheets_writer.py` - Adds FakeService assertions for Legend refresh, Legend row values, Legend row tinting, AccountStatus-driven result-row tinting, and hook-suppressed unscoreable tinting.
- `.planning/phases/06-sheet-polish/06-01-SUMMARY.md` - Documents implementation, verification, decisions, and self-check.

## Decisions Made

- Clean rows are omitted from result-tab background requests. This keeps clean rows as the Sheet default white/no-fill while still letting the Legend clean row show explicit white.
- `judge_failed` uses true gray. This follows audit GAP-03: judge failure is an eval failure, not a content-fabrication signal.
- The Legend tab is refreshed unconditionally, even when Rubric and Inputs are not refreshed. The visual contract is static and should always be present for the viewer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale Rubric tab wording**
- **Found during:** Task 1 (AccountStatus visual contract implementation)
- **Issue:** `build_rubric_rows()` still told viewers that row color came from verdict buckets, which became false once D-01 removed verdict tinting.
- **Fix:** Reworded the Rubric tab note to say red eval text remains and whole-row background comes from AccountStatus, with the Legend tab carrying status colors and precedence.
- **Files modified:** `src/sheets.py`
- **Verification:** `uv run pytest tests/unit/test_sheets_rows.py -x`, `uv run mypy src/sheets.py`, and plan-level verification passed.
- **Committed in:** `36bd02d`

**2. [Rule 1 - Bug] Made existing writer tests Legend-aware**
- **Found during:** Task 2 (integration test extension)
- **Issue:** Existing tests assumed the first value update was always the run tab and that an existing spreadsheet only added one tab. The new persistent Legend tab legitimately changes both assumptions.
- **Fix:** Updated assertions to locate the run-tab update by title and to expect both the Legend tab and run tab addSheet calls where applicable.
- **Files modified:** `tests/integration/test_sheets_writer.py`
- **Verification:** `uv run pytest tests/integration/test_sheets_writer.py -x` and `uv run mypy src/sheets.py tests/integration/test_sheets_writer.py` passed.
- **Committed in:** `7f711ef`

---

**Total deviations:** 2 auto-fixed (Rule 1)
**Impact on plan:** Both fixes were required to keep the visible Sheet contract and tests accurate after replacing verdict tinting. No scope expansion beyond POLISH-01.

## Issues Encountered

- The plan-level grep command form `grep -nE ... src tests` printed directory warnings on this macOS environment. Re-ran it recursively as `grep -R -nE "VERDICT_COLORS|verdict_row_colors" src tests || true`, which returned zero matches.

## Known Stubs

None. Stub scan found no TODO, FIXME, placeholder, coming soon, or not available text in the modified files. Empty strings, empty lists, and empty dicts found by the scan are intentional test fixtures or Sheet blank-cell rendering paths.

## Threat Surface Scan

No new unplanned threat surface. The plan's Google Sheets outbound-write boundary is unchanged. The new Legend tab contains only static AccountStatus names, static meanings, static color labels, and the `STATUS_LEGEND` string, matching T-06-01-01 through T-06-01-03.

## TDD Gate Compliance

- Task 1 RED commit: `5e56a5d`, unit tests failed on missing `ACCOUNT_STATUS_COLORS` export.
- Task 1 GREEN commit: `36bd02d`, unit tests and `mypy src/sheets.py` passed.
- Task 2 RED commit: `7f711ef`, integration tests failed on the missing status-aware `_scored` fixture parameter.
- Task 2 GREEN commit: `d3cff0e`, integration tests and file-scoped mypy passed. This task was integration-test-only, so the GREEN commit is a test fixture support commit rather than production code.

## Verification

- `uv run pytest tests/unit/test_sheets_rows.py tests/integration/test_sheets_writer.py -x` - 23 passed
- `uv run mypy src` - Success, no issues found in 20 source files
- `uv run ruff check src/sheets.py tests/unit/test_sheets_rows.py tests/integration/test_sheets_writer.py` - All checks passed
- `uv run black --check src/sheets.py tests/unit/test_sheets_rows.py tests/integration/test_sheets_writer.py` - 3 files unchanged
- `grep -R -nE "VERDICT_COLORS|verdict_row_colors" src tests || true` - zero matches

## Self-Check: PASSED

- `src/sheets.py` exists and contains exactly one `ACCOUNT_STATUS_COLORS` definition, one `LEGEND_TAB_TITLE` definition, one `account_status_row_colors` definition, and one `build_legend_rows` definition.
- `src/sheets.py` and `tests/unit/test_sheets_rows.py` contain zero `VERDICT_COLORS` or `verdict_row_colors` references.
- `STATUS_LEGEND` appears in `src/sheets.py` at declaration and inside `build_legend_rows`.
- `LEGEND_TAB_TITLE` appears in `src/sheets.py` at declaration, the `_refresh_named_tab` call, and Legend tab color lookup.
- Task commits found in git log: `5e56a5d`, `36bd02d`, `7f711ef`, `d3cff0e`.
- All plan-level verification commands passed after task commits.

## User Setup Required

None.

## Next Phase Readiness

POLISH-01 is complete. Phase 06 Plan 02 can build the per-run Sources tab and hyperlink citations on top of the updated Sheet writer, with AccountStatus row tinting and Legend behavior already covered by unit and integration tests.

---
*Phase: 06-sheet-polish*
*Completed: 2026-05-23*
