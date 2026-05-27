---
phase: 07-public-repo-audit
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scripts/verify_public_repo.py
  - Makefile
  - tests/unit/test_check_public_discipline.py
  - README.md
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-27
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 7 adds a re-runnable public-repo audit script (`scripts/verify_public_repo.py`), a `verify-public-repo` Makefile target, parametrized unit-tests for the pre-existing pre-commit guard (`tests/unit/test_check_public_discipline.py`), and a "Local setup" subsection in `README.md` documenting how to recreate `.secrets-denylist`.

All four files pass `black --check`, `ruff check`, and `mypy --strict`. The new test file passes (`pytest tests/unit/test_check_public_discipline.py` -> 3 passed). The test file correctly uses `FAKE_TERM = "fake-denylisted-term-for-test"` and contains no real vendor names. The README's new section uses no em-dashes (existing em-dashes elsewhere in README are pre-existing and out of phase scope). The Makefile target is correctly added to `.PHONY`.

The findings below cluster on three themes: (1) silent failure modes in the new audit script when git subprocess invocations fail (the script reports "0 hits" instead of surfacing that no scan was performed), (2) a latent crash if `.secrets-denylist` contains a malformed regex line (`re.compile` is uncaught in both the new script and the pre-existing guard), and (3) the new tests do not exercise denylist edge cases (empty file, comment-only file, bad regex), leaving the `_load_patterns` branches uncovered despite Phase 7's stated goal of hardening that surface.

## Warnings

### WR-01: Silent failure when `git log` / `git ls-files` returncode is non-zero

**File:** `scripts/verify_public_repo.py:54-55, 80-81`
**Issue:** Both `_scan_worktree` and `_scan_history` swallow non-zero subprocess returncode and return `0`. If the script is run outside a git work tree, against a bare repo, or `git log --all -p` hits any failure (e.g., a corrupt pack), the operator sees a clean `0 hits in tracked content, 0 hits in history` summary and process exit code `0`. From the audit contract's perspective this is a false-negative: the operator believes the repo is clean, but in fact no scan ran. This contradicts the docstring's explicit framing ("verification is an explicit operator action with stakes-laden output; silence on missing configuration would defeat the audit").

**Fix:** Surface subprocess failure as an error, mirroring how the missing-denylist case is handled.
```python
def _scan_worktree(patterns: list[re.Pattern[str]]) -> int:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git ls-files failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    ...
```
Catch `RuntimeError` in `main()` and return exit code `2` with a stderr message, matching the missing-denylist failure mode.

### WR-02: Malformed regex in `.secrets-denylist` crashes both the audit script and the pre-commit hook

**File:** `scripts/verify_public_repo.py:43`, `scripts/check_public_discipline.py:29`
**Issue:** `_load_patterns` calls `re.compile(line, re.IGNORECASE)` without any error handling. If an operator adds an invalid regex line to `.secrets-denylist` (e.g., an unbalanced paren like `Acme(Corp`), the call raises `re.error` and crashes both the audit script and every subsequent commit (because the pre-commit hook runs on every commit). This contradicts the project's documented philosophy of graceful degradation in operator-facing tooling, and the pre-commit guard's docstring explicitly states "if that file is absent... the check passes silently rather than breaking unrelated commits" - the same logic should extend to malformed lines.

**Fix:** Catch `re.error` per line, log a warning to stderr naming the offending line number, and skip it.
```python
for lineno, raw in enumerate(DENYLIST.read_text(encoding="utf-8").splitlines(), start=1):
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    try:
        patterns.append(re.compile(line, re.IGNORECASE))
    except re.error as exc:
        sys.stderr.write(
            f"{DENYLIST.name}: skipping malformed regex on line {lineno}: {exc}\n"
        )
```

### WR-03: Double-counting when a denylist pattern matches both content and path of the same file

**File:** `scripts/verify_public_repo.py:67-69`
**Issue:** Inside `_scan_worktree`, each file contributes `pat.findall(content) + pat.findall(path)` hits. A file whose name *and* body both reference a denylisted term counts at minimum 2 hits, and the printed summary says `"{n} hits in tracked content"` - but `n` mixes content occurrences and path occurrences in the same counter, which the label "tracked content" does not advertise. An operator inspecting the count cannot tell whether `2` means "two files with content hits" or "one file with one content hit and one path hit". For a tool whose summary is the only safe output channel (no raw match text), the count's meaning is the entire interface.

**Fix:** Either split the counters and report both, or rename the summary string. Splitting is more informative:
```python
def _scan_worktree(patterns: list[re.Pattern[str]]) -> tuple[int, int]:
    content_hits = 0
    path_hits = 0
    ...
    for pat in patterns:
        content_hits += len(pat.findall(content))
        path_hits += len(pat.findall(path))
    return content_hits, path_hits
```
And update the summary line to report each.

### WR-04: New tests do not cover `_load_patterns` edge cases (empty file, comment-only file, bad regex)

**File:** `tests/unit/test_check_public_discipline.py`
**Issue:** The Phase 7 brief states the new tests cover "content-match and path-match branches of `scripts/check_public_discipline.py`". Per CLAUDE.md ("Well-tested is non-negotiable. Err on the side of too many tests rather than too few"), the additional branches in `_load_patterns` should also be tested:
- Denylist file containing only comments / blank lines -> `patterns = []` -> `main` returns 0 (current behavior, but untested).
- Denylist file with a malformed regex line - currently raises uncaught `re.error` (see WR-02), which silently rides under the radar because no test exists.
- `_staged_content` returning empty string for a deleted-from-index path (e.g., `git show :path` fails) - relies on `result.stdout if returncode == 0 else ""`, untested.

**Fix:** Add three more parametrized cases or three discrete tests covering each branch. The comment-only / empty-file case is one line; the bad-regex case will fail today and become the regression test for WR-02 once fixed.

## Info

### IN-01: Test does not assert the format of the violation message written to stderr

**File:** `tests/unit/test_check_public_discipline.py:48`
**Issue:** Both branches assert only `mod.main([str(fixture)]) == expected` (return code). The pre-commit guard's stderr output (`public-repo-discipline check failed; staged changes contain denylisted terms:\n  {path}: matches /{pat.pattern}/i`) is a human-facing contract used by the operator to triage. A regression that drops the path or the pattern from the message would pass the test. Recommend asserting via `capsys.readouterr().err` that both the file path and the regex are present in the failure message.

**Fix:**
```python
def test_main_flags_violations(..., capsys: pytest.CaptureFixture[str]) -> None:
    ...
    assert mod.main([str(fixture)]) == expected
    err = capsys.readouterr().err
    assert str(fixture) in err
    assert FAKE_TERM in err
```

### IN-02: `DENYLIST` path resolution is layout-coupled and undocumented

**File:** `scripts/verify_public_repo.py:32`, `scripts/check_public_discipline.py:18`
**Issue:** `Path(__file__).resolve().parent.parent / ".secrets-denylist"` silently assumes the script lives exactly one directory below the repo root. If the script is moved or vendored, the resolution silently points at the wrong directory and the audit becomes a no-op (after fixing WR-01) or a crash. A one-line comment naming the contract ("# Resolves to `<repo_root>/.secrets-denylist`; both scripts must stay one directory below the repo root.") would make the coupling explicit; alternatively, walk upward looking for a sentinel like `.git`.

**Fix:** Add a comment, or make the lookup more robust:
```python
def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("verify-public-repo: not inside a git work tree")

DENYLIST = _find_repo_root(Path(__file__).resolve()) / ".secrets-denylist"
```

---

_Reviewed: 2026-05-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
