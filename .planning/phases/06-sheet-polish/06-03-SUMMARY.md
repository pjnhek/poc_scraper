---
phase: 06-sheet-polish
plan: 03
subsystem: sheets
tags: [google-sheets, icp, headers, axis-labels, tdd]

requires:
  - phase: 06-sheet-polish
    provides: Per-run Sources tab, HYPERLINK formulas, and the 28-column results HEADERS from 06-02
provides:
  - Weight-baked display labels for the four ICP axis header cells
  - Optional config-driven row-zero projection in build_rows
  - SheetsWriter pass-through so live result tabs render labels from configs/icp.yaml
affects: [06-04-freeze-widths, phase-8-demo]

tech-stack:
  added: []
  patterns:
    - Internal HEADERS remain snake_case while build_rows projects display labels only when config is provided
    - Axis display labels are computed from ICPConfig.axes at write time

key-files:
  created:
    - .planning/phases/06-sheet-polish/06-03-SUMMARY.md
  modified:
    - src/sheets.py
    - tests/unit/test_sheets_rows.py

key-decisions:
  - "D-09 implemented with weight-baked display labels sourced from configs/icp.yaml at write time."
  - "Internal HEADERS stay snake_case so HEADERS.index lookups and width mapping remain stable."
  - "D-10 and D-11 preserved by changing only row-zero labels, not per-axis cell values or column order."

patterns-established:
  - "axis_display_labels(config) is the single helper for converting ICP axis keys and weights into display strings."
  - "build_rows stays backward-compatible by leaving row 0 as list(HEADERS) when config is omitted."

requirements-completed: [POLISH-03]

duration: 3min
completed: 2026-05-23
---

# Phase 06 Plan 03: Per-Axis Weight Labels Summary

**ICP axis headers now render their configured weights in the results tab while keeping the internal header keys stable for code and tests.**

## Performance

- **Duration:** 3min
- **Started:** 2026-05-23T05:41:55Z
- **Completed:** 2026-05-23T05:45:06Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `axis_display_labels(config)` to derive the four axis labels from `ICPConfig.axes`.
- Extended `build_rows` with optional `config` projection for row 0 only.
- Wired `SheetsWriter.write` to pass its existing `config` into `build_rows`.
- Added unit coverage for configured weights, rounded percentages, no-config behavior, axis-only replacement, and the locked four-axis key set.

## Axis Labels Emitted

From the current `configs/icp.yaml`, `axis_display_labels(get_config())` emits:

```python
{
    "support_volume": "Support Volume (40%)",
    "ai_maturity": "AI Maturity (30%)",
    "stage_fit": "Stage Fit (20%)",
    "channel_breadth": "Channel Breadth (10%)",
}
```

`HEADERS` still contains `support_volume`, `ai_maturity`, `stage_fit`, and `channel_breadth` at the same positions. When `config` is provided, only those row-zero cells are replaced with display labels. Non-axis cells such as `domain` and `icp_total` remain snake_case.

## Task Commits

The TDD task was committed through RED then GREEN:

1. **Task 1 RED: Axis display label tests** - `0051231` (test)
2. **Task 1 GREEN: Axis display label implementation** - `518782c` (feat)

## Files Created/Modified

- `src/sheets.py` - Adds `axis_display_labels`, optional `config` support in `build_rows`, and `SheetsWriter.write` pass-through.
- `tests/unit/test_sheets_rows.py` - Covers helper output, rounded integer percentages, row-zero projection, no-config headers, and the four-key axis set.

## Decisions Made

- Kept `AI` uppercase in `AI Maturity` to match the required display label and the project-facing acronym.
- Used `round(axis.weight * 100)` for bare integer percentages, matching D-09.
- Kept per-axis score cells unchanged as raw 1-5 values, with no added formatting.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- The RED commit initially triggered the black pre-commit hook, which reformatted the new test helper. The file was restaged and committed with hooks passing.

## User Setup Required

None - no external service configuration required.

## Checks Run

- `uv run pytest tests/unit/test_sheets_rows.py -x` - passed, 25 tests.
- `uv run mypy src/sheets.py` - passed.
- `uv run ruff check src/sheets.py tests/unit/test_sheets_rows.py` - passed.
- `uv run black --check src/sheets.py tests/unit/test_sheets_rows.py` - passed.
- `uv run python -c "from src.sheets import axis_display_labels; from src.icp_config import get_config; labels = axis_display_labels(get_config()); assert labels['support_volume'] == 'Support Volume (40%)', labels; print('ok')"` - printed `ok`.
- `uv run python -c "from src.sheets import HEADERS, build_rows; from src.icp_config import get_config; rows = build_rows([], config=get_config()); assert rows[0][HEADERS.index('support_volume')] == 'Support Volume (40%)'; assert rows[0][HEADERS.index('domain')] == 'domain'; print('ok')"` - printed `ok`.
- Grep acceptance checks for `axis_display_labels`, `config: ICPConfig | None = None`, and helper call sites - passed.

## Known Stubs

None. Stub scan found no TODO, FIXME, placeholder, coming soon, or not available text in the modified files.

## Authentication Gates

None.

## Next Phase Readiness

Plan 04 can apply freeze panes and width classes against the same 28-entry `HEADERS` tuple. It should key width mappings to the snake_case axis names, while row 0 in live Sheets will show the display labels above.

## Self-Check: PASSED

- Summary file path prepared: `.planning/phases/06-sheet-polish/06-03-SUMMARY.md`
- Required TDD commits found in `git log`: `0051231`, `518782c`
- Key files exist: `src/sheets.py` and `tests/unit/test_sheets_rows.py`
- No untracked plan artifacts remain; root `AGENTS.md` is intentionally untracked project guidance and was not staged.

---
*Phase: 06-sheet-polish*
*Completed: 2026-05-23*
