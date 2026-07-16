# Roadmap: poc_scraper

## Milestones

- ✅ **v1.0 MVP** — Phases 1-8 (shipped 2026-07-15)
- 🚧 **v1.1 MCP Server Surface** — Phases 9-13 (in progress)

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

### 🚧 v1.1 MCP Server Surface (In Progress)

**Milestone Goal:** Expose the grounded account-research pipeline as a public MCP server: a hosted URL anyone can paste into Claude Desktop for capped, evidence-cited demo research, plus a full BYOK stdio server for cloned-repo users.

**Build order:** Phases 9-13 are strictly sequential. Each phase's server surface builds on the seam the previous phase established (extraction -> stdio thin tier -> HTTP transport + limits -> gated full tier -> hosted deploy), following the dependency-driven order from `.planning/research/SUMMARY.md`.

- [x] **Phase 9: Pipeline Extraction & Supporting Models** - Extract `open_deps()` from `pipeline.main()`, promote `collect_context()`, add `NullBrowserbase` and a frozen `EvidencePack` model (completed 2026-07-16)
- [x] **Phase 10: Stdio MCP Server (Thin Tier)** - `get_account_evidence` served over stdio, verified against a real client, smoke-tested against a live domain (completed 2026-07-16)
- [ ] **Phase 11: Rate Limits & Streamable HTTP Transport** - Demo-mode limits with safe client-IP resolution, served over streamable HTTP from the same entry point as stdio
- [ ] **Phase 12: Full-Tier Tool, Resources & Prompt** - Gated `research_account_full`, `icp://rubric` and `icp://eval-report` resources, `research_account` prompt
- [ ] **Phase 13: Hosted Deploy & Docs Close** - Public Fly.io URL, hardened error payloads, CLAUDE.md and README updated for the new surface

## Phase Details

### Phase 9: Pipeline Extraction & Supporting Models

**Goal**: Pipeline internals expose a reusable dependency-construction seam and additive supporting models/clients that the MCP server tiers will build on top of, with existing CLI behavior and tests unchanged.
**Depends on**: Phase 8 (v1.0, complete)
**Requirements**: INTEG-01, INTEG-02, INTEG-03
**Success Criteria** (what must be TRUE):

  1. `make run` behavior and the existing pipeline test suite are unchanged after `open_deps()` is extracted from `pipeline.main()`
  2. `collect_context()` is a public, independently importable function (promoted from `_collect_context`)
  3. `NullBrowserbase` satisfies `BrowserbaseLike` and returns `None` on fetch (D-07: deliberate deviation from the original design spec's "raises BrowserbaseError" wording), verified by a test that exercises `collect_context`'s existing catch-and-continue path with Exa-only results
  4. A frozen `EvidencePack` model (`extra="forbid"`, tuple collections) exists in `src/models.py` following existing model conventions

**Plans**: 4/4 plans complete
Plans:
**Wave 1**

- [x] 09-01-PLAN.md — Extract `open_deps()` async context manager from `pipeline.main()` (INTEG-01)
- [x] 09-02-PLAN.md — Promote `collect_context()`/`RawContext` and add `NullBrowserbase` (INTEG-02)
- [x] 09-03-PLAN.md — Add frozen `EvidencePack` model with `from_context` factory (INTEG-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 09-04-PLAN.md — Full offline regression gate (tests + strict mypy + lint) across the merged changeset

**Note**: Pure refactor plus additive, convention-following code; no `mcp` SDK dependency yet, so this is a standard pattern per research (no dedicated research-phase needed).

### Phase 10: Stdio MCP Server (Thin Tier)

**Goal**: A local user can run the thin-tier MCP server over stdio and connect a real MCP client to retrieve grounded, cited account evidence.
**Depends on**: Phase 9
**Requirements**: MCP-01, MCP-06, MCP-07, HOST-01, TEST-02
**Success Criteria** (what must be TRUE):

  1. A local user runs `make mcp` and connects Claude Code or Claude Desktop over stdio, verified against a real client connection (not just unit tests)
  2. Calling `get_account_evidence(domain)` returns numbered, cited evidence as structured JSON with a `retrieval_status` (`ok`/`thin`/`empty`) honesty field, with snippets capped in size at the MCP boundary
  3. The server resolves and logs its capability tier once at startup; invalid domains, provider failures, and other domain errors surface as `isError: true` tool results, never protocol-level errors
  4. All server logging routes to stderr so stdio JSON-RPC is never contaminated
  5. `make smoke-mcp` runs the stdio server as a real subprocess against one live domain and asserts non-empty numbered justifications, skipped in CI

**Plans**: 5/5 plans complete

Plans:

**Wave 1**

- [x] 10-01-PLAN.md — Foundation: `mcp>=1.28,<2.0` dependency, `EvidencePack.about_text`, `Settings.mcp_tier()` + `mcp_demo_mode`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10-02-PLAN.md — `src/mcp_server/` package: evidence caps, thin-tier lifespan wiring, FastMCP tool + sanitized errors + tier logging, stdio entrypoint, `make mcp`, unit + in-memory functional tests

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 10-03-PLAN.md — Real-transport gates: `make smoke-mcp` subprocess smoke (skipped in CI) + Claude Code real-client verification checkpoint

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 10-04-PLAN.md — Gap closure: enforce the serialized evidence byte budget and reject malformed domains before provider access

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 10-05-PLAN.md — Final gap closure: preserve later valid evidence and reject residual malformed domain forms

**Note**: First phase exercising the `mcp` SDK — verify the `ToolError` import path and confirm the lifespan-runs-once-per-process guarantee before building on it (research flag). [RESOLVED by 10-RESEARCH.md: `ToolError` lives at `mcp.server.fastmcp.exceptions` but plain exceptions suffice; lifespan-once-per-process confirmed against mcp==1.28.1 source.]

### Phase 11: Rate Limits & Streamable HTTP Transport

**Goal**: The hosted transport enforces demo-mode rate limits against a safely-resolved client IP and serves the same tool surface as stdio, from the same entry point.
**Depends on**: Phase 10
**Requirements**: HOST-02, HOST-04
**Success Criteria** (what must be TRUE):

  1. `make mcp-http` serves the same tool surface over streamable HTTP as `make mcp` does over stdio, from one entry point
  2. Demo mode enforces 5 evidence calls per IP per hour and 25 per UTC day globally (both env-tunable), returning structured rationing errors with reset times
  3. Client IP resolves from `Fly-Client-IP` with rightmost-XFF fallback and fails closed into one shared bucket on missing or malformed headers, verified with an injected clock
  4. Rate-limit counters are protected against read-modify-write races under concurrent requests

**Plans**: TBD
**Note**: Highest-uncertainty step in the milestone — confirm the exact `streamable_http_app(middleware=...)` kwarg shape against the installed SDK before building `ClientIPMiddleware` on top of it (research flag).

### Phase 12: Full-Tier Tool, Resources & Prompt

**Goal**: BYOK users get the complete grounded pipeline as a gated MCP tool, and any client can read the rubric, the eval report, and a guided research prompt.
**Depends on**: Phase 11
**Requirements**: MCP-02, MCP-03, MCP-04, MCP-05
**Success Criteria** (what must be TRUE):

  1. A BYOK user (writer/judge and Browserbase keys present) calls `research_account_full(domain, run_eval)` and receives the complete grounded `ScoredAccount` JSON including `AccountStatus`
  2. `MCP_DEMO_MODE=1` forces thin tier and hides `research_account_full` even when full keys are present, verified by a test
  3. An MCP client reads `configs/icp.yaml` via the `icp://rubric` resource and `evals/REPORT.md` via the `icp://eval-report` resource
  4. Invoking the `research_account` prompt guides rubric-based scoring where every claim cites an `[N]` justification index and unciteable claims are dropped

**Plans**: TBD

### Phase 13: Hosted Deploy & Docs Close

**Goal**: A stranger can connect to a public, safely-configured Fly.io URL with zero setup, and the project charter/README reflect the new MCP surface.
**Depends on**: Phase 12
**Requirements**: HOST-03, HOST-05, HOST-06, DOCS-01, DOCS-02, TEST-01
**Success Criteria** (what must be TRUE):

  1. A stranger connects to the hosted Fly.io URL (directly or via `npx mcp-remote`) with zero setup and retrieves cited evidence
  2. The HTTP transport is configured with an explicit `TransportSecuritySettings` allowed-hosts allowlist, and `fly.toml` pins exactly one machine so in-memory rate limits stay truly global
  3. Tool error payloads never contain stack traces, env names, or key fragments, verified against a deliberately triggered failure
  4. CLAUDE.md lists `mcp>=1.28,<2.0` in the locked stack with the MCP surface noted in scope; README gains an MCP section with client config snippets (Claude Desktop, Claude Code, `npx mcp-remote`) and the grounding-by-instruction vs grounding-by-construction contrast
  5. The full offline test suite (unit, functional via in-memory MCP client, integration) covers tiering, limits with an injected clock, evidence construction, and error paths; strict mypy stays clean with no new overrides

**Plans**: TBD
**Note**: Do an early `fly launch` dry run before writing the Dockerfile/`fly.toml` in earnest — no confirmed reference exists for Python + streamable HTTP on Fly (research flag).

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
| 9. Pipeline Extraction & Supporting Models | v1.1 | 4/4 | Complete    | 2026-07-16 |
| 10. Stdio MCP Server (Thin Tier) | v1.1 | 5/5 | Complete    | 2026-07-16 |
| 11. Rate Limits & Streamable HTTP Transport | v1.1 | 0/TBD | Not started | - |
| 12. Full-Tier Tool, Resources & Prompt | v1.1 | 0/TBD | Not started | - |
| 13. Hosted Deploy & Docs Close | v1.1 | 0/TBD | Not started | - |
</content>
