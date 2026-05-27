# Phase 7: Public-Repo Audit - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Formalize the public-repo audit work that was largely executed out-of-band on 2026-05-14, so REPO-01, REPO-03, and REPO-04 flip from Pending to Complete with auditable evidence committed to the repo. Phase 7 produces no new feature code in `src/`; it ships verification tooling, a unit test for the existing pre-commit guard, a Phase 7 findings artifact, and a small README documentation step.

Delivers:
- `scripts/verify_public_repo.py`: re-runnable verification script. Reads `.secrets-denylist` as the single source of truth for terms. Runs two grep passes: (a) ripgrep over the working tree, (b) `git log --all -p` piped through grep. Filters `.secrets-denylist` itself by path (the one allowed location). Requires the denylist present and exits non-zero with a setup-prompt error if absent. Prints a summary; never prints raw match text. (REPO-01, REPO-03 verification).
- `make verify-public-repo`: Makefile target wrapping the script so re-verification is one command.
- `tests/unit/test_check_public_discipline.py`: parametrized coverage for `scripts/check_public_discipline.py:main()`. Two cases at minimum: (a) staged file body contains the denylist term, (b) staged file path contains the denylist term. Patches `DENYLIST` to a tmp file with a fake (non-sensitive) term so the test is independent of the real local denylist and CI-runnable. (REPO-04 verification).
- `.planning/phases/07-public-repo-audit/07-FINDINGS.md`: the Phase 7 verdict artifact. Per-requirement evidence table (REPO-01 / REPO-03 / REPO-04 -> what proves it). Records grep-pass summary counts only (no raw matches, no excerpts). Documents `../poc_scraper-FULL-BACKUP.bundle` retention policy and a brief re-scrub procedure pointer.
- `README.md` "Local setup" section update: short numbered step describing how to recreate `.secrets-denylist` on a fresh clone (gitignored file, one regex per line, used by both the pre-commit guard and the verify script).
- `.planning/REQUIREMENTS.md` traceability flip: REPO-01, REPO-03, REPO-04 status -> Complete, in the same commit that lands FINDINGS.md.

Out of scope (do not pull forward): README front-loading, architecture diagram, failure-mode gallery, "what this gets wrong" section (DEMO-02 / DEMO-03, Phase 8). Loom re-recording (DEMO-01, Phase 8). Any change to the actual scrub policy decided 2026-05-14 (history rewrite + force-push + local-only denylist + silent-on-missing pre-commit hook are all locked decisions). Generic secret scanners (detect-secrets, gitleaks) -- explicitly replaced by the project-specific name guard per 2026-05-14 decision. Any change to `src/` behavior. Any new pipeline features. Any expansion beyond the hiring company name (REPO-02 was withdrawn 2026-05-14; real prospect domains and incidental vendor names are accepted by design).

</domain>

<decisions>
## Implementation Decisions

### Verification Surface (REPO-01, REPO-03)

- **D-01:** **Grep scope: working tree + `git log --all -p`.** Two passes. Pass (a) ripgrep over the worktree catches tracked file content and paths. Pass (b) `git log --all -p | grep` catches every commit reachable from any ref. Together these directly verify REPO-01's "no tracked file content, no tracked file path, and no commit reachable from any ref." Rejected: scanning only the worktree (does not verify the success criterion). Rejected: also scanning stash + reflog + `git fsck --unreachable` (the rewrite already invalidated unreachable history; reflog will expire in 90 days; overkill).

- **D-02:** **Terms come from `.secrets-denylist`.** The same source of truth the pre-commit hook uses. If a term would block a commit, it must not exist in the repo. One file, one set of patterns, zero drift. Rejected: hand-listing additional terms ad hoc (formalizes terms outside the locked Phase 7 scope, which is hiring-company-name only per 2026-05-14). Rejected: auto-generating common-name suspect variants (pollutes results with English-fragment false positives).

- **D-03:** **Pass shape: 0 hits in tracked content + 0 hits in history, with `.secrets-denylist` filtered by path.** The denylist file is the one allowed location for the pattern; it is gitignored and never enters the public repo. Script reports "0 hits in tracked content, 0 hits in history" when that is the only match. Rejected: demand zero hits anywhere on disk (defeats the local-denylist design). Rejected: operator-named runtime allowlist (introduces decision points each run, which is exactly the drift Phase 7 is closing).

- **D-04:** **Runner: `scripts/verify_public_repo.py` + `make verify-public-repo`.** Re-runnable in one command before each Phase 8 record. Mirrors the existing `scripts/check_public_discipline.py` shape. Rejected: bash recipe documented in FINDINGS.md (drifts from the pre-commit hook's pattern source). Rejected: pytest integration test (the denylist is gitignored, so CI would skip the check or need a secrets-management workaround that contradicts the local-only design).

### Guard Robustness (REPO-04)

- **D-05:** **Unit test with a temporary denylist.** Add `tests/unit/test_check_public_discipline.py`. Patch `DENYLIST` to a tmp file with a known-fake term. Stage a fixture containing that term. Assert `main(...)` returns 1. CI-runnable, independent of the real (gitignored) denylist. Rejected: `pre-commit run --all-files` in CI (no-ops when `.secrets-denylist` is absent, which is always the case in CI -- only exercises the happy path). Rejected: manual smoke test (cost paid every operator-touch; hard to enforce).

- **D-06:** **Cover both content-match AND path-match branches.** Two parametrized cases: (a) staged file body contains the term, (b) staged file path contains the term. Both branches of `if pat.search(content) or pat.search(path)` at `scripts/check_public_discipline.py:53` exercised. Cheap and closes the test gap. The missing-denylist no-op branch is acceptable as untested (it returns 0 silently by design).

- **D-07:** **Pre-commit hook stays silent on missing `.secrets-denylist`.** Current behavior at `scripts/check_public_discipline.py:46-47` is correct: the denylist is gitignored by design and a fresh clone has no copy. Loud failure would break commits for any future contributor who does not have the (private) hiring name. Matches the existing memory note `.secrets-denylist is local-only`. Rejected: per-commit warning on stderr (noisy on every commit). Rejected: env-var-gated fail-loud (forces every contributor to know the private term).

- **D-08:** **Verify script DOES require the denylist; exits non-zero on missing.** Verification is an explicit operator action with a stakes-laden output, unlike the pre-commit hook which runs on every commit by every contributor. If the denylist is missing, `scripts/verify_public_repo.py` exits non-zero with a clear error: "verification needs the local denylist; create it (see README) before running." Asymmetry with the pre-commit hook is intentional and load-bearing.

- **D-09:** **README "Local setup" section documents denylist recreation.** Short numbered step under setup: "If you need the public-repo guard active locally, create `.secrets-denylist` with one regex per line -- the file is gitignored." Discoverable by anyone reading the README (the Phase 8 polish target). Note that the file is shared by both `scripts/check_public_discipline.py` (pre-commit) and `scripts/verify_public_repo.py` (verification). Rejected: PROJECT.md only (internal-facing; new contributors do not find it). Rejected: inline comment in the script (helps the script reader, not the operator cloning the repo -- complementary, not substitute).

### Verification Artifact Shape

- **D-10:** **Phase 7 verdict lives at `.planning/phases/07-public-repo-audit/07-FINDINGS.md`.** Mirrors Phase 1's `.planning/phases/audit/findings.md` pattern. Self-contained Phase 7 artifact: per-requirement verdict table, grep-pass summary, guard-active confirmation, formalized 2026-05-14 timeline pointer. Rejected: `07-VERIFICATION.md` matching the GSD verifier filename (loses the "audit findings" framing that mirrors Phase 1; verifier can still reference this file). Rejected: appending to PROJECT.md (bloats it with verification transcripts; harder to deep-link).

- **D-11:** **FINDINGS.md records summary counts only, no raw matches.** Format: "verify-public-repo run on 2026-05-23 at commit <SHA>: 0 hits in tracked content, 0 hits in history reachable from any ref, guard test passing." If a hit is ever found, the script output stays local; FINDINGS.md records the count and that remediation is required, never the hit text itself. Public-repo-safe by construction. Rejected: redacted excerpts (adds redaction logic + redaction-failure attack surface). Rejected: gitignored FINDINGS.md (artifact no longer demonstrates Phase 7 completion to a public-repo reader).

- **D-12:** **Per-requirement verdict table at the top of FINDINGS.md.** Three rows: REPO-01 (grep clean, link to script run), REPO-03 (rewrite-decision documented, link to PROJECT.md Key Decisions row), REPO-04 (guard live + unit-tested, link to `tests/unit/test_check_public_discipline.py`). Phase 7 "Complete" requires flipping each REPO-* row to Complete in `.planning/REQUIREMENTS.md` traceability table -- done in the same commit that lands FINDINGS.md. Rejected: link-only, no table (loses table-at-a-glance read). Rejected: defer the status flip to `/gsd:verify-phase` (Phase 7 commit must close out REQUIREMENTS.md atomically).

- **D-13:** **Phase 7 stays internal; Phase 8 README has no link to FINDINGS.md.** The hiring viewer cares that the repo IS clean, not about the audit machinery. Phase 8 records the clean state by being recorded against a Phase 7-verified SHA; no inline link needed. Rejected: README callout linking FINDINGS.md (mild signal-vs-noise tradeoff; hiring viewers may not value seeing the machinery). Rejected: "what this gets wrong" section mentioning the local-denylist limitation (invites scrutiny of a working design -- the operator IS the only one who needs the guard).

### Bundle / Backup Hygiene

- **D-14:** **Document `../poc_scraper-FULL-BACKUP.bundle` in FINDINGS.md.** Mention the path, its purpose (forensic preservation of the pre-rewrite history), and a retention note. Honest about the artifact without exposing the contents. Rejected: skip entirely (loses the audit trail; future-me may forget what the bundle is). Rejected: require immediate deletion (loses recovery option if the rewrite turns out to have missed something).

- **D-15:** **Retention policy: keep offline, delete after Phase 8 Loom is recorded and committed.** The bundle's purpose is rollback insurance during the milestone. Once Phase 8 records the Loom against the scrubbed state, the rewrite is locked in by the demo artifact and the bundle has no continuing purpose. FINDINGS.md records: "safe to delete after the Phase 8 Loom is recorded; never push to a remote; offline-only by design." Rejected: indefinite retention (value decays sharply once the milestone closes). Rejected: hash-and-delete-immediately (overkill for a single-operator hobby-scale repo).

- **D-16:** **Brief re-scrub procedure pointer only, not a full runbook.** One paragraph in FINDINGS.md: "If a future leak is discovered, the re-scrub procedure is `git filter-repo --replace-text <patterns>`, force-push, reset working repo, delete stale branches, take a fresh `../poc_scraper-FULL-BACKUP.bundle`. The original 2026-05-14 procedure followed this pattern; see PROJECT.md Key Decisions for the timeline." Lightweight reference. Rejected: full runbook with exact commands (becomes stale fast; operator re-reads filter-repo docs anyway). Rejected: skip entirely (loses the "where to start if this happens again" pointer).

- **D-17:** **`verify_public_repo.py` does NOT know about the bundle.** The bundle is intentionally outside the live repo; the script's job is to prove the public repo is clean. Script contract stays simple: "this directory + its git history are clean." Operator handles the bundle via filesystem hygiene, not via the script. Rejected: warn-if-bundle-exists (adds a non-zero exit path the operator must acknowledge). Rejected: refuse-to-pass-while-bundle-exists (couples Phase 7 verification to Phase 8 timing, contradicting D-15).

### Claude's Discretion

- Exact exit code semantics for `scripts/verify_public_repo.py` (e.g., 0 = clean, 1 = hit found, 2 = denylist missing) -- planner discretion. The contract is "non-zero on any non-clean state with a clear stderr message."
- Exact text of the README "Local setup" step (D-09) -- planner discretion within the spirit of "discoverable, brief, no exposure of the sensitive term."
- Whether to consolidate `scripts/check_public_discipline.py` and `scripts/verify_public_repo.py` shared denylist-loading logic into a small helper (e.g., a shared `_load_patterns()`) -- planner discretion based on test impact and DRY judgment.
- Exact test placement under `tests/unit/` (`test_check_public_discipline.py` is the recommended pattern; the script lives at `scripts/check_public_discipline.py` so a `tests/unit/` location is consistent with the project's existing `tests/unit/test_score_math.py` style).
- Whether to add `make verify-public-repo` as a CI gate (planner discretion; the test for `check_public_discipline.py` runs in CI regardless, but the verify-script's history scan needs the full git history which CI may not check out by default).
- Exact wording / structure of FINDINGS.md sections (per-requirement table is locked by D-12; section ordering and prose are planner discretion).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope and Requirements
- `.planning/ROADMAP.md` §"Phase 7: Public-Repo Audit" -- the four success criteria the phase is verified against; the scope-narrowing note ("Scope narrowed 2026-05-14 (was a broad vertical/vendor scrub); see Phase 7 decision log"); the parallelization note (Phase 7 unblocked after Phase 2, runs in parallel with Phases 5 and 6, MUST precede Phase 8).
- `.planning/REQUIREMENTS.md` -- REPO-01 (no hiring company name in tracked content, paths, or any reachable commit; real prospect domains acceptable), REPO-03 (deny-list grep over `git log --all -p` with explicit rewrite-vs-document decision), REPO-04 (pre-commit hook blocks the hiring company name in staged content or paths). REPO-02 is Withdrawn (scope narrowed 2026-05-14); do NOT pull it back in. Traceability table at the bottom is the source of truth for the status flips Phase 7 must perform.

### Project Constraints (locked)
- `.planning/PROJECT.md` §"Key Decisions" -- the three 2026-05-14 rows are LOAD-BEARING:
  - "Phase 7 narrowed from broad vertical/vendor/synthetic scrub to a hiring-company-name-only audit" -- defines the scope ceiling.
  - "History rewritten and force-pushed to purge the hiring company name" -- records what was done; REPO-03's rewrite-vs-document decision is closed by this row.
  - "Pre-commit company-name guard added in lieu of detect-secrets/gitleaks" -- explains why we use `scripts/check_public_discipline.py` instead of a generic secret scanner.
- `.planning/PROJECT.md` §"Constraints" -- public-repo discipline; stack is locked; no em-dashes in published markdown; no emojis. FINDINGS.md and README updates MUST honor these.
- `CLAUDE.md` (project root) §"Public repo discipline" -- the operator-facing version of the same constraint. Note: the .planning/PROJECT.md framing is "hiring company name" only; the CLAUDE.md framing is broader. PROJECT.md (newer) supersedes CLAUDE.md (older). Use PROJECT.md.

### Audit Evidence (binding)
- `.planning/phases/audit/findings.md` §"OQ2 -- History rewrite vs accept-and-document" (lines 288-294) -- the binding rationale for the rewrite-vs-document decision. Reference this from FINDINGS.md's REPO-03 row.

### Code Under Change (or referenced)
- `scripts/check_public_discipline.py` (the existing pre-commit guard; 67 lines):
  - `DENYLIST` constant at `scripts/check_public_discipline.py:18` -- the path to the local-only `.secrets-denylist`.
  - `_load_patterns()` at `scripts/check_public_discipline.py:21-30` -- pattern-loading logic (case-insensitive regex per line). Verify script may share this helper (D-Claude's-Discretion).
  - `_staged_content()` at `scripts/check_public_discipline.py:33-41` -- reads the staged blob via `git show :<path>`. Pre-commit-specific; verify script uses different sources (worktree + `git log --all -p`).
  - `main()` at `scripts/check_public_discipline.py:44-62` -- iterates argv, checks content and path against patterns. The unit test (D-05/D-06) targets this function.
- `scripts/verify_public_repo.py` (NEW) -- the verification script per D-01..D-04, D-08, D-17.
- `.pre-commit-config.yaml` -- the local repo block at lines 21-27 already wires the public-repo-discipline hook; no change needed unless the planner consolidates helpers (D-Claude's-Discretion).
- `.secrets-denylist` (gitignored, local-only) -- the single source of truth for terms. Confirmed present locally on 2026-05-23 (1 active pattern).
- `.gitignore` -- already ignores `.secrets-denylist`; no change needed.
- `Makefile` -- existing targets include `install`, `run`, `test`, `smoke`, `lint`, `format`, `typecheck`, `clean`, `eval-live`, `eval-fixtures`, `setup-sheet`. Phase 7 adds `verify-public-repo` per D-04.
- `tests/unit/test_check_public_discipline.py` (NEW) -- the parametrized unit test per D-05, D-06.
- `README.md` -- Phase 7 adds a "Local setup" section step per D-09. Phase 8 will polish the rest of the README separately; do NOT do Phase 8's job here.

### Phase 7 Output Artifacts
- `.planning/phases/07-public-repo-audit/07-FINDINGS.md` (NEW) -- the Phase 7 verdict per D-10, D-11, D-12.
- `.planning/REQUIREMENTS.md` traceability table -- Phase 7 flips REPO-01, REPO-03, REPO-04 from Pending to Complete per D-12 in the same commit as FINDINGS.md.

### Forensic Bundle (outside repo)
- `../poc_scraper-FULL-BACKUP.bundle` (outside the repo root; documented in PROJECT.md Key Decisions row 2026-05-14) -- the pre-rewrite history. Phase 7 documents its retention policy in FINDINGS.md per D-14, D-15, D-16. NOT scanned by `verify_public_repo.py` per D-17.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/check_public_discipline.py::_load_patterns` at `scripts/check_public_discipline.py:21-30` -- pattern-loading logic for `.secrets-denylist`. `scripts/verify_public_repo.py` can either duplicate this (5 lines, DRY-cost low) or import a shared helper (cleaner but adds an import path). Planner discretion.
- `tests/unit/` -- existing unit-test directory. Examples to mirror: `tests/unit/test_score_math.py` (parametrized cases, pure functions). `test_check_public_discipline.py` follows the same shape.
- `Makefile` -- existing targets are one-line wrappers around `uv run` invocations. `make verify-public-repo` follows the same pattern (e.g., `uv run python scripts/verify_public_repo.py`).

### Established Patterns
- **Local-only files are gitignored, never committed.** `.env`, `credentials.json`, `.secrets-denylist` all live locally; the repo never carries them. Phase 7 verify-script error messages must respect this -- "create `.secrets-denylist`" (operator action), not "commit `.secrets-denylist`."
- **Pre-commit hooks are local repos in `.pre-commit-config.yaml`.** The public-repo-discipline hook at `.pre-commit-config.yaml:21-27` is a `language: system` entry that shells `python scripts/check_public_discipline.py`. No new hook needed for Phase 7; existing hook is the artifact under test.
- **CI runs offline tests + mypy + ruff + black --check.** Per CLAUDE.md "Pre-commit vs CI split" section. The new unit test for the public-discipline guard runs in CI as part of the offline test suite.
- **Strict mypy.** Per CLAUDE.md and `pyproject.toml:56-66`. `scripts/verify_public_repo.py` must be fully annotated. The existing `scripts/check_public_discipline.py` is fully annotated (e.g., `_load_patterns() -> list[re.Pattern[str]]` at line 21); follow the same shape.
- **No emojis in code or commit messages.** Per CLAUDE.md. FINDINGS.md and the new script must comply.
- **No em-dashes in published markdown.** Per CLAUDE.md. FINDINGS.md is internal but README is published; honor the constraint in README copy (use commas, parentheses, or rewrite).

### Integration Points
- `scripts/check_public_discipline.py` is invoked by `.pre-commit-config.yaml` only; no other code path imports it. Adding a unit test does not require touching `.pre-commit-config.yaml` (the hook keeps invoking `scripts/check_public_discipline.py` as before; the test exercises `main()` directly via Python import).
- `scripts/verify_public_repo.py` is invoked by `make verify-public-repo` only; no `pre-commit-config.yaml` wiring (verification is an explicit operator action, not a commit-time gate). The script can also be invoked directly via `uv run python scripts/verify_public_repo.py` for ad-hoc operator use.
- `.planning/REQUIREMENTS.md` traceability table update: small diff (three "Pending" -> "Complete" cells). Same commit as `07-FINDINGS.md` per D-12 to keep the audit atomic.

</code_context>

<specifics>
## Specific Ideas

- Verification is asymmetric with the pre-commit hook by design: the pre-commit hook is silent on missing `.secrets-denylist` (D-07) to avoid breaking contributors, while the verify script requires the denylist and fails loud (D-08) because it is an operator-explicit action with a stakes-laden output. Keep these two paths in sync on pattern source (`.secrets-denylist`) but distinct on missing-file behavior.
- The hiring company name must never appear in any committed Phase 7 artifact, including grep transcripts. The denylist file stores the term; FINDINGS.md, the verify script's source code, and the unit test all use placeholder/fake terms or path-based references only. The test fixture in `tests/unit/test_check_public_discipline.py` should use a non-sensitive fake term (e.g., "fake-denylisted-term-for-test") so the test is publishable.
- The bundle at `../poc_scraper-FULL-BACKUP.bundle` lives at the operator's filesystem; PROJECT.md already records it. FINDINGS.md adds a retention policy (D-15) and brief re-scrub pointer (D-16). It is NOT scanned by `verify_public_repo.py` per D-17 because that would conflate "the public repo is clean" with "the operator's filesystem hygiene is current."
- `make verify-public-repo` should be runnable before Phase 8 records the Loom, so the demo SHA is provably clean. The roadmap's "Phase 7 -> Phase 8 (hard precedence; non-negotiable)" makes this the gating action.

</specifics>

<deferred>
## Deferred Ideas

- **`detect-secrets` / `gitleaks` integration.** Already rejected on 2026-05-14: "Generic secret scanners do not target a project-specific name." Re-list here so the planner does not pull them back in. Revisit only if the public-repo discipline broadens beyond a single name (which would re-open REPO-02).
- **Adding `make verify-public-repo` to CI as a required check.** Deferred to planner discretion (Claude's Discretion section above). The complication is that CI usually does a shallow clone, which `git log --all -p` cannot scan. Treat as planner-judgment, not a Phase 7 requirement.
- **Consolidating `_load_patterns()` into a shared helper.** Deferred to planner discretion. If both scripts ship with duplicated pattern loading and the DRY violation feels real, extract `scripts/_denylist.py`. Not Phase 7's call.
- **A periodic auto-re-verify (e.g., GitHub Action on a schedule).** Out of scope; the verification is operator-triggered before each Phase 8 record. Revisit only if Phase 8 or a future milestone needs continuous assurance.
- **Phase 8 README front-loading + architecture diagram + failure-mode gallery + "what this gets wrong" section.** Explicitly out of Phase 7. The README "Local setup" step in D-09 is the ONLY README change Phase 7 makes; Phase 8 owns the rest.
- **Phase 8 Loom re-recording.** Out of Phase 7. Phase 7 enables Phase 8 by certifying the SHA is clean; Phase 8 records.

</deferred>

---

*Phase: 7-public-repo-audit*
*Context gathered: 2026-05-23*
