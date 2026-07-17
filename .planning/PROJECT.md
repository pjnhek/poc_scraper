# poc_scraper

## What This Is

A generic account-research prototype. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP fit score against an editable rubric, top-3 buyer personas, and grounded outreach hooks per persona. "POC" means both Point of Contact (the right person to reach in an account) and Proof of Concept. The ICP rubric lives in `configs/icp.yaml` so the pipeline can be retargeted at any vertical without code changes.

## Core Value

Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader. If everything else slips, this must hold — it is the whole story.

## Current Milestone: v1.1 MCP Server Surface

**Goal:** Expose the grounded account-research pipeline as a public MCP server: a hosted URL anyone can paste into Claude Desktop for capped, evidence-cited demo research, plus a full BYOK stdio server for cloned-repo users.

**Target features:**
- Tiered FastMCP server in `src/mcp_server/`: thin tier (evidence tool, rubric + eval-report resources, research prompt; Exa-only) always registered; full-pipeline tool gated on BYOK writer/judge/Browserbase keys
- Both transports from one entry point: stdio (local clients) and streamable HTTP (hosted)
- Hosted demo on Fly.io behind `MCP_DEMO_MODE`: 5 evidence calls per IP per hour, 25 per UTC day globally, Exa results clamp, structured rationing errors, in-memory counters
- Supporting refactors: `open_deps()` extraction from `pipeline.main()`, `collect_context()` promotion in `src/enrich.py`, `NullBrowserbase`, frozen `EvidencePack` model
- CLAUDE.md charter amendment (adds the `mcp` SDK to the locked stack), README MCP section, tests across all 5 layers

**Design authority:** `docs/superpowers/specs/2026-07-15-mcp-server-design.md` (commit `3a46444`). Economics decided: operator's hard-capped Exa key (unbilled $14.20 credit pool) funds demo retrieval; connectors' own Claude credits fund the reasoning. Server is read-only: no Sheets writes, no batch tools, no rubric editing. PyPI packaging and endpoint auth deferred.

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

<!-- v1.1 MCP Server Surface (in progress). -->

- ✓ Pipeline seams extracted for MCP reuse: `open_deps()` wiring seam (INTEG-01), public `collect_context()`/`RawContext` + `NullBrowserbase` Exa-only path (INTEG-02), frozen `EvidencePack` with `retrieval_status` honesty field (INTEG-03); CLI behavior unchanged, 329 offline tests + strict mypy + lint green — Validated in Phase 9: Pipeline Extraction & Supporting Models (2026-07-16)

### Active

<!-- v1.1 MCP Server Surface. REQ-IDs live in .planning/REQUIREMENTS.md. -->

- MCP server exposes grounded account evidence, the ICP rubric, and the eval report to any MCP client (thin tier, Exa-only)
- Full grounded pipeline available as a gated MCP tool for BYOK users (stdio)
- Hosted streamable-HTTP demo with hard rate limits and daily budget cap
- Existing pipeline behavior, CLI, and Sheets output unchanged; charter amended for the `mcp` SDK

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
| v1.1 adds an MCP server surface; sales-workflow brief rejected (2026-07-15) | MCP wraps existing seams at a fraction of the cost of the review-queue/CRM product, stays on the groundedness differentiator, and teaches the target skill (building MCPs). Demo economics: operator's capped Exa key funds retrieval, caller's Claude credits fund reasoning. Charter amended to add the mcp SDK | — Decided 2026-07-15 |

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

Milestone v1.1 (MCP Server Surface) is underway: Phases 9-11 complete (2026-07-16). Phase 9 extracted the `open_deps()`, `collect_context()`/`RawContext`/`NullBrowserbase`, and `EvidencePack` seams; Phase 10 shipped the stdio MCP server (thin tier); Phase 11 added demo-mode rate limits (`DemoLimiter` with per-IP hour window + UTC-day global cap, fail-closed client-IP resolution) and streamable HTTP transport from the same entry point (`make mcp-http`/`make mcp-demo`), validating HOST-02 and HOST-04 as amended post-review (Fly-Client-IP-only bucketing per WR-01; demo mode forces NullBrowserbase regardless of credentials per quick task 260716-p8r; 459 offline tests, strict mypy, lint all clean). Next: Phase 12, full-tier tool, resources & prompt.

---
*Last updated: 2026-07-16 after Phase 11 completion (Rate Limits & Streamable HTTP Transport). v1.0 history unchanged above.*
