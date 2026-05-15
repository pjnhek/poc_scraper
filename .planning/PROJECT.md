# poc_scraper

## What This Is

A generic account-research prototype. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP fit score against an editable rubric, top-3 buyer personas, and grounded outreach hooks per persona. "POC" means both Point of Contact (the right person to reach in an account) and Proof of Concept. The ICP rubric lives in `configs/icp.yaml` so the pipeline can be retargeted at any vertical without code changes.

## Core Value

Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader. If everything else slips, this must hold — it is the whole story.

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

### Active

<!-- The demo-ready v1 milestone. Each is a hypothesis until shipped. -->

- [ ] Audit groundedness coverage end-to-end and produce a findings document that drives the rest of the roadmap
- [ ] Close any groundedness gaps found in the audit (writer enforcement, citation extraction, eval rubric)
- [ ] Expand `evals/labeled.jsonl` to a size that makes the rigor claim defensible, with documented coverage rationale
- [ ] Produce an eval narrative artifact (report / README section / screenshot) that makes groundedness numbers legible to a non-author reader
- [ ] Harden the documented failure modes that would surface as stack traces on a real CSV run (rate limits, scraping blocked, empty enrichment, sub-threshold score)
- [ ] Polish Sheet output for demo legibility (citation visibility, red-flag rows for unscoreable / low-groundedness, score breakdown readability)
- [ ] Refresh README + re-record Loom against the final pipeline output once the rigor work has landed
- [ ] Public-repo audit: scrub any vertical-specific names, vendor leaks, or sensitive references from code, prompts, configs, and history

### Out of Scope

<!-- v2/v3 per CLAUDE.md. Restated here so the roadmapper does not drift into them. -->

- Feedback loop from sales rejections — v2, requires production usage data we do not have
- CRM trigger automation — v2, scope creep beyond a research POC
- Webapp / dashboard / Slack bot — v3, the Google Sheet is the deliverable surface
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
| Milestone framed as "demo-ready v1" rather than "harden" or "add features" | Polish-and-close-gaps fits the brownfield state; new features would invite scope creep into v2/v3 territory | — Pending |
| Phase 1 is an audit, not a feature | Groundedness state is not yet fully understood; planning fixes without auditing risks solving the wrong problems | — Pending |
| README/Loom refresh deferred to the closing phase | Re-recording mid-milestone wastes effort; the artifact should reflect the final pipeline output | — Pending |
| Both primary (hiring) and secondary (GTM) demo audiences are in scope, with hiring primary | README+Loom serves both; live-run polish covers the secondary audience without separate work streams | — Pending |
| Public-repo discipline elevated from CLAUDE.md guidance to a PROJECT.md constraint | A leak kills the primary artifact's purpose; deserves a dedicated audit phase rather than ad-hoc review | — Pending |

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

---
*Last updated: 2026-05-14 after initialization*
