---
phase: 07-public-repo-audit
plan: 02
subsystem: testing
tags: [pytest, parametrize, monkeypatch, pre-commit, public-repo-discipline]

requires:
  - phase: 07-public-repo-audit
    provides: existing pre-commit guard at scripts/check_public_discipline.py (since 2026-05-14)
provides:
  - CI-runnable unit-test coverage of both match branches of the public-discipline guard's main() function
  - Tmp-file + monkeypatch pattern that lets the test run identically on a fresh clone with no .secrets-denylist present
  - Happy-path regression guard against future "always-flag" code changes
affects: [07-03-public-repo-audit-close]

tech-stack:
  added: []
  patterns:
    - "monkeypatch.setattr(mod, 'DENYLIST', tmp_path / '.secrets-denylist') for CI-safe denylist patching"
    - "monkeypatch.setattr(mod, '_staged_content', lambda p: body if p == str(fixture) else '') to bypass the git-show subprocess seam in unit tests"
    - "FAKE_TERM = 'fake-denylisted-term-for-test' as the publishable placeholder so the live denylisted term never enters test source"

key-files:
  created:
    - tests/unit/test_check_public_discipline.py
  modified: []

key-decisions:
  - "Used 'fake-denylisted-term-for-test' verbatim per CONTEXT.md D-05 / THR-02 publishability requirement"
  - "Patched _staged_content directly rather than refactoring main() to take a content-provider callable (PATTERNS.md option a, lower-risk for two test cases)"
  - "Added a third happy-path test (D-Claude's-Discretion within CLAUDE.md 'err on the side of too many tests' convention) to lock zero-violation behavior against future regressions"
  - "Did not test the missing-denylist no-op branch per D-06 (acceptable as untested; returns 0 silently by design)"

patterns-established:
  - "Pattern: tmp-file + module-constant monkeypatch for testing scripts that read gitignored config files"
  - "Pattern: patch the subprocess-shelling seam (_staged_content) when unit-testing functions that would otherwise need a real git-staged fixture"

requirements-completed: [REPO-04]

duration: 1min
completed: 2026-05-27
---

# Phase 7 Plan 2: Pre-Commit Guard Unit Test Summary

**Parametrized pytest coverage for scripts/check_public_discipline.py:main() over content-match and path-match branches, plus a happy-path regression guard, all isolated from the real local `.secrets-denylist` via tmp-file monkeypatching**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-27T17:26:02Z
- **Completed:** 2026-05-27T17:27:09Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Locked the content-match branch of `if pat.search(content) or pat.search(path)` at scripts/check_public_discipline.py:53 (parametrize case id `content-match`).
- Locked the path-match branch of the same expression (parametrize case id `path-match`).
- Added a happy-path test `test_main_returns_zero_when_no_denylist_terms_match` to guard against future regressions where a code change accidentally always-flags.
- Verified the full offline suite (306 tests) still passes with the new tests included.

## Task Commits

1. **Task 1: Write tests/unit/test_check_public_discipline.py with content-match + path-match parametrized cases** - `c8160ef` (test)

## Files Created/Modified

- `tests/unit/test_check_public_discipline.py` - Three tests covering main(): two parametrized cases (`content-match`, `path-match`) plus a happy-path test. Uses `FAKE_TERM = "fake-denylisted-term-for-test"` and patches both `DENYLIST` and `_staged_content` to isolate the test from `.secrets-denylist` and from real git.

## Decisions Made

- Patched `_staged_content` directly rather than refactoring `main()` to take a content-provider callable. PATTERNS.md flagged both options; the patch is two lines and avoids touching production code for a unit-test concern.
- Added the third happy-path test as cheap insurance against false-positive regressions, consistent with CLAUDE.md "err on the side of too many tests rather than too few."
- Skipped the missing-denylist no-op branch per CONTEXT.md D-06.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Verification Results

- `uv run pytest tests/unit/test_check_public_discipline.py -v`: 3 passed in 0.02s.
- `uv run pytest tests/unit/test_check_public_discipline.py --collect-only`: test ids include `[content-match-...]` and `[path-match-...]`.
- `uv run pytest -m "not smoke"`: 306 passed, 2 deselected in 10.93s (full offline suite, new tests included).
- `uv run ruff check tests/unit/test_check_public_discipline.py`: All checks passed.
- `uv run black --check tests/unit/test_check_public_discipline.py`: 1 file would be left unchanged.
- `uv run python -c "import tests.unit.test_check_public_discipline"`: import OK, no SyntaxError.
- Denylist-driven safety grep loop (per CONTEXT.md W3 / D-06 acceptance criterion): SAFETY GREP CLEAN. No `.secrets-denylist` pattern matches the test file.
- Pre-commit hooks on the task commit: black, ruff, trailing-whitespace, end-of-file-fixer, public-repo-discipline all passed.

## Next Phase Readiness

- REPO-04's "proof the guard works" half is closed. Plan 07-03 (the atomic close) can now flip REPO-04 from Pending to Complete with this commit (`c8160ef`) cited as evidence.
- No blockers.

## Self-Check: PASSED

- FOUND: tests/unit/test_check_public_discipline.py
- FOUND commit: c8160ef

---
*Phase: 07-public-repo-audit*
*Completed: 2026-05-27*
