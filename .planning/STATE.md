---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 0
status: Awaiting next milestone
stopped_at: Phase 8 context gathered
last_updated: "2026-07-15T00:58:13.289Z"
last_activity: 2026-07-15
last_activity_desc: Milestone v1.0 completed and archived
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 34
  completed_plans: 33
  percent: 88
current_phase_name: readme-and-loom-refresh
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader.
**Current focus:** Phase 08 — readme-and-loom-refresh

## Current Position

Phase: Milestone v1.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-07-15 — Milestone v1.0 completed and archived

## Performance Metrics

**Velocity:**

- Total plans completed: 23
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 02 | 6 | - | - |
| 03 | 6 | - | - |
| 05 | 4 | - | - |
| 07 | 3 | - | - |
| 8 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 03 P03 | 10m | 1 tasks | 1 files |
| Phase 04-eval-narrative P01 | 6m | 2 tasks | 3 files |
| Phase 04-eval-narrative P02 | 7m | 2 tasks | 6 files |
| Phase 04-eval-narrative P03 | 12m | 3 tasks | 4 files |
| Phase 05-failure-mode-hardening P01 | 20m | 2 tasks | 6 files |
| Phase 05-failure-mode-hardening P02 | 12m | 2 tasks | 6 files |
| Phase 05-failure-mode-hardening P03 | 10m | 2 tasks | 1 files |
| Phase 05-failure-mode-hardening P04 | 22m | - tasks | - files |
| Phase 06-sheet-polish P01 | 7min | 2 tasks | 3 files |
| Phase 06-sheet-polish P02 | 6min | 2 tasks | 4 files |
| Phase 06-sheet-polish P03 | 3min | 1 tasks | 2 files |
| Phase 06-sheet-polish P04 | 5min | 2 tasks | 3 files |
| Phase 07-public-repo-audit P01 | 2m | 2 tasks | 2 files |
| Phase 07-public-repo-audit P02 | 1m | 1 tasks | 1 files |
| Phase 07-public-repo-audit P03 | 4min | 5 tasks | 3 files |
| Phase 08-readme-and-loom-refresh P01 | 25min | 2 tasks tasks | 2 files files |
| Phase 08-readme-and-loom-refresh P03 | 10m | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Milestone framed as "demo-ready v1" (brownfield hardening, no net-new features)
- Phase 1 is an audit, not a feature (groundedness state not yet fully understood)
- README/Loom refresh deferred to Phase 8 (no mid-milestone re-recording)
- Public-repo discipline elevated to PROJECT.md constraint with a dedicated Phase 7
- Phases 5, 6, 7 parallelizable after Phase 2 lands the `AccountStatus` schema; Phase 7 must precede Phase 8
- [Phase ?]: evals/COVERAGE.md: 18-cell matrix traced to named pitfalls; size is 25-40 derived from matrix
- [Phase ?]: Phase 4 Plan 1: --emit-log uses field-by-field payload construction
- [Phase ?]: Phase 4 Plan 2: Renderer pydantic loaders inherit _Frozen from src.models (extra=forbid for run-log rows; extra=allow on Calibration shell to tolerate emitter-side fields not displayed)
- [Phase ?]: Phase 4 Plan 2: _pair_claims_to_evidence emits '(no citations)' sentinel rows for uncited sentences in Section 6 to preserve paragraph-level integrity in worked failure case
- [Phase ?]: Phase 4 Plan 2: Synthetic-fixture-only template tests; committed evals/REPORT.md never touched by unit tests (Plan 03 will add integration test)
- [Phase 04 Plan 03]: Integration tests stage real committed artifacts via shutil.copy2 + os.utime on tmp_path copies; REPORT_PATH also monkeypatched to tmp_path so the committed evals/REPORT.md is never touched by test runs
- [Phase 04 Plan 03]: Pre-existing mypy errors in unrelated test files (test_eval_rubric.py, test_contacts.py, test_pipeline*.py) deferred per SCOPE BOUNDARY; targeted gate `mypy src evals tests/integration/test_report_freshness.py` exits clean
- [Phase 05-01]: retry_after_aware_wait reaches the response through state.outcome.exception() narrowed to httpx.HTTPStatusError — Only HTTPStatusError carries .response; the parent httpx.HTTPError does not
- [Phase 05-01]: functional Retry-After tests intercept asyncio.sleep — tenacity's _portable_async_sleep imports asyncio.sleep lazily on every retry; monkeypatch intercepts it; 0.05s test runtime confirms the real wait did not occur
- [Phase ?]: Phase 05-02: narrow tuples drop ValueError/TypeError from outer catches because src/enrich.py:122 and src/score.py:82 already catch those inside the stages
- [Phase ?]: Phase 05-02: D-04 honored by migrating test fixtures (FailingAnthropic, FlakyExa, _RaisingRubric) to raise APIError/httpx.HTTPError instead of re-broadening the catch tuples
- [Phase ?]: Phase 05-02: enrich-stage narrow tuple wraps across 8 lines under black's 100-char cap; cosmetic deviation from the plan's literal grep acceptance criterion, substance intact
- [Phase ?]: Phase 05 Plan 03: integration tests reach into src/sheets._build_row when the claim is graceful Sheet row
- [Phase ?]: Phase 05 Plan 03: max_tokens: int | None = None backfilled on all pre-existing fake synthesize methods (Rule 3 blocking-issue fix for file-scoped mypy strict acceptance criterion)
- [Phase ?]: Phase 05 Plan 04: replay+recording co-located in src/clients/replay.py; ReplayLLM/RecordingLLM accept role Literal[writer,judge] for DRY
- [Phase ?]: Phase 05 Plan 04: ReplayMissError intentionally OUTSIDE pipeline narrow exception tuples so missing fixtures crash, not degrade rows
- [Phase ?]: Phase 05 Plan 04: max_tokens is part of the LLM request hash so future capped calls do not silently collide with default-None fixtures
- [Phase ?]: Phase 05 Plan 04: functional test records bundle via real process_account through Recording* wrappers, not hand-crafted prompts, so the round-trip is robust to upstream edits
- [Phase 06-01]: clean result rows use no-fill while the Legend clean row receives explicit white RGB
- [Phase 06-01]: low_groundedness=1.00/0.97/0.80, hook_suppressed=1.00/0.90/0.78, judge_failed=0.88/0.88/0.88
- [Phase 06-01]: judge_failed is gray because it represents judge failure, not writer fabrication
- [Phase 06-01]: Rubric tab wording now points to AccountStatus and Legend instead of verdict colors
- [Phase 06 Plan 02]: Sources tab is per-run using <results_title>-sources with schema domain/index/summary/url/source.
- [Phase 06 Plan 02]: Hook and score justification cells use whole-cell HYPERLINK formulas targeting the first source row for the account.
- [Phase 06 Plan 02]: Results HEADERS shrank to 28 columns by dropping hook_N_citations; Sources tab owns citation URLs.
- [Phase 06 Plan 03]: Axis display labels are computed from configs/icp.yaml at write time while internal HEADERS remain snake_case for lookups and width mapping.
- [Phase 06 Plan 04]: WIDTH_CLASS_PX pixel values lock at narrow=110, medium=180, wide=400, extra=250; COLUMN_WIDTHS covers every HEADERS entry exactly once (13 narrow, 10 medium, 4 wide, 1 extra = 28).
- [Phase 06 Plan 04]: SheetsWriter calls _lookup_sheet_id once for the results tab and passes the int to the freeze, widths, and wrap helpers so the writer issues a single GET to discovery for all three formatting passes.
- [Phase 06 Plan 04]: Empty scored list still issues all three formatting requests so a future-added row inherits the formatting on subsequent runs; the empty wrap range (startRowIndex=1, endRowIndex=1) is a Sheets-API-tolerated no-op.
- [Phase ?]: [Phase 07 Plan 01]: verify_public_repo.py duplicates _load_patterns() verbatim rather than extracting a shared helper; CONTEXT.md deferred says consolidation is not Phase 7's call
- [Phase ?]: [Phase 07 Plan 01]: Exit codes 0=clean, 1=hits, 2=denylist missing or empty (D-Claude's-Discretion)
- [Phase ?]: [Phase 07 Plan 01]: Single stdout print() call locked by I3 grep gate to enforce THR-01 (no raw match text)
- [Phase 07 Plan 02]: Patched _staged_content seam directly (PATTERNS.md option a) rather than refactoring main() to take a content-provider; lower-risk for 3 test cases
- [Phase 07 Plan 02]: FAKE_TERM = 'fake-denylisted-term-for-test' is the publishable placeholder per CONTEXT.md D-05 / THR-02; live denylisted term never enters test source
- [Phase 07 Plan 02]: Happy-path test added beyond D-06's two parametrized cases as cheap insurance against false-positive regressions (CLAUDE.md "err on the side of too many tests")
- [Phase ?]: [Phase 07 Plan 03]: REPO-04 traceability flip landed in Plan 07-02 commit 8924798 ahead of the atomic close; FINDINGS.md table still covers all three requirements
- [Phase ?]: [Phase 07 Plan 03]: FINDINGS.md kept em-dash-free for consistency with the README change in the same commit
- [Phase ?]: [Phase 07 Plan 03]: Atomic close commit 1a4bca5 stages FINDINGS.md via git add -f (gitignored .planning/) plus normal git add for REQUIREMENTS.md and README.md
- [Phase ?]: [Phase 08 Plan 01]: fixtures/demo-bundle/ is empty in Phase 5 by design; Phase 8 D-06 fallback is not viable. Plan 02 captures all four AccountStatus PNGs from real make run outputs.
- [Phase ?]: [Phase 08 Plan 01]: SHA-pin placeholder is an HTML comment marker (<!-- SHA-PIN: ... -->) below the Loom embed so Plan 04 has a deterministic grep anchor.
- [Phase ?]: [Phase 08 Plan 01]: README failure-mode gallery uses stacked H4 sections with image plus italic caption blocks per D-05; chosen over a 2x2 table for readability.
- [Phase ?]: [Phase 08 Plan 01]: Eval section's (populated after first run) code-block placeholder replaced with a one-line headline number reusing the proof-bullet phrasing for consistency per Claude's Discretion in 08-CONTEXT.md.
- [Phase ?]: [Phase 08 Plan 03]: README Plan-01 scaffold's inline-[N] citation claim did not match shipping implementation; Plan 03 rewrote the citations paragraph plus three adjacent surfaces to describe per-claim cited_indices metadata + rapidfuzz coverage gate + whole-cell HYPERLINK formula
- [Phase ?]: [Phase 08 Plan 03]: Failure-mode gallery degraded to two captured states with a one-line gap note rather than broken markdown image refs; the four-state prose contract above the gallery stays intact

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Phase 1's six open questions (sentence-coverage shape, history rewrite vs document, specificity/recency timing, demo-bundle caching need, `great-tables` yes/no, label migration vs re-label) will be resolved within the audit itself, not blockers.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-mrg | Document specificity and recency in judge rubric tab | 2026-07-14 | 6f8be41 | [260714-mrg-fix-rubric-tab-add-specificity-and-recen](./quick/260714-mrg-fix-rubric-tab-add-specificity-and-recen/) |

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Eval rubric | Specificity and recency as 1-5 judge axes (AXIS-01) | v2, conditional on Phase 1 audit decision | 2026-05-14 |
| Eval tooling | `great-tables` for PNG-quality eval tables (EVAL-V2-01) | v2, conditional on Phase 4 Markdown sufficiency | 2026-05-14 |

## Session Continuity

Last session: 2026-06-04T02:34:27.858Z
Stopped at: Phase 8 context gathered
Resume file: None

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
