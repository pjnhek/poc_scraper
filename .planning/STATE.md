---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Agent-Driven ICP Scoring
current_phase: 2
status: Awaiting next milestone
stopped_at: Phase 14 complete (security 9/9 closed, UAT 13/13 passed), milestone v1.2 at 100%
last_updated: "2026-07-18T04:32:18.384Z"
last_activity: 2026-07-18
last_activity_desc: "Quick task 260718-ev4: documented hosted MCP usage and redeployed the box from v1.1 to v1.2"
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
current_phase_name: deterministic-scoring-guided-flow
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18)

**Core value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader.
**Current focus:** Close milestone v1.2 (all phases complete)

## Current Position

Phase: Milestone v1.2 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-07-18 — Quick task 260718-ev4: documented hosted MCP usage, redeployed the hosted demo from v1.1 to v1.2

## Performance Metrics

**Velocity:**

- Total plans completed: 47
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
| 12 | 4 | - | - |
| 13 | 5 | - | - |
| 14 | 3 | - | - |

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
| Phase 12 P01 | 12min | 2 tasks | 2 files |
| Phase 12 P02 | 20min | 2 tasks | 3 files |
| Phase 12 P03 | 15min | 2 tasks | 4 files |
| Phase 12 P04 | 7min | 2 tasks | 1 files |
| Phase 13 P01 | 15min | 2 tasks | 5 files |
| Phase 13 P02 | 18min | 3 tasks | 5 files |
| Phase 13 P03 | 5min | 2 tasks | 1 files |
| Phase 13-hosted-deploy-docs-close P04 | 185min | 3 tasks | 1 files |
| Phase 13 P05 | 20min | 2 tasks | 2 files |
| Phase 14 P01 | 12min | 2 tasks | 5 files |
| Phase 14 P02 | 12min | 2 tasks | 5 files |
| Phase 14 P03 | 14min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v1.2 roadmapped as a single phase (Phase 14): the design is locked (deterministic `score_account` tool reusing `compute_total`/`verdict_for`, clamped `news_days`, prompt + docs updates), the code/tests/docs changes are all tightly coupled edits to the same `src/mcp_server/` module with no real sequencing dependency — splitting would invent structure the work does not need (2026-07-17)
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
- [Phase ?]: elif not run_eval: sits between hook_suppressed and eval_score is None checks so a deliberate judge skip never reads as judge_failed/low_groundedness (D-02)
- [Phase ?]: on_stage fires with no try/except around it; a raising callback propagates rather than being swallowed (RESEARCH OQ2)
- [Phase ?]: Deps.limiter typed bare None (not Optional[limiter type]) to keep src/pipeline.py free of any src.mcp_server import
- [Phase ?]: [Phase 12-02]: Sanitized resource-failure messages are resource-specific (rubric vs eval report) so callers can tell which resource degraded, without leaking the filesystem path
- [Phase ?]: [Phase 12-02]: research_account prompt points at icp://rubric and get_account_evidence rather than embedding rubric content, keeping icp.yaml the single editable source of truth
- [Phase ?]: [Phase 12-03]: EvidenceDeps uses @property members for covariant limiter typing so ThinDeps and the extended pipeline Deps both satisfy it under strict mypy without inheritance
- [Phase ?]: [Phase 12-03]: make_full_lifespan is a one-line delegation to open_deps (not an independent second client stack) so the full-tier server shares one httpx pool and inherits replay/record branching
- [Phase ?]: [Phase 12-03]: tier is threaded through build_server as an explicit parameter derived from resolve_and_log_tier, never re-derived from the settings=None/not-None check, so MCP_DEMO_MODE hides research_account_full regardless of transport
- [Phase ?]: [Phase 12-04]: HappyWriterLLM/HappyJudgeLLM kept as separate fakes so judge invocation count is independently assertable for D-02
- [Phase ?]: [Phase 12-04]: title=None on fake about-page ExaResult mirrors test_pipeline_failures.py so justification summary clears the rapidfuzz groundedness_suppress_threshold gate reliably
- [Phase ?]: mcp_public_hostname sources allowlist entries additively; wildcard binds (0.0.0.0, ::) excluded from the bind-derived allowlist entry entirely (D-07)
- [Phase ?]: D-06 guard checks transport==http and mcp_http_host not in loopback set and not mcp_public_hostname, matching the WR-03 guard shape and call-site convention exactly
- [Phase ?]: MCP_PUBLIC_HOSTNAME .env.example documentation deferred to docs/DEPLOY.md (plan 13-02) because .env.example is outside this session's file-access permissions
- [Phase ?]: fly launch dry run degraded gracefully (13-02): flyctl installed via brew but no Fly.io account was available in the automated session; only the smoke-checks flag was confirmed without auth, remaining 4 observations deferred to plan 13-04's deploy preflight
- [Phase ?]: Dockerfile copies README.md into the uv sync layer (13-02) because hatchling's readme field is read during project install, not just dependency install
- [Phase 13-03]: HOST-05 offline regression coverage lives in tests/integration/test_mcp_error_sanitization.py with a BANNED_SUBSTRINGS constant checked against all three get_account_evidence error paths; TEST-01 offline gate confirmed green with no new mypy overrides
- [Phase 13-04]: Hosted deploy target switched from Fly.io to Hugging Face Spaces mid-plan; `fly apps create` requires a payment method on file even for free-tier usage and the operator declined. HF Spaces (free CPU-basic Docker Space, no card) is now primary; Fly.io artifacts (Dockerfile shared, fly.toml) stay committed as a documented, unverified-live alternative in docs/DEPLOY.md's appendix. `make deploy` now wraps `scripts/push_hf_space.py`; `make deploy-fly` is the prior Fly target.
- [Phase 13-04]: D-01/D-03 (suspend-on-idle cost posture, single-machine pin) map onto HF's free CPU-basic Spaces as: exactly one container replica by construction (no scale knob to misconfigure) and sleep-after-inactivity with cold-start-on-wake (documented as ~48h by HF, subject to change), same DemoLimiter-counters-reset-on-restart tradeoff as Fly's suspend behavior.
- [Phase 13-04]: scripts/push_hf_space.py assembles an explicit file allowlist (mirrors .dockerignore) into a scratch dir and pushes via `hf upload` (single-commit, not git push); verified locally with huggingface_hub's filter_repo_objects that the allowlist excludes tests/, .planning/, .env, credentials.json, and the project's own top-level README.md.
- [Phase 13-04]: HF Spaces Docker/Gradio SDK space creation now returns 402 Payment Required without a PRO subscription (confirmed 2026-07-17 against the live API with a write-scoped token; a throwaway dataset repo create/delete on the same token succeeded, isolating this to the SDK-type gate, not a token-scope problem). Only "static" SDK spaces are free; not viable for a Dockerized MCP server. Both Fly.io (card required) and HF Spaces (PRO required) now gate their previously-free Docker hosting behind payment; operator decision needed before Task 2 can proceed.
- [Phase 13-04]: Deploy-target decision chain resolved: Fly.io (card required, 402-equivalent) -> HF Spaces (PRO required, 402) -> Oracle Cloud Always Free (chosen 2026-07-17; card required at signup for identity verification only, $0/mo thereafter unless explicitly upgraded to Pay As You Go). Oracle is now primary in docs/DEPLOY.md; HF and Fly stay committed as labeled appendices, each annotated with why it is not primary.
- [Phase 13-04]: D-01 (idle-behavior cost intent) reinterpreted for a raw VM with no suspend primitive: the Always Free VM runs 24/7 at $0/month instead of idling to hit the cost goal; DemoLimiter counters persist across quiet periods and reset only on redeploy/crash, same tradeoff class as the Fly/HF suspend-reset behavior.
- [Phase 13-04]: deploy/oracle/setup.sh is deliberately the single artifact used both as OCI instance user-data (cloud-init runs a plain `#!/bin/bash` user-data script directly, no separate cloud-init YAML) and as a manually re-run redeploy/secret-pickup script over SSH, to avoid drift between first-boot and redeploy behavior (DRY).
- [Phase 13-04]: Chose Ubuntu 22.04 (apt-based) over Oracle Linux for deploy/oracle/setup.sh to keep the script single-OS; image OCID is looked up dynamically per shape (`oci compute image list --shape ...`) so the ARM (A1.Flex) vs AMD (E2.1.Micro) image split never needs a hand-maintained OCID.
- [Phase 13-04]: setup.sh adds a 2GB swapfile when total RAM is below 2GB (the E2.1.Micro Always Free fallback has 1GB) as a Rule 2 defensive addition, since `docker build`'s `uv sync` step is the most likely OOM point on that shape.
- [Phase 13-04]: Container binds to 127.0.0.1:8000 only on the Oracle VM (not the public interface); Caddy is the sole public-facing process (defense in depth beyond what the managed Fly/HF edges provide by default).
- [Phase 13-04]: D-14 live real-client verification passed: official MCP Python SDK client retrieved cited evidence for notion.so (HOST-03) and got a clean one-line sanitized error for an invalid domain (HOST-05 live half) against https://170.9.7.144.sslip.io/mcp
- [Phase 13-04]: Live URL for 13-05's README Try it live section: https://170.9.7.144.sslip.io/mcp
- [Phase 13-04]: HOST-06 live half confirmed: exactly one instance/container, forged Host header rejected at both Caddy edge and the app's own TransportSecuritySettings allowlist
- [Phase ?]: Plan 13-05 substituted the confirmed live Oracle Cloud endpoint (https://170.9.7.144.sslip.io/mcp) for the plan's fly.dev placeholder throughout README.md, per the 13-04 deploy-target pivot
- [Phase ?]: CLAUDE.md Makefile-targets mention lists provision-oracle/deploy-oracle/deploy-hf/deploy-fly (the real current targets) instead of the plan's generic deploy target
- [Phase ?]: score_account has zero ctx/Context[...] parameters by construction, structurally proving it cannot reach DemoLimiter, exa, or browserbase (SCORE-02)
- [Phase ?]: Range validation lives in the tool body (D-04); type validation is left to the MCP SDK's own arg-model, asserted only for isError=True and absence of banned substrings
- [Phase ?]: news_days threads through exactly three hops (get_account_evidence -> build_evidence_pack -> collect_context -> exa.search_news); collect_context's days=90 keyword-only default preserves Enricher.enrich's existing 90-day behavior
- [Phase ?]: research_account rewritten as an explicit six-step numbered flow ending in score_account and personas/hooks; empty-evidence skip rule (unscoreable/drop/fabricate wording) lives inline in step 1, not as a separate step
- [Phase ?]: README/Oracle landing-page docs updated with score_account hybrid framing (judgment grounding-by-instruction, arithmetic grounding-by-construction); full offline gate green, closing v1.2 (SCORE-01..03, PROMPT-01, EVID-01, DOCS-03/04, TEST-03/04)
- [Phase ?]: test_mcp_scoring.py black-reformatted as part of the TEST-03 gate (pre-existing Plan 01 formatting drift, fixed via make format per Task 2's own instructions)

### Pending Todos

None yet.

### Blockers/Concerns

None

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-mrg | Document specificity and recency in judge rubric tab | 2026-07-14 | 6f8be41 | [260714-mrg-fix-rubric-tab-add-specificity-and-recen](./quick/260714-mrg-fix-rubric-tab-add-specificity-and-recen/) |
| 260716-p8r | Fix demo-mode Browserbase safety rail regression in MCP server wiring | 2026-07-17 | 4fbc1bf | [260716-p8r-fix-demo-mode-browserbase-safety-rail-re](./quick/260716-p8r-fix-demo-mode-browserbase-safety-rail-re/) |
| 260718-ev4 | Document hosted MCP usage and redeploy the box from v1.1 to v1.2 | 2026-07-18 | 605691f | [260718-ev4-mcp-usage-docs-redeploy](./quick/260718-ev4-mcp-usage-docs-redeploy/) |

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Eval rubric | Specificity and recency as 1-5 judge axes (AXIS-01) | v2, conditional on Phase 1 audit decision | 2026-05-14 |
| Eval tooling | `great-tables` for PNG-quality eval tables (EVAL-V2-01) | v2, conditional on Phase 4 Markdown sufficiency | 2026-05-14 |
| MCP server | PyPI/uvx packaging, hosted-endpoint auth, `structuredContent`, MCP Registry listing, company-name-to-domain resolution | v2, per v1.1 REQUIREMENTS.md Future Requirements | 2026-07-15 |
| MCP server | Per-call rubric weights/descriptions override for `score_account`; arbitrary-axis rubrics | v2, per v1.2 REQUIREMENTS.md Future Requirements | 2026-07-17 |
| Deploy process | No check that the hosted endpoint matches `origin/main` at milestone close. v1.2 sat undeployed for a day while the README advertised `score_account` as live (found in 260718-ev4). Candidate: milestone-close step probing live `tools/list` against the local inventory | Open, size with v1.3 scope | 2026-07-18 |

## Session Continuity

Last session: 2026-07-18T03:05:00Z
Stopped at: Phase 14 complete (security 9/9 closed, UAT 13/13 passed), milestone v1.2 at 100%
Resume file: None

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
