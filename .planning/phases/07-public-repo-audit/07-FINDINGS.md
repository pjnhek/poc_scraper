# Phase 7 Public-Repo Audit Findings

**Audit date:** 2026-05-23
**Auditor:** Claude
**Phase context:** Phase 7 of 8 (Public-Repo Audit)
**Requirements:** REPO-01 (no hiring company name in content, paths, or reachable history), REPO-03 (deny-list grep with rewrite-vs-document decision), REPO-04 (pre-commit hook blocks the name)

## 1. Per-Requirement Verdict Table (D-12)

| Requirement | Verdict | Evidence |
|-------------|---------|----------|
| REPO-01 | Complete | `make verify-public-repo` run 2026-05-23 at commit `8924798`: 0 hits in tracked content, 0 hits in history reachable from any ref. Source: `scripts/verify_public_repo.py`. |
| REPO-03 | Complete | History rewritten via `git filter-repo` on 2026-05-14, force-pushed. Pre-rewrite preserved offline at `../poc_scraper-FULL-BACKUP.bundle`. Decision recorded at `.planning/PROJECT.md` Key Decisions row 2026-05-14. Rationale at `.planning/phases/audit/findings.md` lines 288-294 (OQ2). |
| REPO-04 | Complete | Pre-commit hook at `.pre-commit-config.yaml:21-27` invokes `scripts/check_public_discipline.py`. Content-match and path-match branches covered by `tests/unit/test_check_public_discipline.py`. |

## 2. Grep-Pass Summary (D-11)

```
verify-public-repo: 0 hits in tracked content, 0 hits in history reachable from any ref (commit 8924798).
```

The above line is the output of `make verify-public-repo`, defined at `scripts/verify_public_repo.py`. Per D-11, only summary counts are recorded here. If a future re-run yields a non-zero count, the script's stderr will name the count; the matching content stays local.

## 3. Pre-Commit Guard Confirmation (REPO-04)

- Hook wired at `.pre-commit-config.yaml:21-27` (local repo, `language: system`).
- Guard script at `scripts/check_public_discipline.py`; reads patterns from `.secrets-denylist` (gitignored).
- Branch coverage at `tests/unit/test_check_public_discipline.py` (content-match and path-match parametrized cases per D-06).

## 4. Forensic Bundle Retention Policy (D-14, D-15)

The pre-rewrite git history is preserved offline at `../poc_scraper-FULL-BACKUP.bundle`, a sibling of the repo root (not inside the repo). It was captured 2026-05-14 immediately before the `git filter-repo` rewrite and serves as a forensic rollback artifact. Retention rule (D-15): safe to delete after the Phase 8 Loom is recorded; never push to a remote; offline-only by design. Per D-17, `scripts/verify_public_repo.py` does NOT scan the bundle; its scan boundary is the current repo plus its git history only.

## 5. Re-Scrub Procedure Pointer (D-16)

If a future leak is discovered, the re-scrub procedure is `git filter-repo --replace-text <patterns>`, force-push, reset the working repo, delete stale branches, and take a fresh `../poc_scraper-FULL-BACKUP.bundle`. The original 2026-05-14 procedure followed this pattern; see `.planning/PROJECT.md` Key Decisions for the timeline.

## 6. Timeline Pointer to PROJECT.md (2026-05-14 rows)

The three load-bearing 2026-05-14 entries in `.planning/PROJECT.md` Key Decisions:

- "Phase 7 narrowed from broad vertical/vendor/synthetic scrub to a hiring-company-name-only audit"
- "History rewritten and force-pushed to purge the hiring company name"
- "Pre-commit company-name guard added in lieu of detect-secrets/gitleaks"

## Audit Sign-off

Date: 2026-05-23

All four ROADMAP Phase 7 success criteria (`.planning/ROADMAP.md` lines 204-209) are satisfied by this document:

1. The hiring company name (case-insensitive) appears in no tracked file's content or path, and in no commit reachable from any ref. Evidence: section 1 REPO-01 row plus section 2 grep-pass summary (0 hits in tracked content, 0 hits in history at commit `8924798`).
2. `inputs/accounts.csv` retains real prospect domains by design; the pipeline must run against real companies. This is an explicit accepted decision recorded in `.planning/PROJECT.md` Key Decisions 2026-05-14 (Phase 7 scope narrowing row) and surfaced in REQUIREMENTS.md REPO-01 wording. Not a gap.
3. A deny-list grep over `git log --all -p` has been run and the result recorded with an explicit rewrite-vs-document decision. Evidence: section 2 grep-pass summary (`scripts/verify_public_repo.py` is re-runnable) plus section 1 REPO-03 row linking to the OQ2 rationale at `.planning/phases/audit/findings.md` lines 288-294.
4. A pre-commit hook blocks the hiring company name (any case) in staged content or paths before it can ship. Evidence: section 3 Pre-Commit Guard Confirmation plus section 1 REPO-04 row, with branch coverage at `tests/unit/test_check_public_discipline.py`.

Phase 7 closes against commit `8924798`. The repo is provably ready for Phase 8 to record the Loom against a clean SHA, fulfilling the ROADMAP "Phase 7 -> Phase 8 (hard precedence; non-negotiable)" gating.
