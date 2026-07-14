---
quick_id: 260714-mrg
type: quick
status: complete
completed: 2026-07-14
files_modified:
  - src/sheets.py
commit: 6f8be41
---

# Quick 260714-mrg: Fix Rubric tab — add specificity and recency rows

## What changed

`build_rubric_rows()` in `src/sheets.py` previously documented only three of the
five judge dimensions in the human-readable Rubric tab (groundedness,
icp_relevance, personalization). The Results tab renders all five columns
(including eval_specificity and eval_recency), so the Rubric tab contradicted the
Results columns two tabs over.

Added two new rows immediately after the `personalization` row block, using the
same list-of-two-strings shape as the existing judge-rubric rows:

- `specificity`: "1-5 categorical: 1 = generic claim that could apply to any company, 5 = highly specific facts unique to this account."
- `recency`: "1-5 categorical: 1 = no recent evidence cited, 5 = multiple recent-news citations."

The wording mirrors the judge prompt in `evals/rubric.py:39-42` so the Rubric tab
and the judge stay in sync. `black` reformatted the recency continuation onto a
single line (implicit string concatenation); the assembled text is unchanged.

## Tests

No test asserted the exact judge-rubric row set (the existing
`tests/unit/test_sheets_rubric.py` only checks `config.axes`, the writer axes, not
the judge axes), so no test update was needed. The trivial change did not warrant a
new test.

## Verify block outputs

- `uv run python -m pytest tests -k sheets -q`: PASS — `60 passed, 262 deselected in 91.26s`
  (the `uv run pytest` shorthand hit a stale venv shebang; `uv run python -m pytest` was used).
- `uv run python -m ruff check src/sheets.py`: PASS — `All checks passed!`
- `uv run python -m black --check src/sheets.py`: PASS — `1 file would be left unchanged` (after applying black).
- `uv run python -m mypy src/sheets.py`: PASS — `Success: no issues found in 1 source file`
- Sanity one-liner (`specificity` and `recency` present in flattened rows): PASS — `sanity ok`

## Commit

`6f8be41` fix(sheets): document specificity and recency in judge rubric tab
(committed with pre-commit hooks enabled, no --no-verify; src/sheets.py only).

## Self-Check: PASSED

- `src/sheets.py` exists and contains the new rows (sanity check confirmed).
- Commit `6f8be41` present in git history.
