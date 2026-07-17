# Milestones

## v1.1 MCP Server Surface (Shipped: 2026-07-17)

**Phases completed:** 5 phases, 21 plans, 47 tasks

**Key accomplishments:**

- `open_deps(settings)` async context manager extracted from `pipeline.main()`, owning httpx.AsyncClient lifetime and yielding the existing `Deps` bundle across replay/record/live modes
- Promoted `Enricher._collect_context`/`_RawContext` to a public module-level `collect_context()`/`RawContext` seam and added a `NullBrowserbase` no-op client, giving Phase 10's thin MCP tier an Exa-only retrieval path with zero `Enricher` instance and no LLM key required.
- Frozen `EvidencePack` pydantic model with `from_context` factory classmethod computing "ok"/"thin"/"empty" retrieval-status honesty signal, no circular import with src/enrich.py
- Closed Phase 9 with a clean `make test` (329 passed) + `make typecheck` (0 errors, 0 new overrides) + `make lint` (ruff and black clean) run against the fully merged Wave-1 changeset (open_deps, collect_context/RawContext, NullBrowserbase, EvidencePack), with zero code changes needed.
- Added the official mcp>=1.28.1 SDK as a project dependency and extended EvidencePack + Settings with the about_text field and mcp_tier() resolver that plans 10-02/10-03 build the thin-tier server on.
- Built the `src/mcp_server/` package: MCP-boundary evidence capping, key-aware thin-tier lifespan wiring, the `get_account_evidence` FastMCP tool with read-only annotations and a sanitizing error wrapper, the stderr-first stdio entrypoint, `make mcp`, and an offline in-memory-client functional test suite covering MCP-01/06/07.
- Added a real-subprocess MCP smoke gate and verified the thin-tier server end to end through a real Codex stdio client, including grounded evidence, sanitized invalid-domain handling, and connection survival.
- Exact serialized EvidencePack budgeting and strict shared hostname validation close the two Phase 10 verifier gaps without changing the wire schema or adding dependencies.
- Filter-before-cap evidence selection, semantic hostname validation, and fixed-size invalid-domain errors close the final deterministic Phase 10 gaps.
- In-memory DemoLimiter (rolling per-IP hour window + fixed-UTC-day global cap, asyncio.Lock-guarded) and fail-closed resolve_client_ip, plus five env-tunable Settings knobs for HOST-04
- Wired plan 11-01's DemoLimiter and Exa clamp into the live tool path: demo-mode construction in make_thin_lifespan, a single check-and-consume gate in get_account_evidence before retrieval, and a 402/429 exhaustion masquerade that borrows the daily-cap message
- Same get_account_evidence tool surface served over streamable HTTP from the one `python -m src.mcp_server` entry point, gated behind an explicit localhost TransportSecuritySettings allowlist, with header-driven per-IP rate limiting verified end-to-end through the real ASGI/Starlette stack
- process_account gains additive run_eval and on_stage keyword-only parameters (D-02/D-05) and Deps exposes exa/browserbase/limiter, all with zero behavior change for existing callers
- icp://rubric and icp://eval-report MCP resources plus a static research_account prompt enforcing [N]-citation discipline, all registered unconditionally on every tier
- Gated `research_account_full` MCP tool wired through a shared `open_deps` lifespan, tier-gated at registration time so `MCP_DEMO_MODE` provably hides it even with full BYOK keys present
- Five new in-memory MCP functional tests lock research_account_full's complete ScoredAccount JSON payload, run_eval honesty, degraded-stage mirroring, sanitized errors, and per-stage progress; phase gate green after one black-formatting fix.
- `mcp_public_hostname` Settings field parametrizes build_server's DNS-rebinding allowlist so a real Fly client Host header is accepted while wildcard binds (0.0.0.0, ::) are never allowlisted, backed by a D-06 fail-fast startup guard.
- Multi-stage uv Dockerfile, single-machine suspend-on-idle fly.toml, thin `make deploy` target, and a complete `docs/DEPLOY.md` operator runbook for the hosted MCP demo, with the roadmap-mandated `fly launch` dry run done first (partially, via a graceful no-account degradation) and independently end-to-end verified with a local Docker build.
- New `tests/integration/test_mcp_error_sanitization.py` proves all three `get_account_evidence` error paths (invalid domain, provider failure, poisoned internal exception) stay sanitized, and the full offline gate is green across the merged Phase 13 Wave 1 changeset with zero new mypy overrides.
- Public MCP endpoint live on an Oracle Cloud Always Free VM (poc-scraper-mcp behind Caddy, TLS via sslip.io + Let's Encrypt) after a three-target deploy pivot; a real MCP client confirmed cited-evidence retrieval and a sanitized error payload against the live URL.
- README gains a "Try it live" hook and a full MCP server section (grounding-by-instruction vs grounding-by-construction contrast, three client snippets, BYOK subsection) using the confirmed live Oracle endpoint; CLAUDE.md's stack, file layout, and failure-mode sections are synced to the shipped MCP surface.

---

## v1.0 MVP (Shipped: 2026-07-15)

**Phases completed:** 8 phases, 33 plans

**Delivered:** A demo-ready hardening of the account-research pipeline: groundedness made provable end-to-end, an eval narrative that makes the rigor legible, hardened failure modes, a polished Google Sheet output, a scrubbed public repo, and a front-loaded README with a recorded walkthrough pinned to a specific commit.

**Key accomplishments:**

- **Groundedness enforced by construction.** Extracted a single citation parser (`src/citations.py`) with per-claim rapidfuzz coverage checks, so any outreach claim that does not match its cited evidence is dropped before it reaches the sheet (Phases 1-2).
- **Discrete failure taxonomy.** A four-state `AccountStatus` enum (clean / low_groundedness / hook_suppressed / judge_failed) plus an `eval_failed` sentinel that separates judge failure from writer fabrication (Phase 2).
- **Defensible eval set + calibration.** Expanded `evals/labeled.jsonl` to a 15-field schema with an 18-cell coverage matrix, and a calibration runner computing cross-family Cohen's kappa and agreement per axis (Phase 3).
- **Eval narrative artifact.** A pure, byte-stable `evals/REPORT.md` renderer answering the six rigor questions from concrete artifacts, headlined by 2.73 / 5.0 mean groundedness on a 10-record holdout (Phase 4).
- **Failure-mode hardening.** RFC 7231 Retry-After handling on 429s, blanket `except Exception` sites narrowed to per-stage tuples, and replay/record machinery for credit-free deterministic runs (Phase 5).
- **Sheet legibility.** Four-state row colors with a Legend tab, a per-run Sources tab with whole-cell HYPERLINK citations, per-axis score columns, and freeze panes so the workbook reads on first open (Phase 6).
- **Public-repo readiness + demo close.** History scrubbed of the hiring-company name with a pre-commit guard, then a front-loaded what/why/proof README, a failure-mode gallery, and a recorded walkthrough pinned to commit `f868a09` (Phases 7-8).

**Known caveats (disclosed):**

- The recorded walkthrough does not demonstrate the `[N]`-citation click into the Sources tab; the citation mechanism is documented in the README prose, gallery, and live Sources tab (Phase 8, operator-accepted).
- The failure-mode gallery shows 2 of the 4 `AccountStatus` states; `hook_suppressed` and `judge_failed` did not surface across the real-run capture attempts and are documented in prose instead (Phase 8).

---
