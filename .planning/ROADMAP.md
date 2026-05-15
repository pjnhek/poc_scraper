# Roadmap: poc_scraper (demo-ready v1)

## Overview

A brownfield hardening milestone for an existing async account-research pipeline. The journey starts with a no-code groundedness audit that drives the rest of the work, then closes the gaps the audit surfaces in `src/`, expands and structures the labeled eval set, generates the eval narrative artifact, hardens documented failure modes and polishes the Sheet output (in parallel), scrubs the repository for public-share readiness, and closes with a refreshed README plus a re-recorded Loom against the locked, scrubbed pipeline. Every phase is gated on the two demo-killers from PROJECT.md: an ungrounded outreach claim that traces to nothing, and eval numbers that do not tell a coherent story.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Groundedness Audit** - No-code audit producing findings that drive every subsequent phase
- [ ] **Phase 2: Groundedness Fix** - Close the gaps the audit surfaces; ship the shared citation parser, `AccountStatus` enum, and sentence-level coverage
- [ ] **Phase 3: Eval Set Expansion** - Coverage matrix, expanded labeled set, deterministic train/holdout split, cross-family calibration slice
- [ ] **Phase 4: Eval Narrative** - Committed `evals/REPORT.md` plus `make eval-report` that makes the rigor legible to a non-author reader
- [ ] **Phase 5: Failure-Mode Hardening** - Narrowed exceptions, `Retry-After` parsing, integration coverage for empty enrichment and citation-drop, optional cached demo bundle
- [ ] **Phase 6: Sheet Polish** - Four `AccountStatus` visuals, hyperlinked citations to a Sources tab, per-axis score columns, freeze panes
- [ ] **Phase 7: Public-Repo Audit** - Synthetic inputs, scrubbed prompts and configs, history deny-list grep with a deliberate decision, secret-scanning pre-commit hook
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
**Plans**: TBD

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
**Plans**: TBD

### Phase 3: Eval Set Expansion
**Goal**: Make the rigor claim defensible by growing the labeled set against a documented coverage matrix, splitting it into a fixed train and held-out slice, and adding a cross-family calibration slice that surfaces judge-writer collusion honestly.
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. `evals/COVERAGE.md` exists; its cells span the failure modes from research PITFALLS.md (partial citation, generic personalization, judge collusion, empty enrichment, and the rest).
  2. Every cell of the coverage matrix has at least one labeled example in `evals/labeled.jsonl`, and the size rationale is documented.
  3. The labeled set is split into train and ~30% holdout; the split is deterministic and recorded, and the holdout has never been inspected during prompt iteration.
  4. A cross-family calibration slice has been run using the secondary-provider judge against the same examples, and inter-judge agreement is recorded.
**Plans**: TBD

### Phase 4: Eval Narrative
**Goal**: Make the rigor work legible to a reader who never runs the pipeline by shipping a committed `evals/REPORT.md`, regenerable via `make eval-report`, that answers the six rigor questions with concrete numbers and includes a verbatim claim-source audit slice.
**Depends on**: Phase 3
**Requirements**: NARR-01, NARR-02, NARR-03
**Success Criteria** (what must be TRUE):
  1. `evals/report.py` plus a `make eval-report` target read the labeled set and a run log and write `evals/REPORT.md` deterministically; `jinja2>=3.1.6` is in `pyproject.toml`.
  2. `evals/REPORT.md` is committed and answers all six rigor questions (what is evaluated, how labeling works, how judging works, where the pipeline fails, cross-family agreement, what is held out) with concrete numbers sourced from Phase 3 outputs.
  3. The report contains a verbatim claim-source audit slice rendering several claims side by side with their cited evidence so a reader can spot-check rigor without running the pipeline.
**Plans**: TBD

### Phase 5: Failure-Mode Hardening
**Goal**: Make the pipeline survive a real CSV run end-to-end without stack traces and without masking real bugs as network errors, by narrowing broad exception catches, honoring server-side rate-limit hints, and adding test coverage for the empty-enrichment and citation-drop paths.
**Depends on**: Phase 2 (parallelizable with Phase 6 and Phase 7)
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04
**Success Criteria** (what must be TRUE):
  1. Every blanket `except Exception` in the pipeline has been narrowed to specific exception classes or annotated with the exception class name and a documented rationale.
  2. The Exa and Browserbase clients parse and honor the `Retry-After` header on 429 responses; the parsing path has dedicated test coverage.
  3. Integration tests cover the empty-enrichment (no Exa results) and citation-drop (writer emits unciteable claims) paths and assert that they surface as graceful Sheet rows, not stack traces.
  4. A cached demo bundle (such as a `vcr.py` cassette) has either shipped or been explicitly skipped with the decision recorded, gated on whether a real `make run` exceeds the ~90s threshold on the synthetic CSV.
**Plans**: TBD

### Phase 6: Sheet Polish
**Goal**: Make the rigor work visible at first glance in the Sheet so a demo viewer can see groundedness signals without operator narration: distinct visuals per `AccountStatus`, hyperlinked citations, per-axis score breakdown, and freeze panes.
**Depends on**: Phase 2 (parallelizable with Phase 5 and Phase 7)
**Requirements**: POLISH-01, POLISH-02, POLISH-03, POLISH-04
**Success Criteria** (what must be TRUE):
  1. Each of the four `AccountStatus` states (clean, low-groundedness, hook-suppressed, judge-failed) renders with a distinct, whole-row visual treatment in the Sheet.
  2. `[N]` citation markers in hook cells are hyperlinks into a `Sources` tab that lists the resolved URLs per row.
  3. The ICP score is broken into per-axis columns sourced from `configs/icp.yaml` so a viewer sees the breakdown, not just the total.
  4. Freeze panes and column widths are sized for the demo so the Sheet reads cleanly on first open without scrolling or manual resizing.
**Plans**: TBD
**UI hint**: yes

### Phase 7: Public-Repo Audit
**Goal**: Make the repository publishable by replacing any vertical-specific, vendor-specific, or company-specific content in code, prompts, configs, fixtures, and history with abstract or synthetic equivalents, and by adding tooling that prevents future leaks.
**Depends on**: Phase 2 (parallelizable with Phase 5 and Phase 6; MUST precede Phase 8)
**Requirements**: REPO-01, REPO-02, REPO-03, REPO-04
**Success Criteria** (what must be TRUE):
  1. `inputs/accounts.csv` lists synthetic, clearly fictional domains and names; the file is committed in its synthetic form.
  2. Prompts, docstrings, fixtures, and `configs/icp.yaml` carry no vertical-specific or vendor-specific language; the ICP definition remains abstract per CLAUDE.md.
  3. A deny-list grep over `git log --all -p` has been run; the hit list is recorded and a deliberate decision (rewrite history or document the historical artifacts) is logged.
  4. `detect-secrets` or `gitleaks` is wired into pre-commit so future leaks are caught before they ship.
**Plans**: TBD

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
| 1. Groundedness Audit | 0/TBD | Not started | - |
| 2. Groundedness Fix | 0/TBD | Not started | - |
| 3. Eval Set Expansion | 0/TBD | Not started | - |
| 4. Eval Narrative | 0/TBD | Not started | - |
| 5. Failure-Mode Hardening | 0/TBD | Not started | - |
| 6. Sheet Polish | 0/TBD | Not started | - |
| 7. Public-Repo Audit | 0/TBD | Not started | - |
| 8. README and Loom Refresh | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-14*
