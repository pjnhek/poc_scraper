# Roadmap: poc_scraper (demo-ready v1)

## Overview

A brownfield hardening milestone for an existing async account-research pipeline. The journey starts with a no-code groundedness audit that drives the rest of the work, then closes the gaps the audit surfaces in `src/`, expands and structures the labeled eval set, generates the eval narrative artifact, hardens documented failure modes and polishes the Sheet output (in parallel), scrubs the repository for public-share readiness, and closes with a refreshed README plus a re-recorded Loom against the locked, scrubbed pipeline. Every phase is gated on the two demo-killers from PROJECT.md: an ungrounded outreach claim that traces to nothing, and eval numbers that do not tell a coherent story.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Groundedness Audit** - No-code audit producing findings that drive every subsequent phase (completed 2026-05-15)
- [x] **Phase 2: Groundedness Fix** - Close the gaps the audit surfaces; ship the shared citation parser, `AccountStatus` enum, and sentence-level coverage (completed 2026-05-15)
- [x] **Phase 3: Eval Set Expansion** - Coverage matrix, expanded labeled set, deterministic train/holdout split, cross-family calibration slice (completed 2026-05-16)
- [x] **Phase 4: Eval Narrative** - Committed `evals/REPORT.md` plus `make eval-report` that makes the rigor legible to a non-author reader (completed 2026-05-21)
- [x] **Phase 5: Failure-Mode Hardening** - Narrowed exceptions, `Retry-After` parsing, integration coverage for empty enrichment and citation-drop, optional cached demo bundle (completed 2026-05-22)
- [x] **Phase 6: Sheet Polish** - Four `AccountStatus` visuals, hyperlinked citations to a Sources tab, per-axis score columns, freeze panes (completed 2026-05-23)
- [ ] **Phase 7: Public-Repo Audit** - Company-name audit: the hiring company name appears nowhere in code, configs, fixtures, or history; secret-scanning pre-commit hook. Real prospect domains and vendor names are acceptable.
- [ ] **Phase 8: README and Loom Refresh** - Front-loaded README, architecture diagram, failure-mode gallery, "what this gets wrong" section, re-recorded Loom pinned to a commit SHA

## Parallelization

After Phase 2 lands the `AccountStatus` schema and the shared citation parser, Phases 5 and 6 are independent and can run in parallel. Phase 7 (public-repo audit) is independent of code work and can run in parallel with Phases 5 and 6, but it MUST complete before Phase 8 because the README and Loom record the scrubbed state of the repository. Phases 1, 2, 3, 4, and 8 are strictly sequential.

Concretely:

- Phase 5 || Phase 6 (after Phase 2)
- Phase 7 || {Phase 5, Phase 6} (after Phase 2)
- Phase 7 -> Phase 8 (hard precedence; non-negotiable)

## Phase Details

### Phase 1: Groundedness Audit

**Goal**: Produce a findings document that enumerates every gap between current pipeline behavior and a strict groundedness contract, plus concrete decisions on the six open questions, so Phase 2 has a code-change list rather than a hypothesis.
**Depends on**: Nothing (first phase)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):

  1. `.planning/phases/audit/findings.md` exists and lists every groundedness gap with a `file:line` reference for each finding.
  2. A sample of 10-20 existing outreach hooks has been hand-paired claim-to-evidence with per-claim verdicts (grounded, partial, fabricated) recorded in the findings.
  3. Each of the six open questions from research SUMMARY.md (sentence-coverage shape, history rewrite vs document, specificity/recency timing, demo-bundle caching need, `great-tables` yes/no, label migration vs re-label) has a documented decision in the findings.
  4. The findings document the scope handoff to Phase 2 in actionable form (the list of edits Phase 2 will make).

**Plans**: 3 plans

Plans:

- [x] 01-01-PLAN.md -- Gap enumeration from source code (AUDIT-01): create findings.md with D-03 contract preamble and all groundedness gaps (GAP-01 through GAP-08) with verified file:line refs
- [x] 01-02-PLAN.md -- Pipeline run and hook capture (AUDIT-02 prerequisite): execute fresh make run against all 10 domains, capture hook paragraphs into hooks-sample.txt for claim-pairing
- [x] 01-03-PLAN.md -- Claim-pairing analysis, OQ decisions, Phase 2 handoff (AUDIT-02, AUDIT-03): hand-pair 10-20 claims, decide all six open questions including evidence-driven D-05, write Phase 2 code-change list

### Phase 2: Groundedness Fix

**Goal**: Close every gap the audit surfaced in `src/` and `evals/`, including the shared citation parser, the discrete `AccountStatus` enum, the `EvalScore.eval_failed` sentinel, sentence-level writer coverage, and the removal of any hardcoded vertical-coupled defaults.
**Depends on**: Phase 1
**Requirements**: FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, FIX-06
**Success Criteria** (what must be TRUE):

  1. `src/citations.py` exists as the single source of truth for citation parsing and coverage rules, and both `src/outreach.py` and `evals/rubric.py` import from it.
  2. `models.AccountStatus` is a discrete enum distinguishing clean, low-groundedness, hook-suppressed, and judge-failed states; `EvalScore.eval_failed` separates judge failure from writer fabrication.
  3. The writer enforces sentence-level citation coverage per the shape decided in Phase 1; sub-coverage claims are suppressed rather than emitted.
  4. The writer's default-contacts fallback is either removed entirely or moved into `configs/icp.yaml` so no vertical-specific names can leak from `src/`.
  5. `rapidfuzz>=3.14.5` is in `pyproject.toml` and `groundedness_suppress_threshold` is in `configs/icp.yaml`; the strict mypy + offline test suite still passes.

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 02-00-PLAN.md -- Wave 0: rapidfuzz dep + test stubs (FIX-01, FIX-06): uv add rapidfuzz>=3.14.5; create tests/unit/test_citations.py stubs (D-06 all 9 cases) and tests/unit/test_contacts.py stub (FIX-05)
- [x] 02-01-PLAN.md -- Wave 1: src/citations.py extraction + unit tests (FIX-01, FIX-06): create citations.py with INDEX_MARKER_RE, parse_indices, markers_in_paragraph, check_claim_coverage, assemble_paragraph; update outreach.py + rubric.py imports; fill in all 9 D-06 unit tests
- [x] 02-02-PLAN.md -- Wave 1: models schema + evals blast radius (FIX-02, FIX-03): AccountStatus str-enum, EvalScore.eval_failed/specificity/recency, rubric.py _floor()/evaluate_hook()/evaluate_account(), mypy blast radius

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-03-PLAN.md -- Wave 2: writer output shape + per-claim suppression (FIX-04): D-01 prompt shape in outreach.py, call assemble_paragraph(), D-06 functional test for fabricated-claim suppression
- [x] 02-04-PLAN.md -- Wave 2: config + contacts cleanup (FIX-05, FIX-06): DefaultPersona + groundedness_suppress_threshold in icp_config.py + icp.yaml, _default_contacts reads config, D-07 validators, unit tests

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-05-PLAN.md -- Wave 3: pipeline/sheets propagation + phase gate (FIX-02, FIX-03): D-03 precedence in process_account, sheets.py HEADERS + _build_row + STATUS_LEGEND, integration tests, full mypy + offline suite green

### Phase 3: Eval Set Expansion

**Goal**: Make the rigor claim defensible by growing the labeled set against a documented coverage matrix, splitting it into a fixed train and held-out slice, and adding a cross-family calibration slice that surfaces judge-writer collusion honestly.
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):

  1. `evals/COVERAGE.md` exists; its cells span the failure modes from research PITFALLS.md (partial citation, generic personalization, judge collusion, empty enrichment, and the rest).
  2. Every cell of the coverage matrix has at least one labeled example in `evals/labeled.jsonl`, and the size rationale is documented.
  3. The labeled set is split into train and ~30% holdout; the split is deterministic and recorded, and the holdout has never been inspected during prompt iteration.
  4. A cross-family calibration slice has been run using the secondary-provider judge against the same examples, and inter-judge agreement is recorded.

**Plans**: 6 plans

Plans:

- [x] 03-00-PLAN.md -- Wave 0: fix stale test assertions and create stub test modules (EVAL-01, EVAL-02, EVAL-03, EVAL-04)
- [x] 03-01-PLAN.md -- Wave 1: evals/agreement.py with assign_split, cohen_kappa_linear, pct_agreement; fill test stubs (EVAL-03, EVAL-04)
- [x] 03-02-PLAN.md -- Wave 1: extend evals/run_eval.py schema and create evals/check_coverage.py (EVAL-01, EVAL-02, EVAL-03, EVAL-04)
- [x] 03-03-PLAN.md -- Wave 2: author evals/COVERAGE.md coverage matrix (EVAL-01, EVAL-02)
- [x] 03-04-PLAN.md -- Wave 3: operator labeling session and labeled.jsonl rebuild (EVAL-01, EVAL-02, EVAL-03) [checkpoint]
- [x] 03-05-PLAN.md -- Wave 4: calibration runner, CALIBRATION.md, calibration.json (EVAL-04) [checkpoint]

### Phase 4: Eval Narrative

**Goal**: Make the rigor work legible to a reader who never runs the pipeline by shipping a committed `evals/REPORT.md`, regenerable via `make eval-report`, that answers the six rigor questions with concrete numbers and includes a verbatim claim-source audit slice.
**Depends on**: Phase 3
**Requirements**: NARR-01, NARR-02, NARR-03
**Success Criteria** (what must be TRUE):

  1. `evals/report.py` plus a `make eval-report` target read the labeled set and a run log and write `evals/REPORT.md` deterministically; `jinja2>=3.1.6` is in `pyproject.toml`.
  2. `evals/REPORT.md` is committed and answers all six rigor questions (what is evaluated, how labeling works, how judging works, where the pipeline fails, cross-family agreement, what is held out) with concrete numbers sourced from Phase 3 outputs.
  3. The report contains a verbatim claim-source audit slice rendering several claims side by side with their cited evidence so a reader can spot-check rigor without running the pipeline.

**Plans**: 3 plans

Plans:
**Wave 1**

- [x] 04-01-PLAN.md -- Wave 1: add --emit-log to evals/run_eval.py and tests (NARR-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md -- Wave 2: jinja2 dep, evals/report.py renderer + template + unit tests for selectors, id-lookup, calibration sub-tables, freshness, byte-stability (NARR-01, NARR-02, NARR-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-03-PLAN.md -- Wave 3: Makefile eval-report target, operator checkpoint to emit + commit run-log.json, generate + commit REPORT.md, integration tests for D-06 freshness via mtime manipulation (NARR-01, NARR-02, NARR-03)

### Phase 5: Failure-Mode Hardening

**Goal**: Make the pipeline survive a real CSV run end-to-end without stack traces and without masking real bugs as network errors, by narrowing broad exception catches, honoring server-side rate-limit hints, and adding test coverage for the empty-enrichment and citation-drop paths.
**Depends on**: Phase 2 (parallelizable with Phase 6 and Phase 7)
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04
**Success Criteria** (what must be TRUE):

  1. Every blanket `except Exception` in the pipeline has been narrowed to specific exception classes or annotated with the exception class name and a documented rationale.
  2. The Exa and Browserbase clients parse and honor the `Retry-After` header on 429 responses; the parsing path has dedicated test coverage.
  3. Integration tests cover the empty-enrichment (no Exa results) and citation-drop (writer emits unciteable claims) paths and assert that they surface as graceful Sheet rows, not stack traces.
  4. A cached demo bundle (such as a `vcr.py` cassette) has either shipped or been explicitly skipped with the decision recorded, gated on whether a real `make run` exceeds the ~90s threshold on the synthetic CSV.

**Plans**: 4 plans

Plans:
**Wave 1**

- [x] 05-01-PLAN.md -- Wave 1: src/clients/retry.py with parse_retry_after + retry_after_aware_wait; swap wait= in exa/browserbase clients; unit + functional tests (HARD-02)

**Wave 2** *(blocked on Wave 1; 05-02 touches src/clients/browserbase_client.py which 05-01 also modifies)*

- [x] 05-02-PLAN.md -- Wave 2: narrow 7 blanket except Exception sites in pipeline.py / browserbase_client.py / evals/run_eval.py; prefix exception class into ScoredAccount.error string (HARD-01)

**Wave 3** *(parallel; both depend on 05-02 error format and pipeline.py edits)*

- [x] 05-03-PLAN.md -- Wave 3: integration tests for empty-enrichment and citation-drop reaching SheetsWriter._build_row in tests/integration/test_pipeline_failures.py (HARD-03)
- [x] 05-04-PLAN.md -- Wave 3: src/clients/replay.py (Replay + Recording clients + ReplayMissError); Settings.demo_bundle/record_bundle; build_deps branch; make run-demo; fixtures/demo-bundle/ shell; unit + functional tests (HARD-04)

### Phase 6: Sheet Polish

**Goal**: Make the rigor work visible at first glance in the Sheet so a demo viewer can see groundedness signals without operator narration: distinct visuals per `AccountStatus`, hyperlinked citations, per-axis score breakdown, and freeze panes.
**Depends on**: Phase 2 (parallelizable with Phase 5 and Phase 7)
**Requirements**: POLISH-01, POLISH-02, POLISH-03, POLISH-04
**Success Criteria** (what must be TRUE):

  1. Each of the four `AccountStatus` states (clean, low-groundedness, hook-suppressed, judge-failed) renders with a distinct, whole-row visual treatment in the Sheet.
  2. `[N]` citation markers in hook cells are hyperlinks into a `Sources` tab that lists the resolved URLs per row.
  3. The ICP score is broken into per-axis columns sourced from `configs/icp.yaml` so a viewer sees the breakdown, not just the total.
  4. Freeze panes and column widths are sized for the demo so the Sheet reads cleanly on first open without scrolling or manual resizing.

**Plans**: 4 plans

Plans:

**Wave 1**

- [x] 06-01-PLAN.md -- Wave 1: AccountStatus visual contract + Legend tab (POLISH-01): ACCOUNT_STATUS_COLORS palette dict (white/yellow/orange/gray), account_status_row_colors helper, build_legend_rows, LEGEND_TAB_TITLE, delete VERDICT_COLORS/verdict_row_colors, preserve _apply_eval_flag_text

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md -- Wave 2: Per-run Sources tab + HYPERLINK citations (POLISH-02): shrink HEADERS by 3 columns, delete _format_hook_citations, simplify _format_score_justification, add build_sources_rows + _hyperlink_formula + _sources_row_lookup, hook + justification cells become HYPERLINK formulas

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 06-03-PLAN.md -- Wave 3: Per-axis weight-baked display labels (POLISH-03): axis_display_labels(config) helper, build_rows projects display labels onto row 0 when config provided, snake_case HEADERS preserved for HEADERS.index() lookups

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 06-04-PLAN.md -- Wave 4: Freeze panes + column widths + wrap strategy (POLISH-04): COLUMN_WIDTHS + WIDTH_CLASS_PX dicts (narrow/medium/wide/extra), _apply_freeze_panes / _apply_column_widths / _apply_wrap_strategy helpers wired after _write_values

**UI hint**: yes

### Phase 7: Public-Repo Audit

**Goal**: Make the repository publishable by ensuring the hiring company name appears nowhere in code, prompts, configs, fixtures, or git history, and by adding tooling that prevents the name from reentering. Real prospect domains and incidental vendor names are acceptable; the tool requires real companies to demonstrate it works. Scope narrowed 2026-05-14 (was a broad vertical/vendor scrub); see Phase 7 decision log.
**Depends on**: Phase 2 (parallelizable with Phase 5 and Phase 6; MUST precede Phase 8)
**Requirements**: REPO-01, REPO-03, REPO-04
**Success Criteria** (what must be TRUE):

  1. The hiring company name (case-insensitive) appears in no tracked file's content or path, and in no commit reachable from any ref. (Largely satisfied 2026-05-14: history rewritten via git filter-repo, force-pushed; see decision log.)
  2. `inputs/accounts.csv` retains real prospect domains by design (the pipeline must run against real companies); this is an explicit accepted decision, not a gap.
  3. A deny-list grep over `git log --all -p` has been run and the result recorded with an explicit rewrite-vs-document decision. (Satisfied 2026-05-14: history rewritten; decision logged.)
  4. A pre-commit hook blocks the hiring company name (any case) in staged content or paths before it can ship. (Satisfied 2026-05-14: scripts/check_public_discipline.py + local-only .secrets-denylist.)

**Plans**: 3 plans

Plans:

**Wave 1** (parallel)

- [x] 07-01-PLAN.md -- scripts/verify_public_repo.py + make verify-public-repo target (REPO-01, REPO-03): re-runnable worktree+history grep over .secrets-denylist patterns; counts-only output per D-11
- [ ] 07-02-PLAN.md -- tests/unit/test_check_public_discipline.py (REPO-04): parametrized content-match and path-match coverage for the pre-commit guard; uses publishable fake term per D-05

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 07-03-PLAN.md -- 07-FINDINGS.md + REQUIREMENTS.md flip + README Local setup (REPO-01, REPO-03, REPO-04): atomic D-12 commit closing all three requirements with audit evidence

### Phase 8: README and Loom Refresh

**Goal**: Ship the public-facing artifact that closes the milestone: a front-loaded README and a re-recorded Loom that reflect the final, scrubbed pipeline output and a specific commit SHA, so a hiring or GTM viewer encounters the rigor story without operator narration.
**Depends on**: Phase 7 (hard precedence), Phase 4 (eval numbers), Phase 6 (Sheet visuals)
**Requirements**: DEMO-01, DEMO-02, DEMO-03
**Success Criteria** (what must be TRUE):

  1. The README opens with what / why / proof in the first scroll, links to `evals/REPORT.md`, and references a specific committed SHA that matches the recorded Loom.
  2. A re-recorded Loom walkthrough against the synthetic CSV reflects the final pipeline output (citation UX, four-state Sheet visuals, eval narrative) and is linked from the README.
  3. The README contains an architecture diagram, a failure-mode gallery (one screenshot per `AccountStatus` state), the editable-rubric framing, and an honest "what this gets wrong" section.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**

Phases execute in numeric order, with the parallelization carve-outs noted under "Parallelization" above. The execute workflow may schedule Phases 5, 6, and 7 concurrently after Phase 2 lands.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Groundedness Audit | 3/3 | Complete   | 2026-05-15 |
| 2. Groundedness Fix | 6/6 | Complete   | 2026-05-15 |
| 3. Eval Set Expansion | 6/6 | Complete   | 2026-05-16 |
| 4. Eval Narrative | 3/3 | Complete   | 2026-05-22 |
| 5. Failure-Mode Hardening | 4/4 | Complete   | 2026-05-22 |
| 6. Sheet Polish | 2/4 | In Progress|  |
| 7. Public-Repo Audit | 1/3 | In Progress|  |
| 8. README and Loom Refresh | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-14*
*Phase 1 plans added: 2026-05-15*
*Phase 2 plans added: 2026-05-15*
*Phase 5 plans added: 2026-05-21*
