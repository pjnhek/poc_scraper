---
phase: 07-public-repo-audit
plan: 01
subsystem: public-repo-audit
tags: [verification, audit, scripts, makefile]
requires:
  - .secrets-denylist (gitignored, local-only; same source the pre-commit guard uses)
  - git history (full clone; the script's `git log --all -p` pass cannot run on a shallow checkout)
provides:
  - scripts/verify_public_repo.py (re-runnable audit script, stdlib only, strict-mypy clean)
  - Makefile target `verify-public-repo` (operator-triggered, not in CI)
affects:
  - REPO-01 (verification surface formalized; pre-Phase-8 sign-off enabled)
  - REPO-03 (re-runnable proof the rewrite remains clean)
tech-stack:
  added: []
  patterns:
    - "scripts/check_public_discipline.py shape (DENYLIST resolution + `_load_patterns()` verbatim + subprocess.run pattern)"
    - "Makefile one-line `uv run python -m scripts.<name>` wrapper (mirrors setup-sheet, eval-report)"
key-files:
  created:
    - scripts/verify_public_repo.py
  modified:
    - Makefile
decisions:
  - "Exit codes: 0 = clean (0 hits worktree + 0 hits history), 1 = at least one occurrence found, 2 = denylist missing or empty (D-Claude's-Discretion per CONTEXT.md)."
  - "Duplicated `_load_patterns()` verbatim rather than extracting to scripts/_denylist.py; the helper is 9 lines and CONTEXT.md `<deferred>` says the consolidation is not Phase 7's call."
  - "Worktree pass uses `Path(path).read_text(encoding=\"utf-8\", errors=\"replace\")` + `pat.findall` (stdlib only) instead of ripgrep, per PATTERNS.md note that the project does not carry rg as a dependency."
  - "History pass iterates `result.stdout.splitlines()` in-process; CONTEXT.md T-07-03 accepts the memory cost because the operator runs this rarely."
  - "Single stdout `print(` call locked by the I3 grep acceptance gate to enforce THR-01 (no raw match text under any code path)."
metrics:
  duration: 2m
  completed: 2026-05-27T17:23:00Z
---

# Phase 7 Plan 1: verify-public-repo Script and Makefile Target Summary

One-line: Re-runnable public-repo audit shipped as `scripts/verify_public_repo.py` + `make verify-public-repo`, reading patterns from the gitignored `.secrets-denylist`, scanning both the worktree and `git log --all -p`, emitting one summary line with counts plus HEAD SHA (never raw matches), and exiting 2 with a clear setup message when the denylist is absent.

## What Shipped

**`scripts/verify_public_repo.py`** (new, 136 lines):
- Module docstring mirrors `scripts/check_public_discipline.py` framing (purpose, denylist-file framing, missing-denylist asymmetry vs the pre-commit guard, usage line).
- `DENYLIST = Path(__file__).resolve().parent.parent / ".secrets-denylist"` (cwd-independent).
- `_load_patterns() -> list[re.Pattern[str]]` copied verbatim from the analog; case-insensitive regex per line, blank and `#`-comment lines skipped.
- `_scan_worktree(patterns) -> int`: shells `git ls-files`, skips `.secrets-denylist` per D-03, reads each tracked text file with `errors="replace"`, increments by `len(pat.findall(content)) + len(pat.findall(path))` (true occurrence counts per I2).
- `_scan_history(patterns) -> int`: shells `git log --all -p`, iterates lines, sums `len(pat.findall(line))` for every compiled pattern.
- `_head_sha() -> str`: shells `git rev-parse --short HEAD`, falls back to the literal `"unknown"` if empty.
- `main() -> int`: missing denylist returns 2 with stderr setup prompt; empty denylist returns 2; otherwise prints one summary line and returns 0 (clean) or 1 (hits found) with a non-revealing stderr remediation hint.
- Entry point: `if __name__ == "__main__": raise SystemExit(main())`.

**`Makefile`** (modified, two surgical edits):
- `.PHONY` line extended with ` verify-public-repo`.
- New target block appended after `clean:`:
  ```
  verify-public-repo:
      uv run python -m scripts.verify_public_repo
  ```

## Verification Gates

| Gate | Result |
|------|--------|
| `uv run mypy scripts/verify_public_repo.py` | Success: no issues found in 1 source file |
| `uv run ruff check scripts/verify_public_repo.py` | All checks passed |
| `uv run black --check scripts/verify_public_repo.py` | 1 file would be left unchanged |
| `grep -c 'print(' scripts/verify_public_repo.py` | 1 (I3 / THR-01 single-emit invariant locked) |
| `grep -c -- '--verbose' scripts/verify_public_repo.py` | 0 (no stale flag breadcrumb per W4) |
| `grep -c 'poc_scraper-FULL-BACKUP' scripts/verify_public_repo.py` | 0 (D-17 scan boundary respected) |
| `uv run python -m scripts.verify_public_repo` (denylist present) | exit 0, stdout `verify-public-repo: 0 hits in tracked content, 0 hits in history reachable from any ref (commit 917b6e6).` |
| Missing-denylist branch (DENYLIST monkeypatched to `/nonexistent-denylist`) | exit 2, clear stderr setup message |
| `make -n verify-public-repo` | prints `uv run python -m scripts.verify_public_repo`, exits 0 |
| `make verify-public-repo` (final, after both commits) | exit 0, summary line cites commit `3983473` |

## Acceptance Criteria Met

Task 1:
- Script exists, starts with `from __future__ import annotations`, contains the canonical `DENYLIST` resolution, `_load_patterns()` signature, `main() -> int`, entry-point guard.
- Worktree pass uses `git ls-files` subprocess.run; history pass uses `git log --all -p` subprocess.run.
- Worktree pass calls `pat.findall(...)` on both content and path (true occurrence counts per I2).
- `.secrets-denylist` skip branch present in worktree loop (D-03).
- No `--verbose`, no bundle reference, exactly one `print(` call.
- Clean run returns 0 with the regex-matched summary line; missing-denylist returns 2 with stderr setup message.
- Strict mypy clean.

Task 2:
- `.PHONY` extended with `verify-public-repo` on the same line (minimal diff).
- New target block at end of file using a literal TAB for the recipe.
- `make -n verify-public-repo` dry-runs cleanly; `make verify-public-repo` runs the script and exits 0 (not 2).
- No other Makefile target was modified.

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Task | Hash    | Type  | Message                                                          |
| ---- | ------- | ----- | ---------------------------------------------------------------- |
| 1    | 917b6e6 | feat  | feat(07-01): add scripts/verify_public_repo.py for re-runnable audit |
| 2    | 3983473 | chore | chore(07-01): add verify-public-repo Makefile target             |

## Threat Model Reconciliation

| Threat ID | Disposition | Realized? |
|-----------|-------------|-----------|
| T-07-01 (Information Disclosure, stdout/stderr) | mitigate | Yes. Exactly one `print(` call in source (I3 grep gate); stderr messages contain setup prompts and a no-paste reminder only; no raw match text under any code path. |
| T-07-02 (Tampering, denylist source-of-truth) | mitigate | Yes. Script reads only `.secrets-denylist` via the shared `Path(__file__).resolve().parent.parent / ".secrets-denylist"` resolution; missing or empty denylist returns 2 with stderr prompt. |
| T-07-03 (DoS, git log size) | accept | Acceptable. In-process iteration; rare operator-triggered invocation. |
| T-07-04 (Information Disclosure, external bundle) | accept | Acceptable. Script intentionally knows nothing about `../poc_scraper-FULL-BACKUP.bundle`; scan boundary is the current repo only (D-17). |

No new threat surface introduced beyond the planned mitigations.

## Known Stubs

None. The script is fully wired end-to-end (worktree + history scan, summary emission, exit-code branching).

## Self-Check: PASSED

- File present: `scripts/verify_public_repo.py` -> FOUND
- File present: `Makefile` -> FOUND (modified)
- Commit present: `917b6e6` -> FOUND
- Commit present: `3983473` -> FOUND
- `make verify-public-repo` runs to completion with exit 0 and emits one summary line.
- Strict mypy, ruff, black all clean.
