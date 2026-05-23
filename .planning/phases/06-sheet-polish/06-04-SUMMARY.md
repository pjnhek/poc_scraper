---
phase: 06-sheet-polish
plan: 04
subsystem: sheets
tags: [google-sheets, freeze-panes, column-widths, wrap-strategy, tdd]

requires:
  - phase: 06-sheet-polish
    provides: 28-column HEADERS, axis display labels, per-run Sources tab, Legend tab from plans 01-03
provides:
  - WIDTH_CLASS_PX and COLUMN_WIDTHS as the DRY single source of truth for D-13
  - SheetsWriter._apply_freeze_panes, _apply_column_widths, _apply_wrap_strategy helpers
  - Integration coverage for freeze, width, and wrap batchUpdate request shapes
affects: [phase-08-readme-and-loom]

tech-stack:
  added: []
  patterns:
    - Single _lookup_sheet_id call powers freeze + widths + wrap so the writer stays gentle on the discovery API
    - WIDTH_CLASS_PX and COLUMN_WIDTHS sit at module level and feed both the writer and the test invariants
    - WRAP_COLUMN_NAMES locks the wrap set to hook_1, hook_2, hook_3, justification so future header edits do not silently widen the scope

key-files:
  created:
    - .planning/phases/06-sheet-polish/06-04-SUMMARY.md
  modified:
    - src/sheets.py
    - tests/unit/test_sheets_rows.py
    - tests/integration/test_sheets_writer.py

key-decisions:
  - "D-12 implemented as a single updateSheetProperties request with frozenRowCount=1 and frozenColumnCount=2 on the results tab only."
  - "D-13 issues one updateDimensionProperties request per HEADERS entry (28 requests) in a single batchUpdate; per-class collapsing deferred as a future optimization."
  - "D-14 issues four repeatCell wrap requests scoped to hook_1, hook_2, hook_3, and justification data ranges."
  - "All three formatting passes share one _lookup_sheet_id call after _apply_eval_flag_text so they bind to the final shape of the tab."

patterns-established:
  - "Module-level WIDTH_CLASS_PX and COLUMN_WIDTHS dicts: tests assert set equality with HEADERS as the DRY-coverage gate."
  - "Each _apply_* helper receives sheet_id as a parameter instead of re-resolving it, keeping API chatter low."
  - "Empty scored list still issues all formatting requests so a future-added row inherits the formatting on subsequent runs."

requirements-completed: [POLISH-04]

duration: 5min
completed: 2026-05-23
---

# Phase 06 Plan 04: Freeze Panes, Column Widths, and Wrap Strategy Summary

**The results tab now opens with row 1 and columns A-B frozen, every column sized to its width class, and hook plus justification cells wrapping so multi-sentence paragraphs read inside the cell on first open.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-23T05:53:21Z
- **Completed:** 2026-05-23T05:58:00Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Added `WIDTH_CLASS_PX = {narrow: 110, medium: 180, wide: 400, extra: 250}` as the single pixel-class source.
- Added `COLUMN_WIDTHS` covering all 28 HEADERS entries with exactly one class each.
- Added `WRAP_COLUMN_NAMES` to lock the wrap set to hook_1, hook_2, hook_3, justification.
- Added `_apply_freeze_panes`, `_apply_column_widths`, `_apply_wrap_strategy` on `SheetsWriter`.
- Wired all three helpers into `SheetsWriter.write` after `_apply_eval_flag_text`, sharing a single `_lookup_sheet_id` call.
- Added 4 unit tests covering COLUMN_WIDTHS coverage, WIDTH_CLASS_PX values, allowed class names, and D-13 class assignment per header.
- Added 5 integration tests covering the three batchUpdate request shapes via FakeService inspection plus the empty-scored guard.

## COLUMN_WIDTHS Mapping (final)

| Column                | Class  | Pixels |
| --------------------- | ------ | ------ |
| domain                | narrow | 110    |
| status                | narrow | 110    |
| name                  | medium | 180    |
| industry              | medium | 180    |
| headcount             | medium | 180    |
| tech_signals          | medium | 180    |
| icp_total             | narrow | 110    |
| verdict               | narrow | 110    |
| support_volume        | narrow | 110    |
| ai_maturity           | narrow | 110    |
| stage_fit             | narrow | 110    |
| channel_breadth       | narrow | 110    |
| justification         | wide   | 400    |
| contact_1_role        | medium | 180    |
| contact_1_rationale   | medium | 180    |
| hook_1                | wide   | 400    |
| contact_2_role        | medium | 180    |
| contact_2_rationale   | medium | 180    |
| hook_2                | wide   | 400    |
| contact_3_role        | medium | 180    |
| contact_3_rationale   | medium | 180    |
| hook_3                | wide   | 400    |
| eval_groundedness     | narrow | 110    |
| eval_icp_relevance    | narrow | 110    |
| eval_personalization  | narrow | 110    |
| eval_specificity      | narrow | 110    |
| eval_recency          | narrow | 110    |
| error                 | extra  | 250    |

Total: 13 narrow + 10 medium + 4 wide + 1 extra = 28 entries, matching the 28-entry HEADERS tuple.

## WIDTH_CLASS_PX Pixel Values

```python
{"narrow": 110, "medium": 180, "wide": 400, "extra": 250}
```

These sit inside the D-13 documented ranges (narrow 100-120, medium 180, wide 400, extra 250).

## Task Commits

Each TDD task was committed through RED then GREEN:

1. **Task 1 RED: COLUMN_WIDTHS coverage tests** - `983caee` (test)
2. **Task 1 GREEN: WIDTH_CLASS_PX, COLUMN_WIDTHS, three batchUpdate helpers wired into writer** - `b23e8f3` (feat)
3. **Task 2: integration tests for freeze, widths, wrap, empty-scored** - `3dac1ed` (test)

Task 2 is test-only since the implementation already shipped in Task 1; the integration tests pin the request shapes at the writer boundary.

## Files Created/Modified

- `src/sheets.py` - Adds WIDTH_CLASS_PX, COLUMN_WIDTHS, WRAP_COLUMN_NAMES, three private helpers on SheetsWriter, and wires them into SheetsWriter.write after the eval flag pass.
- `tests/unit/test_sheets_rows.py` - Adds four unit tests for the new mappings: pixel value lock, HEADERS coverage, allowed class names, and D-13 class assignment per header.
- `tests/integration/test_sheets_writer.py` - Adds five tests: COLUMN_WIDTHS-covers-HEADERS invariant, freeze panes on results tab, per-column widths match class mapping, wrap strategy on hook + justification, and empty-scored graceful path.
- `.planning/phases/06-sheet-polish/06-04-SUMMARY.md` - Documents implementation, mapping, decisions, verification, and self-check.

## Decisions Made

- Pixel values 110 / 180 / 400 / 250 picked inside the D-13 ranges. 110 keeps narrow numeric columns scannable; 400 lets wrapped hook paragraphs render multi-sentence prose without horizontal scroll.
- icp_total and verdict treated as narrow per the plan's spirit of "headline-first, narrow numeric columns" (D-13 does not explicitly classify them).
- Each helper receives `sheet_id` as a parameter so the writer issues exactly one `_lookup_sheet_id` call for all three formatting passes.
- Empty scored list still issues all three formatting requests so a future-added row inherits the formatting on subsequent runs. The empty wrap range (startRowIndex=1, endRowIndex=1) is a no-op the Sheets API tolerates.
- Per-class width collapsing (one updateDimensionProperties request per contiguous same-class run) deferred as a future bytes-savings optimization; 28 requests sit far under the Sheets per-batchUpdate limit.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0.
**Impact on plan:** No scope change.

## Issues Encountered

- The first run of `black --check` flagged the integration test file. `uv run black` reformatted it, all tests stayed green, and `black --check` ran clean afterwards.

## User Setup Required

None - no external service configuration required.

## Checks Run

- `uv run pytest tests/unit tests/integration -x` - 244 passed.
- `uv run mypy src` - Success, no issues found in 20 source files.
- `uv run mypy src tests/integration/test_sheets_writer.py` - Success, no issues found in 21 source files.
- `uv run ruff check src tests` - All checks passed.
- `uv run black --check src tests` - 58 files unchanged.
- `uv run python -c "from src.sheets import HEADERS, COLUMN_WIDTHS, WIDTH_CLASS_PX; assert set(COLUMN_WIDTHS.keys()) == set(HEADERS); assert set(COLUMN_WIDTHS.values()).issubset(set(WIDTH_CLASS_PX.keys())); assert WIDTH_CLASS_PX == {'narrow': 110, 'medium': 180, 'wide': 400, 'extra': 250}; print('ok')"` - printed `ok`.
- `uv run python -c "from src.sheets import COLUMN_WIDTHS; assert COLUMN_WIDTHS['hook_1'] == 'wide'; assert COLUMN_WIDTHS['justification'] == 'wide'; assert COLUMN_WIDTHS['error'] == 'extra'; assert COLUMN_WIDTHS['support_volume'] == 'narrow'; assert COLUMN_WIDTHS['name'] == 'medium'; print('ok')"` - printed `ok`.
- `grep -nE "^WIDTH_CLASS_PX|^COLUMN_WIDTHS" src/sheets.py` - 2 matches.
- `grep -nE "^    def _apply_freeze_panes|^    def _apply_column_widths|^    def _apply_wrap_strategy" src/sheets.py` - 3 matches.
- `grep -n "frozenRowCount\|frozenColumnCount" src/sheets.py` - matches inside `_apply_freeze_panes`.
- `grep -n "wrapStrategy" src/sheets.py` - matches the literal `"WRAP"` and the `userEnteredFormat.wrapStrategy` fields mask.
- `grep -nE "test_column_widths_covers_every_header|test_results_tab_gets_frozen_row_and_two_frozen_columns|test_results_tab_column_widths_match_class_mapping|test_hook_and_justification_columns_get_wrap_strategy|test_freeze_and_width_and_wrap_skipped_on_empty_scored_list" tests/integration/test_sheets_writer.py` - 5 matches.

## Known Stubs

None. Stub scan found no TODO, FIXME, placeholder, coming soon, or not available text in the modified files.

## Threat Surface Scan

No new unplanned threat surface. The plan's Google Sheets outbound-write boundary is unchanged. Width, freeze, and wrap requests contain only integer parameters (sheetId, pixelSize, column indices, row indices) plus the literal string "WRAP". No untrusted input crosses the boundary. T-06-04-01 (COLUMN_WIDTHS-HEADERS coverage drift) is mitigated by `test_column_widths_covers_every_header` and `test_column_widths_covers_every_header_exactly_once`.

## TDD Gate Compliance

- Task 1 RED commit: `983caee`, unit tests failed on missing `COLUMN_WIDTHS` and `WIDTH_CLASS_PX` imports.
- Task 1 GREEN commit: `b23e8f3`, all unit and integration tests passed, mypy strict satisfied.
- Task 2 commit: `3dac1ed`, integration tests for the three batchUpdate shapes passed at first run because Task 1 already shipped the implementation; this is the expected sequence for a test-only follow-up task on top of a TDD predecessor.

## Authentication Gates

None.

## Next Phase Readiness

POLISH-04 is complete. The Sheet writer now ships with the full sheet-polish package (POLISH-01 through POLISH-04). Phase 7 (public-repo audit) and Phase 8 (README and Loom) can proceed knowing that the demo Sheet renders cleanly on first open without manual resizing or scrolling.

## Self-Check: PASSED

- `src/sheets.py` exists and contains exactly one `WIDTH_CLASS_PX` declaration and one `COLUMN_WIDTHS` declaration.
- `src/sheets.py` contains `_apply_freeze_panes`, `_apply_column_widths`, `_apply_wrap_strategy` methods on `SheetsWriter`.
- `tests/integration/test_sheets_writer.py` contains all five named tests from the plan.
- `tests/unit/test_sheets_rows.py` contains four unit tests for the new mappings.
- Task commits found in git log: `983caee`, `b23e8f3`, `3dac1ed`.
- `.planning/phases/06-sheet-polish/06-04-SUMMARY.md` written.

---
*Phase: 06-sheet-polish*
*Completed: 2026-05-23*
