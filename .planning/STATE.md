---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: MCP Server Surface
current_phase: 12
current_phase_name: Full-Tier Tool, Resources & Prompt
status: ready_to_execute
stopped_at: Phase 12 planned (4 plans, 3 waves, checker passed)
last_updated: "2026-07-17T04:16:46.000Z"
last_activity: 2026-07-17
last_activity_desc: "Phase 12 planned: 4 plans in 3 waves, plan-checker passed on iteration 2, validation contract filled"
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 12
  completed_plans: 12
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15)

**Core value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader.
**Current focus:** Phase 12 — full-tier-tool-resources-prompt

## Current Position

Phase: 12 — Full-Tier Tool, Resources & Prompt
Plan: 0/4 complete
Status: Ready to execute (4 plans in 3 waves, plan-checker passed)
Last activity: 2026-07-17 — Phase 12 planned: 4 plans in 3 waves, plan-checker passed on iteration 2, validation contract filled

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 35
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
| 09 | 4 | - | - |
| 10 | 5 | - | - |
| 11 | 3 | - | - |

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
| Phase 09-pipeline-extraction-supporting-models P01 | 15min | 2 tasks | 2 files |
| Phase 09-pipeline-extraction-supporting-models P02 | 12min | 2 tasks | 4 files |
| Phase 09-pipeline-extraction-supporting-models P03 | 5min | 2 tasks | 2 files |
| Phase 09-pipeline-extraction-supporting-models P04 | 1min | 1 tasks | 0 files |
| Phase 10-stdio-mcp-server-thin-tier P01 | 4min | 3 tasks | 6 files |
| Phase 10 P02 | 6min | 3 tasks | 8 files |
| Phase 10 P3 | 1h13m | 2 tasks | 2 files |
| Phase 10 P4 | 10min | 2 tasks | 5 files |
| Phase 10 P5 | 4min | 2 tasks | 5 files |
| Phase 11 P01 | 8min | 2 tasks | 5 files |
| Phase 11 P02 | 4min | 3 tasks | 3 files |
| Phase 11 P03 | 4min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v1.1 adds an MCP server surface; sales-workflow brief rejected (2026-07-15) — MCP wraps existing seams at a fraction of the cost, stays on the groundedness differentiator, teaches the target skill
- Roadmap follows the research-endorsed dependency-driven build order, consolidated into 5 phases (extraction+models -> stdio thin tier -> limits+HTTP transport -> gated full tier+resources/prompt -> hosted deploy+docs)
- TEST-01 (cross-cutting test coverage) traced to the closing Phase 13 as the gate where full coverage across tiering/limits/evidence/errors is verifiable; each phase 9-12 still carries its own test acceptance per research's per-phase testing guidance
- HOST-06 (TransportSecuritySettings + fly.toml single-machine pin) traced to Phase 13 since the fly.toml half of the requirement cannot exist before the deploy phase
- Milestone framed as "demo-ready v1" (brownfield hardening, no net-new features) — v1.0
- Phase 1 is an audit, not a feature (groundedness state not yet fully understood) — v1.0
- README/Loom refresh deferred to Phase 8 (no mid-milestone re-recording) — v1.0
- Public-repo discipline elevated to PROJECT.md constraint with a dedicated Phase 7 — v1.0
- Phases 5, 6, 7 parallelizable after Phase 2 lands the `AccountStatus` schema; Phase 7 must precede Phase 8 — v1.0
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
- [Phase 09-01]: open_deps yields the existing frozen Deps dataclass verbatim; no new bundle type introduced (D-01) — Callers get a fully self-contained wiring seam without duplicating replay/record/live construction logic; MCP server inherits replay for free
- [Phase ?]: [Phase 09-02]: RawContext/collect_context promoted to module level (D-05/D-06); Enricher.enrich() delegates internally
- [Phase ?]: [Phase 09-02]: NullBrowserbase.render() returns None rather than raising BrowserbaseError (D-07 deviation) so it threads through collect_context's existing continue-with-Exa-only branch
- [Phase 09-03]: from_context takes about_text_min_chars as an explicit keyword arg rather than importing ABOUT_TEXT_MIN_CHARS, avoiding a models.py<->enrich.py import cycle (D-09)
- [Phase ?]: No code changes required in 09-04 -- all three gates (make test, make typecheck, make lint) passed cleanly on first run against the fully merged Wave-1 changeset
- [Phase ?]: [Phase 10-01]: mcp_tier() checks EXA_API_KEY before the mcp_demo_mode early return since no tier can retrieve without Exa
- [Phase ?]: [Phase 10-01]: mcp SDK SUS heuristic flag resolved as false positive via uv pip show + Project-URL metadata cross-check against official modelcontextprotocol/python-sdk repo
- [Phase 10]: [Phase 10-02]: news capped before justification numbering so indices and the news field never disagree
- [Phase 10]: [Phase 10-02]: get_account_evidence strips pydantic's 'Value error, ' prefix from ValidationError messages so client-visible text matches Account's own validator wording
- [Phase 10]: [Phase 10-02]: create_connected_server_and_client_session accepts a FastMCP instance directly and already calls initialize() internally
- [Phase 10]: Codex substituted for Claude Code in the real-client checkpoint after Claude session quota exhaustion — The user explicitly approved the substitution; Codex exercised the same local stdio MCP process with valid-invalid-valid calls and no fallback tools.
- [Phase 10]: Citation URLs are indivisible provenance; over-limit evidence units are dropped rather than rewritten.
- [Phase 10]: Account accepts only bare hostnames or root HTTP(S) URLs and validates ASCII DNS labels before retrieval.
- [Phase 10]: Filter indivisible invalid news provenance before applying NEWS_ITEM_MCP_CAP. — Rejected evidence units must not consume the client-visible count allowance.
- [Phase 10]: Keep Account as the sole domain boundary with standard-library IP and exact IDNA validation plus constant invalid-domain errors. — One shared boundary prevents provider calls and bounded wording prevents raw-input reflection.
- [Phase ?]: [Phase 11-01]: resolve_client_ip takes starlette.requests.Request | None directly, not an MCP Context, keeping limits.py dependency-free of the mcp SDK
- [Phase ?]: [Phase 11-01]: check_and_consume checks per-IP before the global daily cap so a doubly-exhausted caller sees the per-IP refusal message
- [Phase ?]: [Phase 11-02]: DemoClampedExa uses min() clamp semantics so a caller's smaller num_results request is never inflated
- [Phase ?]: [Phase 11-02]: D-07 exhaustion check extends the existing except (httpx.HTTPError, BrowserbaseError) branch body rather than adding a new except clause
- [Phase ?]: [Phase 11-03]: stateless_http=True locked for the HTTP transport per RESEARCH.md A1 (avoids long-lived per-session tasks on an unauthenticated public endpoint)
- [Phase ?]: [Phase 11-03]: TransportSecuritySettings passed explicitly rather than relying on the SDK's auto-built localhost wildcard, so the allowlist is greppable and Phase 13 has a single place to swap in the Fly hostname
- [Phase ?]: [Phase 11-03]: ASGI-transport HTTP tests enter the Starlette lifespan manually via asgi_app.router.lifespan_context(asgi_app), the exact context uvicorn runs; documented for Phase 13's deploy verification to reuse

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Research flags three one-time SDK-surface checks scoped to specific v1.1 phases, not carried risk: Phase 10 needs the `ToolError` import path and lifespan-once-per-process confirmed; Phase 11 needs the `streamable_http_app(middleware=...)` kwarg shape confirmed against the installed SDK; Phase 13 needs an early `fly launch` dry run before writing the Dockerfile/`fly.toml` in earnest.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-mrg | Document specificity and recency in judge rubric tab | 2026-07-14 | 6f8be41 | [260714-mrg-fix-rubric-tab-add-specificity-and-recen](./quick/260714-mrg-fix-rubric-tab-add-specificity-and-recen/) |
| 260716-p8r | Fix demo-mode Browserbase safety rail regression in MCP server wiring | 2026-07-17 | 4fbc1bf | [260716-p8r-fix-demo-mode-browserbase-safety-rail-re](./quick/260716-p8r-fix-demo-mode-browserbase-safety-rail-re/) |

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Eval rubric | Specificity and recency as 1-5 judge axes (AXIS-01) | v2, conditional on Phase 1 audit decision | 2026-05-14 |
| Eval tooling | `great-tables` for PNG-quality eval tables (EVAL-V2-01) | v2, conditional on Phase 4 Markdown sufficiency | 2026-05-14 |
| MCP server | PyPI/uvx packaging, hosted-endpoint auth, `structuredContent`, MCP Registry listing, company-name-to-domain resolution | v2, per v1.1 REQUIREMENTS.md Future Requirements | 2026-07-15 |

## Session Continuity

Last session: 2026-07-17T03:33:48.168Z
Stopped at: Phase 12 context gathered
Resume file: .planning/phases/12-full-tier-tool-resources-prompt/12-CONTEXT.md

## Operator Next Steps

- Run `/gsd-discuss-phase 12` to capture context for Phase 12 (Full-Tier Tool, Resources & Prompt)
- Then `/gsd-plan-phase 12` to plan it

</content>
