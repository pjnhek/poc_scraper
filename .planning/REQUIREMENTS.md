# Requirements: poc_scraper v1.2 Agent-Driven ICP Scoring

**Defined:** 2026-07-17
**Core Value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader.
**Milestone frame:** Hybrid grounding. The connecting agent's judgment stays grounding-by-instruction (it must cite [N] evidence per axis); the scoring math becomes grounding-by-construction (the server cannot return an arithmetically wrong score). The caller's model does the reasoning; our server guarantees the rubric is applied exactly.

## v1.2 Requirements

### Deterministic Scoring (SCORE)

- [ ] **SCORE-01**: A connecting agent can call a `score_account` MCP tool with four 1-5 axis scores (`support_volume`, `ai_maturity`, `stage_fit`, `channel_breadth`, plus optional per-axis reason strings) and receive the rubric breakdown, weighted total, and verdict computed server-side by reusing `compute_total(breakdown, config)` and `config.verdict_for(total)` with the frozen `RubricBreakdown` model (no new axes, no model changes)
- [ ] **SCORE-02**: `score_account` is registered on both the thin and full tiers, performs pure arithmetic (no LLM, no Exa, no keys, no I/O), and does not consume the demo rate-limit quota (`DemoLimiter` is never consulted for it)
- [ ] **SCORE-03**: `score_account` carries `readOnlyHint: true` / `destructiveHint: false` annotations and returns the project's standard sanitized one-line error on invalid input (axis outside 1-5, malformed values) via the existing error-wrapper pattern in `src/mcp_server/server.py` (no stack traces, env var names, or key fragments)

### Guided Flow (PROMPT)

- [ ] **PROMPT-01**: The `research_account` prompt orchestrates the full scoring flow: call `get_account_evidence`, read `icp://rubric`, score each axis 1-5 with [N] citations from the evidence, call `score_account` with those scores, and present the returned verdict

### Evidence Tuning (EVID)

- [ ] **EVID-01**: A caller can pass an optional `news_days` parameter to `get_account_evidence` to tune the Exa news lookback window; the value is clamped server-side to a sane range and defaults to the current 90-day behavior (threads through `collect_context` to `ExaClient.search_news(days=...)`)

### Documentation (DOCS)

<!-- Continues numbering from v1.1 (DOCS-01, DOCS-02 shipped). -->

- [ ] **DOCS-03**: The deploy landing page (`deploy/oracle/setup.sh` index.html) mentions the agent-driven scoring capability alongside evidence retrieval
- [ ] **DOCS-04**: The README MCP section documents `score_account` with the honest hybrid framing: judgment is grounding-by-instruction (agent cites [N] per axis), scoring math is grounding-by-construction (server-guaranteed rubric application)

### Test Coverage (TEST)

<!-- Continues numbering from v1.1 (TEST-01, TEST-02 shipped). -->

- [ ] **TEST-03**: `score_account` is covered by unit tests (tool wrapper math delegation + input validation + sanitized errors) and an in-memory MCP-client functional test (`mcp.shared.memory`), and the full offline suite + strict mypy + ruff + black + `verify-public-repo` stay green with no new mypy overrides
- [ ] **TEST-04**: `news_days` clamping and default behavior are covered by tests at the MCP boundary (out-of-range values clamp, omitted parameter preserves the 90-day default)

## Future Requirements

<!-- Discussed but deferred. -->

- Per-call rubric weights/descriptions override for `score_account` (same 4 axes only) — parked companion, not bundled into v1.2
- Arbitrary-axis rubrics — explicitly deferred as expensive/risky; the frozen 4-axis `RubricBreakdown` is the contract
- PyPI/uvx packaging, hosted-endpoint auth, `structuredContent`, MCP Registry listing, company-name-to-domain resolution — carried from v1.1 Future Requirements

## Out of Scope

<!-- Explicit exclusions with reasoning. -->

- Server-side LLM scoring on the thin tier ("Option A") — defeats the keyless/costless demo economics; the caller's model does the reasoning by design
- Touching `RubricBreakdown` or the fixed axis set — frozen model shared across pipeline, sheet, and eval; changing it is a different milestone
- Feedback loop, CRM automation, webapp/dashboard, multi-tenant config, custom caching — v2/v3 per CLAUDE.md locked scope
- Compute upgrade for the Oracle host — `score_account` is pure math; the live box has ample headroom (~84 MB used, load 0.00)

## Traceability

<!-- Filled by roadmap creation. -->

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCORE-01 | Phase 14 | Pending |
| SCORE-02 | Phase 14 | Pending |
| SCORE-03 | Phase 14 | Pending |
| PROMPT-01 | Phase 14 | Pending |
| EVID-01 | Phase 14 | Pending |
| DOCS-03 | Phase 14 | Pending |
| DOCS-04 | Phase 14 | Pending |
| TEST-03 | Phase 14 | Pending |
| TEST-04 | Phase 14 | Pending |

---
*9 requirements defined for milestone v1.2*
