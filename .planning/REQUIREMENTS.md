# Requirements: poc_scraper (demo-ready v1)

**Defined:** 2026-05-14
**Core Value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader.

## v1 Requirements

Requirements for the demo-ready v1 milestone. Each maps to exactly one roadmap phase. IDs use the milestone's working phase categories.

### Groundedness Audit

- [ ] **AUDIT-01**: Produce `.planning/phases/audit/findings.md` enumerating every gap between the current writer/judge behavior and a strict groundedness contract, with `file:line` references for each finding.
- [ ] **AUDIT-02**: Hand-pair claims to evidence on a sample of 10-20 existing outreach hooks; record per-claim verdicts (grounded, partial, fabricated) in the audit findings.
- [ ] **AUDIT-03**: Resolve the six open questions from `.planning/research/SUMMARY.md` with concrete decisions documented in the audit findings (sentence-coverage shape, history rewrite vs document, specificity/recency axes timing, demo-bundle caching need, `great-tables` yes/no, label-migration vs re-label).

### Groundedness Fix

- [ ] **FIX-01**: Extract `src/citations.py` as the single source of truth for citation parsing and coverage rules, imported by both `src/outreach.py` and `evals/rubric.py`.
- [ ] **FIX-02**: Replace `status: Literal["scored","unscoreable"]` + free-form `error: str` with an `AccountStatus` enum that distinguishes clean, low-groundedness, hook-suppressed, and judge-failed.
- [ ] **FIX-03**: Add `EvalScore.eval_failed` sentinel so a judge-side failure can never be rendered as a low-groundedness writer fabrication.
- [ ] **FIX-04**: Enforce sentence-level citation coverage in the writer per the shape decided in AUDIT-03; suppress claims that fail coverage rather than emitting them.
- [ ] **FIX-05**: Move the writer's default-contacts fallback into `configs/icp.yaml` (or drop it entirely) so it cannot silently leak vertical-specific names into prompts or output.
- [ ] **FIX-06**: Add `rapidfuzz>=3.14.5` to `pyproject.toml` via `uv` and use it for sentence-to-evidence overlap; add `groundedness_suppress_threshold` to `configs/icp.yaml`.

### Eval Set Expansion

- [x] **EVAL-01**: Define a coverage matrix in `evals/COVERAGE.md` whose cells span the failure modes from `.planning/research/PITFALLS.md` (partial citation, generic personalization, judge collusion, empty enrichment, etc.).
- [x] **EVAL-02**: Expand `evals/labeled.jsonl` so every coverage-matrix cell has at least one labeled example; document the size rationale.
- [x] **EVAL-03**: Split the labeled set into train and a held-out evaluation slice (~30% holdout); record the split deterministically; never inspect holdout during prompt tuning.
- [x] **EVAL-04**: Run a cross-family calibration slice using the NVIDIA judge against the same examples and record inter-judge agreement.

### Eval Narrative

- [x] **NARR-01**: Add `evals/report.py` plus a `make eval-report` target that reads the labeled set and a run log and writes `evals/REPORT.md` (committed for GitHub legibility); add `jinja2>=3.1.6` for templating.
- [x] **NARR-02**: `evals/REPORT.md` answers the six rigor questions from Pitfall 8 (what we evaluate, how we label, how we judge, where we fail, cross-family agreement, what is held out) with concrete numbers from EVAL-02/03/04.
- [x] **NARR-03**: Include a verbatim claim-source audit slice in the report (a small set of claims with their cited evidence shown side by side) so a reader can spot-check rigor without running the pipeline.

### Failure-Mode Hardening

- [x] **HARD-01**: Narrow blanket `except Exception` blocks in the pipeline to specific exception classes, tagging each retained catch with the exception type and rationale.
- [x] **HARD-02**: Parse and honor `Retry-After` on rate-limit responses from Exa and Browserbase; add test coverage for the parsing path.
- [x] **HARD-03**: Add integration-test coverage for empty-enrichment (no Exa results) and citation-drop (writer emits unciteable claims) paths so they surface as graceful sheet rows rather than stack traces.
- [x] **HARD-04**: Decide on and ship a cached demo-bundle (e.g. `vcr.py` cassette) if and only if a real `make run` exceeds ~90 seconds on the synthetic CSV; otherwise document the decision to skip.

### Sheet Polish

- [x] **POLISH-01**: Render the four `AccountStatus` states with distinct sheet visuals (clean, low-groundedness, hook-suppressed, judge-failed); whole-row tinting so the demo audience reads the state at a glance.
- [x] **POLISH-02**: Make `[N]` citation markers hyperlinks into a `Sources` tab that lists the resolved URLs per row.
- [x] **POLISH-03**: Break the ICP score into per-axis columns (one column per rubric axis from `configs/icp.yaml`) so a viewer sees the breakdown, not just the total.
- [x] **POLISH-04**: Apply freeze panes and column widths sized for the demo so the Sheet reads cleanly on first open.

### Public-Repo Audit

- [ ] **REPO-01**: The hiring company name (case-insensitive) must appear in no tracked file content, no tracked file path, and no commit reachable from any ref. Real prospect domains in `inputs/accounts.csv` are acceptable by design; the pipeline must run against real companies. (Scope narrowed 2026-05-14; superseded the prior synthetic-CSV requirement. Former REPO-02, the broad vertical/vendor scrub, is withdrawn.)
- [ ] **REPO-03**: Run a deny-list grep (`git log --all -p`) for the hiring company name; record the hit list and decide explicitly whether to rewrite history or document as historical artifacts.
- [ ] **REPO-04**: Add a pre-commit hook that blocks the hiring company name (any case) in staged content or paths before it can ship.

### README and Loom Refresh

- [ ] **DEMO-01**: Re-record the Loom walkthrough against the final pipeline on the synthetic CSV; pin the commit SHA referenced in the README to the recorded state.
- [ ] **DEMO-02**: Rewrite the README so the first scroll answers what / why / proof (what the system does, why grounded outreach matters, proof in the form of eval numbers + a sheet screenshot); link to `evals/REPORT.md`.
- [ ] **DEMO-03**: Add an architecture diagram, a failure-mode gallery, the editable-rubric framing, and an honest "what this gets wrong" section to the README.

## v2 Requirements

Deferred. Acknowledged but not in this milestone.

### Specificity and Recency

- **AXIS-01**: Add specificity and recency as 1-5 judge axes alongside groundedness (only if AUDIT-03 defers them out of FIX-04).

### Eval Tooling

- **EVAL-V2-01**: Adopt `great-tables` for PNG-quality eval tables if Markdown rendering proves insufficient for the demo audience.

## Out of Scope

Explicitly excluded from this milestone. Each came up in research or PROJECT.md and was rejected with reasoning.

| Feature | Reason |
|---------|--------|
| Feedback loop from sales rejections | v2/v3 per PROJECT.md; requires production usage data we do not have |
| CRM trigger automation | v2/v3 per PROJECT.md; scope creep beyond a research POC |
| Webapp / dashboard / Slack bot | v3 per PROJECT.md; the Google Sheet is the deliverable surface |
| Multi-tenant config | v3 per PROJECT.md; single-operator tool by design |
| Custom prompt-caching layer | DeepSeek auto-caches; NVIDIA does not expose cache control; revisit only on provider change |
| `deepeval` / `ragas` / `promptfoo` / `inspect-ai` / `litellm` | Each replaces working code with a wrapper API; rejected in `.planning/research/STACK.md` |
| 1-10 numeric quality score | Judges drift on numeric scales per NeMo guidance; 1-5 categorical is locked |
| LLM-written persona narratives or executive summary cell | Anti-feature AF6/AF11 in FEATURES.md; sounds impressive, undermines rigor (ungroundable by design) |
| In-sheet feedback loop | Anti-feature AF7; same concerns as CRM automation |
| Vector store / embeddings layer | Anti-feature; current Exa retrieval is sufficient and grounded retrieval is the project value |
| Chat / Q&A over accounts | Anti-feature; out of scope for a research-output pipeline |
| Net-new pipeline features (any) | Milestone is "harden the existing pipeline for a demo-ready v1," not "extend it" |

## Traceability

Finalized by the roadmapper 2026-05-14. Each requirement maps to exactly one phase. The provisional mapping in the working-phase categories above was confirmed without changes.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 1 | Pending |
| AUDIT-02 | Phase 1 | Pending |
| AUDIT-03 | Phase 1 | Pending |
| FIX-01 | Phase 2 | Pending |
| FIX-02 | Phase 2 | Pending |
| FIX-03 | Phase 2 | Pending |
| FIX-04 | Phase 2 | Pending |
| FIX-05 | Phase 2 | Pending |
| FIX-06 | Phase 2 | Pending |
| EVAL-01 | Phase 3 | Complete |
| EVAL-02 | Phase 3 | Complete |
| EVAL-03 | Phase 3 | Complete |
| EVAL-04 | Phase 3 | Complete |
| NARR-01 | Phase 4 | Complete |
| NARR-02 | Phase 4 | Complete |
| NARR-03 | Phase 4 | Complete |
| HARD-01 | Phase 5 | Complete |
| HARD-02 | Phase 5 | Complete |
| HARD-03 | Phase 5 | Complete |
| HARD-04 | Phase 5 | Complete |
| POLISH-01 | Phase 6 | Complete |
| POLISH-02 | Phase 6 | Complete |
| POLISH-03 | Phase 6 | Complete |
| POLISH-04 | Phase 6 | Complete |
| REPO-01 | Phase 7 | Pending |
| REPO-02 | Phase 7 | Withdrawn (scope narrowed 2026-05-14) |
| REPO-03 | Phase 7 | Pending |
| REPO-04 | Phase 7 | Pending |
| DEMO-01 | Phase 8 | Pending |
| DEMO-02 | Phase 8 | Pending |
| DEMO-03 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 30 total
- Mapped to phases: 30 (finalized 2026-05-14)
- Unmapped: 0

---
*Requirements defined: 2026-05-14*
*Last updated: 2026-05-14 after roadmap finalized traceability*
