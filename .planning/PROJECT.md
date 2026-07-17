# poc_scraper

## What This Is

A generic account-research prototype. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP fit score against an editable rubric, top-3 buyer personas, and grounded outreach hooks per persona. "POC" means both Point of Contact (the right person to reach in an account) and Proof of Concept. The ICP rubric lives in `configs/icp.yaml` so the pipeline can be retargeted at any vertical without code changes.

## Core Value

Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader. If everything else slips, this must hold — it is the whole story.

## Shipped Milestone: v1.1 MCP Server Surface

**Status:** SHIPPED 2026-07-17 (Phases 9-13). Live hosted thin-tier endpoint on Oracle Cloud Always Free; full details archived in `.planning/milestones/v1.1-ROADMAP.md`.

**Goal (as shipped):** Expose the grounded account-research pipeline as a public MCP server: a hosted URL anyone can paste into Claude Desktop for capped, evidence-cited demo research, plus a full BYOK stdio server for cloned-repo users.

**Target features:**
- Tiered FastMCP server in `src/mcp_server/`: thin tier (evidence tool, rubric + eval-report resources, research prompt; Exa-only) always registered; full-pipeline tool gated on BYOK writer/judge/Browserbase keys
- Both transports from one entry point: stdio (local clients) and streamable HTTP (hosted)
- Hosted demo on Fly.io behind `MCP_DEMO_MODE`: 5 evidence calls per IP per hour, 25 per UTC day globally, Exa results clamp, structured rationing errors, in-memory counters
- Supporting refactors: `open_deps()` extraction from `pipeline.main()`, `collect_context()` promotion in `src/enrich.py`, `NullBrowserbase`, frozen `EvidencePack` model
- CLAUDE.md charter amendment (adds the `mcp` SDK to the locked stack), README MCP section, tests across all 5 layers

**Design authority:** `docs/superpowers/specs/2026-07-15-mcp-server-design.md` (commit `3a46444`). Economics decided: operator's hard-capped Exa key (unbilled $14.20 credit pool) funds demo retrieval; connectors' own Claude credits fund the reasoning. Server is read-only: no Sheets writes, no batch tools, no rubric editing. PyPI packaging and endpoint auth deferred.

## Current Milestone: v1.2 Agent-Driven ICP Scoring

**Goal:** Let a connecting agent (Codex/Claude) score a company domain against the ICP rubric using its own reasoning on the hosted keyless thin tier, while the server guarantees the scoring math deterministically (a pure `score_account` tool, no server-side LLM).

**Target features:**
- New `score_account` MCP tool on thin and full tiers: agent supplies 1-5 per axis (plus optional per-axis reason strings); server computes weighted total + verdict by reusing `compute_total` / `verdict_for` and the frozen `RubricBreakdown` (4 fixed axes, unchanged)
- Pure arithmetic: no LLM, no Exa, no keys, no I/O; does NOT consume the demo rate-limit quota; `readOnlyHint: true`; sanitized one-line validation errors per the existing error-wrapper pattern
- `research_account` prompt updated to orchestrate the full flow: `get_account_evidence` -> read `icp://rubric` -> score each axis 1-5 with [N] citations -> call `score_account` -> present the verdict
- Optional `news_days` parameter on `get_account_evidence` to tune the Exa news lookback (clamped; threads through `collect_context` to `ExaClient.search_news(days=...)`)
- Landing page (`deploy/oracle/setup.sh` index.html) + README MCP section updated with the honest hybrid framing: the judgment stays grounding-by-instruction (agent must cite [N] per axis), the scoring math becomes grounding-by-construction (the server cannot return an arithmetically wrong score)

**Scope decision (conscious expansion):** This expands the thin tier beyond its original "evidence-only" framing, but it stays read-only, keyless, and costless (a deterministic helper, not a server-side pipeline). Arbitrary-axis rubrics remain deferred; the 4-axis `RubricBreakdown` model is not touched.

## Requirements

### Validated

<!-- Inferred from the existing codebase via .planning/codebase/ map. These shipped and work. -->

- ✓ Async pipeline orchestrating enrich → score → contacts → outreach → sheets — existing (`src/pipeline.py`)
- ✓ Firmographic enrichment + recent context via Exa with Browserbase fallback — existing (`src/enrich.py`, `src/clients/`)
- ✓ ICP rubric scoring driven by `configs/icp.yaml` (verticals swappable without code) — existing (`src/score.py`)
- ✓ Top-3 persona inference per account — existing (`src/contacts.py`)
- ✓ Grounded outreach hook generation with citation extraction — existing (`src/outreach.py`)
- ✓ Google Sheets writer with service-account auth — existing (`src/sheets.py`)
- ✓ Configurable LLM provider (DeepSeek default, NVIDIA Build fallback) — existing (`src/config.py`, `src/clients/`)
- ✓ LLM-as-judge eval with 1-5 categorical rubric over `evals/labeled.jsonl` — existing (`evals/`)
- ✓ 5-layer test strategy (unit / functional / integration / smoke / edge) — existing (`tests/`)
- ✓ Strict mypy + pre-commit (black, ruff) + CI split — existing (`.pre-commit-config.yaml`, `pyproject.toml`)
- ✓ README + Loom walkthrough as the demo artifact — existing (`README.md`)

<!-- Shipped in the demo-ready v1.0 MVP milestone (Phases 1-8, 2026-07-15). -->

- ✓ Groundedness audit producing a findings document that drove the roadmap — v1.0 (Phase 1)
- ✓ Groundedness gaps closed: shared citation parser, per-claim rapidfuzz suppression, four-state AccountStatus — v1.0 (Phase 2)
- ✓ Expanded, coverage-documented labeled eval set with cross-family judge calibration — v1.0 (Phase 3)
- ✓ Eval narrative artifact (`evals/REPORT.md`, 2.73/5.0 holdout headline) legible to a non-author reader — v1.0 (Phase 4)
- ✓ Failure modes hardened: Retry-After handling, narrowed exception catches, replay/record machinery — v1.0 (Phase 5)
- ✓ Sheet polish: four-state row colors + Legend, per-run Sources tab with HYPERLINK citations, per-axis columns, freeze panes — v1.0 (Phase 6)
- ✓ Public-repo scrub (history rewrite + pre-commit name guard) — v1.0 (Phase 7)
- ✓ Front-loaded README + recorded walkthrough pinned to a specific commit — v1.0 (Phase 8)

<!-- v1.1 MCP Server Surface (shipped 2026-07-17). -->

- ✓ Pipeline seams extracted for MCP reuse: `open_deps()` wiring seam (INTEG-01), public `collect_context()`/`RawContext` + `NullBrowserbase` Exa-only path (INTEG-02), frozen `EvidencePack` with `retrieval_status` honesty field (INTEG-03); CLI behavior unchanged — v1.1 (Phase 9, 2026-07-16)
- ✓ Stdio thin-tier MCP server: `get_account_evidence` returns numbered cited evidence verified against a real client, stderr-only logging, `make smoke-mcp` real-subprocess gate (MCP-01, MCP-06, MCP-07, HOST-01, TEST-02) — v1.1 (Phase 10, 2026-07-16)
- ✓ Streamable HTTP transport from one entry point plus demo-mode rate limits: `DemoLimiter` (per-IP hour window + UTC-day global cap, race-safe, injected clock), fail-closed `Fly-Client-IP` resolution, explicit `TransportSecuritySettings` allowlist (HOST-02, HOST-04) — v1.1 (Phase 11, 2026-07-16)
- ✓ ICP rubric + eval report as `icp://rubric` / `icp://eval-report` resources and the `research_account` guided prompt on every tier; tier-gated `research_account_full` BYOK tool (hidden below full tier, complete `ScoredAccount` JSON, `run_eval` honesty, per-stage progress, sanitized errors) (MCP-02/03/04/05) — v1.1 (Phase 12, 2026-07-17)
- ✓ Public hosted deploy (Oracle Cloud Always Free, live) with hardened/sanitized error payloads and a single-machine global rate-limit invariant; CLAUDE.md charter + README MCP section synced to the shipped surface (HOST-03, HOST-05, HOST-06, DOCS-01, DOCS-02, TEST-01) — v1.1 (Phase 13, 2026-07-17)

### Active

<!-- v1.2 Agent-Driven ICP Scoring. REQ-IDs defined in .planning/REQUIREMENTS.md. -->

- Agent-driven deterministic ICP scoring via a `score_account` MCP tool on the thin and full tiers (server-guaranteed math over the existing rubric)
- `research_account` prompt orchestrates evidence -> rubric -> cited axis scores -> `score_account` -> verdict
- Optional clamped `news_days` lookback parameter on `get_account_evidence`
- Landing page + README document the new scoring capability with the hybrid grounding framing

### Out of Scope

<!-- v2/v3 per CLAUDE.md. Restated here so the roadmapper does not drift into them. -->

- Feedback loop from sales rejections — v2, requires production usage data we do not have
- CRM trigger automation — v2, scope creep beyond a research POC
- Webapp / dashboard / Slack bot — v3, the Google Sheet is the deliverable surface (the v1.1 MCP server is a protocol adapter over existing seams, not a webapp; explicitly in scope per the 2026-07-15 design spec)
- Multi-tenant config — v3, single-operator tool by design
- Custom prompt-caching layer — DeepSeek auto-caches at 1/10 input price on hits, NVIDIA does not expose cache control; revisit only if moving to a provider where explicit cache control is necessary
- Net-new features beyond hardening the existing pipeline for a demo-ready v1 — out of scope for this milestone, not the project

## Context

- **Brownfield project.** The pipeline is built and runs end-to-end. This milestone hardens what exists rather than building new capabilities. The codebase map at `.planning/codebase/` is the authoritative reference for current state.
- **Demo as the deliverable artifact.** The README + Loom walkthrough is the primary artifact (hiring audience); a live run on a real CSV is the secondary artifact (GTM audience). Both must be solid, with the README/Loom as the primary surface a reader encounters first.
- **Two demo-killers identified up front.** (1) An ungrounded outreach claim that traces to nothing — the most damaging failure for an AI-product story. (2) Eval numbers that do not tell a coherent story — thin dataset, drifty judge, or no narrative artifact making the rigor visible. The roadmap is structured around eliminating both.
- **Audit before fix.** Groundedness state is not yet fully understood — Phase 1 is an audit that outputs findings, and subsequent phases close the gaps the audit surfaces. This avoids planning fixes for problems that may not exist and missing problems that do.
- **Standard milestone size.** Targeting 5-8 phases over roughly 2-4 weeks of focused work. Scope is intentionally tight around the two demo-killers plus crash-resilience, sheet polish, and the closing README/Loom refresh.
- **Stack is locked per CLAUDE.md.** Python 3.11+, uv, OpenAI-compatible LLM clients (DeepSeek/NVIDIA), Exa + Browserbase, Google Sheets API, strict mypy. Do not drift.

## Constraints

- **Public repo discipline**: No specific company, vendor, or vertical names in code, prompts, configs, commit messages, or eval data — The repo is intended to be public; a leak makes it unshareable and kills the hiring artifact. Per CLAUDE.md, the ICP definition stays abstract and vertical-specific runs happen by editing `configs/icp.yaml` locally.
- **CLAUDE.md scope is the boundary**: No feedback loop, CRM automation, webapp/dashboard, multi-tenant config, or custom caching layer — These are v2/v3 per the locked project scope. Restating here so the roadmapper does not drift toward them when audit findings surface adjacent ideas.
- **Stack is locked**: Python 3.11+, uv, DeepSeek/NVIDIA OpenAI-compatible clients, Exa primary + Browserbase fallback, Google Sheets API, strict mypy, conventional commits, no emojis in code or commit messages, no em-dashes in published markdown — Per CLAUDE.md; changes require explicit discussion.
- **Grounded claims only**: Every outreach claim must trace to a retrieval; unciteable claims get dropped — This is the project's core value; it is a constraint on every code path that produces user-visible text, not a feature to be toggled.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Milestone framed as "demo-ready v1" rather than "harden" or "add features" | Polish-and-close-gaps fits the brownfield state; new features would invite scope creep into v2/v3 territory | Good, shipped v1.0 |
| Phase 1 is an audit, not a feature | Groundedness state is not yet fully understood; planning fixes without auditing risks solving the wrong problems | Good, shipped v1.0 |
| README/Loom refresh deferred to the closing phase | Re-recording mid-milestone wastes effort; the artifact should reflect the final pipeline output | Good, shipped v1.0 |
| Both primary (hiring) and secondary (GTM) demo audiences are in scope, with hiring primary | README+Loom serves both; live-run polish covers the secondary audience without separate work streams | Good, shipped v1.0 |
| Public-repo discipline elevated from CLAUDE.md guidance to a PROJECT.md constraint | A leak kills the primary artifact's purpose; deserves a dedicated audit phase rather than ad-hoc review | Good, shipped v1.0 |
| Phase 7 narrowed from broad vertical/vendor/synthetic scrub to a hiring-company-name-only audit (2026-05-14) | The pipeline must run against real companies to demonstrate it works; real prospect domains and incidental vendor names are acceptable. The only fatal leak is the hiring company name. REPO-02 withdrawn; REPO-01 redefined | — Decided 2026-05-14 |
| History rewritten and force-pushed to purge the hiring company name (2026-05-14) | The name was baked into ~40 commits of source/prompts plus a commit message on origin/main; git filter-repo replaced it, force-pushed, working repo reset, stale branches deleted, original preserved at ../poc_scraper-FULL-BACKUP.bundle. Repo had 0 forks; exposure closed. Satisfies REPO-03 (rewrite chosen over document) | — Done 2026-05-14 |
| Pre-commit company-name guard added in lieu of detect-secrets/gitleaks (2026-05-14) | scripts/check_public_discipline.py reads a local-only gitignored .secrets-denylist so the term never enters the public repo; no-ops if absent. Generic secret scanners do not target a project-specific name. Satisfies REPO-04 | — Done 2026-05-14 |
| v1.1 adds an MCP server surface; sales-workflow brief rejected (2026-07-15) | MCP wraps existing seams at a fraction of the cost of the review-queue/CRM product, stays on the groundedness differentiator, and teaches the target skill (building MCPs). Demo economics: operator's capped Exa key funds retrieval, caller's Claude credits fund reasoning. Charter amended to add the mcp SDK | Good, shipped v1.1 (2026-07-17) |
| Hosted deploy target pivoted Fly.io -> Oracle Cloud Always Free (2026-07-17) | Fly.io (card required) and HF Docker Spaces (PRO required) both gated previously-free container hosting behind payment mid-phase; Oracle Always Free runs the single container 24/7 at $0/mo. fly.toml + HF push kept as documented, unverified-live alternatives | Good, live at `https://170.9.7.144.sslip.io/mcp` |
| Post-ship hardening: two Codex reviews + `/gsd-secure-phase` on the public MCP surface (2026-07-17) | A publicly-exposed endpoint warrants adversarial review beyond per-phase verification; found and fixed a live `Fly-Client-IP` rate-limit spoof (Caddy did not overwrite the trusted header after the Fly->Oracle pivot) plus 6 lower-severity issues | Good, 7 fixed with tests; 14/14 threats closed |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current State

Shipped the demo-ready v1.0 MVP (8 phases, 2026-07-15). The pipeline is grounded end-to-end (unciteable claims dropped before the sheet), the eval rigor is legible via `evals/REPORT.md` (2.73/5.0 holdout), failure modes are hardened, the Google Sheet output is demo-legible, the public repo is scrubbed, and the README + recorded walkthrough are live and pinned to commit `f868a09`.

Shipped milestone v1.1 (MCP Server Surface) — all 5 phases (9-13, 2026-07-17). The grounded pipeline is now an MCP server: Phase 9 extracted the `open_deps()`/`collect_context()`/`NullBrowserbase`/`EvidencePack` seams (reused, not duplicated); Phase 10 shipped the stdio thin tier (`get_account_evidence`, real-client verified); Phase 11 added `DemoLimiter` rationing + fail-closed `Fly-Client-IP` resolution + streamable HTTP from one entry point; Phase 12 completed the surface with `icp://rubric` / `icp://eval-report` resources, the `research_account` prompt, and the tier-gated `research_account_full` BYOK tool; Phase 13 deployed a public thin-tier endpoint (Oracle Cloud Always Free, live at `https://170.9.7.144.sslip.io/mcp`) with hardened error payloads and synced the CLAUDE.md/README charter.

Post-execution, Phase 13 additionally received two adversarial Codex reviews (7 findings fixed with tests, incl. a live Caddy `Fly-Client-IP` spoofing fix), a formal `/gsd-secure-phase 13` audit (14/14 STRIDE threats closed), and a passing milestone audit (20/20 requirements, 6/6 cross-phase flows wired, 5/5 Nyquist-compliant). Full offline suite green: 512 pytest, strict mypy, ruff, black, verify-public-repo 0 hits. Next: `/gsd-new-milestone` to scope the next version.

---
*Last updated: 2026-07-17 at v1.2 milestone start (Agent-Driven ICP Scoring). v1.0/v1.1 history unchanged above.*
