---
phase: 07-public-repo-audit
verified: 2026-05-27T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 7: Public-Repo Audit Verification Report

**Phase Goal:** Make the repository publishable by ensuring the hiring company name appears nowhere in code, prompts, configs, fixtures, or git history, and by adding tooling that prevents the name from reentering. Real prospect domains and incidental vendor names are acceptable; the tool requires real companies to demonstrate it works.
**Verified:** 2026-05-27
**Status:** passed
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The hiring company name (case-insensitive) appears in no tracked file's content or path, and in no commit reachable from any ref. | VERIFIED | `make verify-public-repo` executed during verification at HEAD `4480e4e`: `0 hits in tracked content, 0 hits in history reachable from any ref`. Exit code 0. Script at `scripts/verify_public_repo.py:73-86` scans worktree via `git ls-files` and history via `git log --all -p`. |
| 2 | `inputs/accounts.csv` retains real prospect domains by design; explicit accepted decision, not a gap. | VERIFIED | Acknowledged in ROADMAP Phase 7 success criterion 2; surfaced in REQUIREMENTS.md REPO-01 wording ("Real prospect domains in `inputs/accounts.csv` are acceptable by design"); reaffirmed in `07-FINDINGS.md:53`. |
| 3 | A deny-list grep over `git log --all -p` has been run and the result recorded with an explicit rewrite-vs-document decision. | VERIFIED | History pass implemented at `scripts/verify_public_repo.py:73-86`. Decision recorded as "rewrite" (executed 2026-05-14 via `git filter-repo`) per `07-FINDINGS.md:13` and `.planning/PROJECT.md` Key Decisions 2026-05-14 rows. |
| 4 | A pre-commit hook blocks the hiring company name (any case) in staged content or paths before it can ship. | VERIFIED | Hook wired at `.pre-commit-config.yaml:21-27` invoking `scripts/check_public_discipline.py`. Both match branches (content + path) covered by `tests/unit/test_check_public_discipline.py` (3 tests, all pass). |

**Score:** 4/4 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/verify_public_repo.py` | Re-runnable audit script with main(), counts-only output | VERIFIED | 137 lines; contains `def main(` at line 100; uses `_load_patterns`, `_scan_worktree`, `_scan_history`, `_head_sha`; never echoes raw match text. |
| `Makefile` | `verify-public-repo` target wrapping the script | VERIFIED | Line 51-52: `verify-public-repo:` target with `uv run python -m scripts.verify_public_repo`. Listed in `.PHONY` at line 1. |
| `tests/unit/test_check_public_discipline.py` | Parametrized content/path match coverage; uses FAKE_TERM | VERIFIED | 70 lines; contains `FAKE_TERM = "fake-denylisted-term-for-test"` at line 12; parametrized `test_main_flags_violations` with case_ids `content-match` and `path-match`; additional `test_main_returns_zero_when_no_denylist_terms_match`. |
| `.planning/phases/07-public-repo-audit/07-FINDINGS.md` | Verdict artifact with per-requirement table | VERIFIED | 58 lines; "## 1. Per-Requirement Verdict Table" at line 8 covers REPO-01, REPO-03, REPO-04 with evidence rows pointing to script + SHA, history rewrite, and pre-commit hook + test. |
| `.planning/REQUIREMENTS.md` | REPO-01/03/04 flipped to Complete | VERIFIED | Checkbox lines 54-56 all `- [x]`; traceability table lines 125, 127, 128 all `Complete`. |
| `README.md` | Local setup subsection before `### Picking models` | VERIFIED | `### Local setup` at line 108; content at line 110 documents `.secrets-denylist` recreation; `### Picking models` follows at line 112. No em-dashes in the new section. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `scripts/verify_public_repo.py` | `.secrets-denylist` | `Path(__file__).resolve().parent.parent / ".secrets-denylist"` | WIRED | Line 32: `DENYLIST = Path(__file__).resolve().parent.parent / ".secrets-denylist"`; same shape as the pre-commit guard. |
| `Makefile` | `scripts/verify_public_repo.py` | `uv run python -m scripts.verify_public_repo` | WIRED | Line 52; target invoked successfully during verification (exit 0). |
| `tests/unit/test_check_public_discipline.py` | `scripts.check_public_discipline` | `monkeypatch.setattr(mod, "DENYLIST", fake_denylist)` + `monkeypatch.setattr(mod, "_staged_content", ...)` | WIRED | Lines 34, 42-46; imports module at line 7; both seams patched as planned. |
| `.pre-commit-config.yaml` | `scripts/check_public_discipline.py` | `entry: python scripts/check_public_discipline.py` | WIRED | Lines 21-27; hook still present and unmodified by Phase 7 (the guard pre-dated this phase). |
| `07-FINDINGS.md` | `scripts/verify_public_repo.py` | REPO-01 evidence row | WIRED | Line 12 names the script and the run-at-SHA `8924798`. |
| `07-FINDINGS.md` | `tests/unit/test_check_public_discipline.py` | REPO-04 evidence row | WIRED | Line 14 cites the test path. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `make verify-public-repo` exits clean | `make verify-public-repo` | `0 hits in tracked content, 0 hits in history reachable from any ref (commit 4480e4e).` exit 0 | PASS |
| Unit tests pass | `uv run pytest tests/unit/test_check_public_discipline.py -q` | `3 passed in 0.01s`, exit 0 | PASS |
| Full unit suite still passes | `uv run pytest tests/unit/ -q` | `215 passed in 0.50s`, exit 0 | PASS |
| Test file uses publishable FAKE_TERM | `grep -c "fake-denylisted-term-for-test" tests/unit/test_check_public_discipline.py` | 1 | PASS |
| Test file does NOT contain hiring company name | grep `-i` for the denylisted hiring company name against `tests/unit/test_check_public_discipline.py` | no match (exit 1) | PASS |
| `.secrets-denylist` is gitignored | `grep -E "secrets-denylist" .gitignore` | match found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REPO-01 | 07-01, 07-03 | Hiring company name in no tracked content/path/history; real prospect domains acceptable | SATISFIED | `.planning/REQUIREMENTS.md:54` flipped to `[x]`; line 125 traceability `Complete`; `make verify-public-repo` returns 0 hits at HEAD `4480e4e`. |
| REPO-03 | 07-01, 07-03 | Deny-list grep over `git log --all -p` with explicit rewrite-vs-document decision | SATISFIED | `.planning/REQUIREMENTS.md:55` flipped to `[x]`; line 127 traceability `Complete`; history pass implemented in script; decision = rewrite (filter-repo 2026-05-14) per FINDINGS section 1 row 2. |
| REPO-04 | 07-02, 07-03 | Pre-commit hook blocks staged hiring company name | SATISFIED | `.planning/REQUIREMENTS.md:56` already `[x]`; line 128 traceability `Complete`; hook wired at `.pre-commit-config.yaml:21-27`; both match branches covered by 3 passing unit tests. |

No orphaned requirements: all three IDs declared in plans 07-01/07-02/07-03 appear in REQUIREMENTS.md and resolve to Complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none in Phase 7 modified files) | - | - | - | - |

The Phase 7 code review (`07-REVIEW.md`) flagged 4 warnings (silent failure on git subprocess errors, malformed regex crash, content/path counter conflation, missing `_load_patterns` edge-case tests) and 2 info notes. These are defensive-coding improvements for the new audit script, NOT goal-blocking failures: the script behaves correctly on the happy path (0 hits, clean exit), the regex format in `.secrets-denylist` is operator-controlled, and the missing edge-case tests are additional coverage suggestions rather than gaps in the parametrized content/path coverage that REPO-04 requires. The audit goal (no hiring-company-name leakage; tooling that prevents reentry) is achieved.

### Human Verification Required

None. All goal criteria are observable in the codebase and were exercised programmatically during verification:

- The grep-pass for the hiring company name ran in this verification session and reported zero hits in both worktree and full history.
- The pre-commit guard's behavior is locked by parametrized unit tests, not by manual inspection.
- The README setup documentation is present and free of em-dashes in the new section.

### Gaps Summary

No gaps. The phase goal is achieved end-to-end:

- Make the repo publishable: verified by 0-hit grep across worktree + `git log --all -p` at HEAD `4480e4e`.
- Add tooling to prevent reentry: `.pre-commit-config.yaml` hook (pre-existing, retained), `scripts/check_public_discipline.py` (pre-existing, now under unit-test coverage), `scripts/verify_public_repo.py` (new, re-runnable audit), `make verify-public-repo` (new, one-command operator entry).
- Auditable verdict: `07-FINDINGS.md` records per-requirement evidence, grep-pass summary (counts only per D-11/THR-01), bundle retention policy, and re-scrub procedure pointer.
- Traceability flipped atomically per D-12 (REPO-01/03 in commit `1a4bca5`; REPO-04 flipped earlier in commit `8924798` by plan 07-02 with the deviation acknowledged in the plan-03 commit message).

The code-review warnings in `07-REVIEW.md` are valid improvements but do not block the phase goal. They can be addressed in a follow-up if desired; Phase 8 (Loom recording) is not blocked.

---

_Verified: 2026-05-27_
_Verifier: Claude (gsd-verifier)_
