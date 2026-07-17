# Roadmap: poc_scraper

## Milestones

- ✅ **v1.0 MVP** — Phases 1-8 (shipped 2026-07-15)
- ✅ **v1.1 MCP Server Surface** — Phases 9-13 (shipped 2026-07-17)
- 🔵 **v1.2 Agent-Driven ICP Scoring** — Phase 14 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-8) — SHIPPED 2026-07-15</summary>

A brownfield hardening milestone for the async account-research pipeline: a no-code groundedness audit drove gap-closure in `src/`, then eval-set expansion, the eval narrative artifact, failure-mode hardening and Sheet polish (in parallel), a public-repo scrub, and a closing README plus recorded walkthrough against the locked, scrubbed pipeline. Full details archived at [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Groundedness Audit (3/3 plans) — completed 2026-05-15
- [x] Phase 2: Groundedness Fix (6/6 plans) — completed 2026-05-15
- [x] Phase 3: Eval Set Expansion (6/6 plans) — completed 2026-05-16
- [x] Phase 4: Eval Narrative (3/3 plans) — completed 2026-05-22
- [x] Phase 5: Failure-Mode Hardening (4/4 plans) — completed 2026-05-22
- [x] Phase 6: Sheet Polish (4/4 plans) — completed 2026-07-15
- [x] Phase 7: Public-Repo Audit (3/3 plans) — completed 2026-05-27
- [x] Phase 8: README and Loom Refresh (4/4 plans) — completed 2026-07-15

</details>

<details>
<summary>✅ v1.1 MCP Server Surface (Phases 9-13) — SHIPPED 2026-07-17</summary>

Exposed the grounded account-research pipeline as an MCP server: a hosted, rationed thin tier (evidence retrieval, live on Oracle Cloud Always Free) plus a BYOK full tier over stdio (full cited pipeline, ICP scoring), with the ICP rubric and eval report served as MCP resources. Built on a dependency-driven order (pipeline extraction -> stdio thin tier -> HTTP transport + rate limits -> gated full tier -> hosted deploy + docs). Full details archived at [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).

- [x] Phase 9: Pipeline Extraction & Supporting Models (4/4 plans) — completed 2026-07-16
- [x] Phase 10: Stdio MCP Server (Thin Tier) (5/5 plans) — completed 2026-07-16
- [x] Phase 11: Rate Limits & Streamable HTTP Transport (3/3 plans) — completed 2026-07-16
- [x] Phase 12: Full-Tier Tool, Resources & Prompt (4/4 plans) — completed 2026-07-17
- [x] Phase 13: Hosted Deploy & Docs Close (5/5 plans) — completed 2026-07-17

</details>

### v1.2 Agent-Driven ICP Scoring (Phase 14) — IN PROGRESS

A deliberately small milestone with a locked design: one new deterministic `score_account` MCP tool reusing `compute_total`/`verdict_for` over the existing frozen `RubricBreakdown`, wired into an updated `research_account` prompt, plus a clamped `news_days` evidence-tuning parameter and doc updates for the hybrid grounding framing. All 9 requirements land in a single phase; the work is one tightly-coupled server-module change with no real sequencing dependency between the tool, the prompt, evidence tuning, tests, and docs.

- [ ] **Phase 14: Deterministic Scoring & Guided Flow** - Agents get a server-guaranteed ICP score alongside their cited evidence, orchestrated end-to-end by the research prompt

## Phase Details

### Phase 14: Deterministic Scoring & Guided Flow
**Goal**: A connecting agent can retrieve cited evidence, score each ICP axis itself, and get a deterministically-computed weighted total and verdict back from the server — with the guided prompt, tunable news recency, and docs all reflecting the new capability.
**Depends on**: Phase 13 (existing thin/full tier MCP server, `compute_total`/`verdict_for`, `RubricBreakdown`, `icp://rubric` resource, `research_account` prompt, `get_account_evidence` tool)
**Requirements**: SCORE-01, SCORE-02, SCORE-03, PROMPT-01, EVID-01, DOCS-03, DOCS-04, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. A connected MCP client calls `score_account` with four 1-5 axis scores (plus optional per-axis reason strings) and receives back the rubric breakdown, weighted total, and verdict, computed by reusing `compute_total`/`verdict_for` against the unchanged, frozen `RubricBreakdown` — no new axes, no model changes.
  2. `score_account` is registered on both the thin and full tiers, performs pure arithmetic with no LLM/Exa/key/I-O dependency, never consumes the `DemoLimiter` quota, carries `readOnlyHint: true`/`destructiveHint: false`, and returns the project's standard sanitized one-line error for invalid axis input.
  3. Following the updated `research_account` prompt, an agent calls `get_account_evidence`, reads `icp://rubric`, scores each axis 1-5 with `[N]` citations from the evidence, calls `score_account` with those scores, and is shown the returned verdict — the guided flow works end to end.
  4. A caller can pass `news_days` to `get_account_evidence` to tune the Exa news lookback; out-of-range values are clamped server-side, and omitting the parameter preserves the existing 90-day default, threaded through `collect_context` to `ExaClient.search_news(days=...)`.
  5. The Oracle landing page and README MCP section document `score_account` with the honest hybrid framing (judgment stays grounding-by-instruction via agent-cited `[N]`, scoring math becomes grounding-by-construction), and the full offline gate (unit tests, in-memory MCP-client functional tests for `score_account` and `news_days` clamping, strict mypy, ruff, black, `verify-public-repo`) stays green with no new mypy overrides.
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
| ----- | --------- | -------------- | -------- | ---------- |
| 1. Groundedness Audit      | v1.0 | 3/3 | Complete | 2026-05-15 |
| 2. Groundedness Fix        | v1.0 | 6/6 | Complete | 2026-05-15 |
| 3. Eval Set Expansion      | v1.0 | 6/6 | Complete | 2026-05-16 |
| 4. Eval Narrative          | v1.0 | 3/3 | Complete | 2026-05-22 |
| 5. Failure-Mode Hardening  | v1.0 | 4/4 | Complete | 2026-05-22 |
| 6. Sheet Polish            | v1.0 | 4/4 | Complete | 2026-07-15 |
| 7. Public-Repo Audit       | v1.0 | 3/3 | Complete | 2026-05-27 |
| 8. README and Loom Refresh | v1.0 | 4/4 | Complete | 2026-07-15 |
| 9. Pipeline Extraction & Supporting Models | v1.1 | 4/4 | Complete | 2026-07-16 |
| 10. Stdio MCP Server (Thin Tier) | v1.1 | 5/5 | Complete | 2026-07-16 |
| 11. Rate Limits & Streamable HTTP Transport | v1.1 | 3/3 | Complete | 2026-07-16 |
| 12. Full-Tier Tool, Resources & Prompt | v1.1 | 4/4 | Complete | 2026-07-17 |
| 13. Hosted Deploy & Docs Close | v1.1 | 5/5 | Complete | 2026-07-17 |
| 14. Deterministic Scoring & Guided Flow | v1.2 | 0/TBD | Not started | - |
