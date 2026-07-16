# Phase 10: Stdio MCP Server (Thin Tier) - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

First phase exercising the `mcp` SDK: a local user runs `make mcp`, connects a real MCP client over stdio, and calls `get_account_evidence(domain)` to receive numbered, cited evidence as structured JSON with a `retrieval_status` honesty field. The server resolves and logs its capability tier once at startup; all logging routes to stderr; domain failures surface as `isError: true` tool results, never protocol errors. Closes with `make smoke-mcp` (opt-in subprocess smoke against one live domain, skipped in CI). Requirements: MCP-01, MCP-06, MCP-07, HOST-01, TEST-02.

Out of this phase: HTTP transport and rate limits (Phase 11), full-tier tool / resources / prompt (Phase 12), hosting and docs (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### Evidence payload shape (MCP-01)
- **D-01:** The tool payload includes the cleaned `about_text` per the design spec. Phase 9's `EvidencePack` shipped without it; this phase adds it.
- **D-02:** `about_text: str = ""` is added as a field on the frozen `EvidencePack` model (additive, defaulted, so Phase 9 tests stay green). `from_context` already receives `about_text` and stores the pre-capped value. One model owns the wire format; `model_dump()` stays the single serialization path. No wrapper dict at the tool layer.
- **D-03:** MCP-boundary size caps are module constants in `src/mcp_server/evidence.py` (SCREAMING_SNAKE, following the `SUMMARY_MAX_CHARS` precedent): about_text ~2000 chars, per-justification summary ~300 chars, news list ~10 items. No new env knobs (Phase 9 D-09 principle). Demo-specific clamps (Exa results=5) remain Phase 11 scope. Capping happens in `evidence.py` before model construction, honoring Phase 9 D-10 (capping at the MCP boundary, not in the model).

### Thin-tier Browserbase policy (wiring)
- **D-04:** Key-aware Browserbase fallback in thin tier: construct a real `BrowserbaseClient` when `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID` are set, `NullBrowserbase` otherwise. This honors the design spec ("Browserbase fallback when a key exists") and matches CLI evidence quality. It REFINES Phase 9 D-04's "Exa + NullBrowserbase" wording; the core of that decision stands: the thin tier wires its own clients via `collect_context` and does NOT call `open_deps`. Demo mode (Phase 11) still forces `NullBrowserbase` unconditionally.

### Real-client verification + smoke (HOST-01, TEST-02)
- **D-05:** Claude Code is the verification gate for the real-client success criterion: register via `claude mcp add` (command wrapping `make mcp` / `uv run python -m src.mcp_server`) and exercise `get_account_evidence` in a live session. Claude Desktop verification is optional bonus, not gating; its config snippet is Phase 13 README work.
- **D-06:** `make smoke-mcp` reuses one domain from `tests/smoke/fixtures.csv` (notion.so or linear.app) so MCP smoke and pipeline smoke burn credits against the same well-understood accounts. Assertions per the roadmap: non-empty numbered justifications, plus `retrieval_status` present.

### Error result design (MCP-07)
- **D-07:** A sanitizing catch-all wraps the tool from day one: unexpected exceptions return a generic "internal error, try again" `isError` result while the full traceback logs to stderr at WARNING+. Do not rely on FastMCP's default exception stringification (leaks paths/env detail). This brings HOST-05 discipline forward so Phase 13 verifies rather than retrofits.
- **D-08:** Error results are plain human-readable messages, no machine-readable error codes. Categories and wording per the design spec: invalid domain passes through the `Account` validator message; Exa failure after tenacity retries returns "retrieval unavailable, try again"; empty/thin retrieval is NOT an error (communicated via `retrieval_status` in a successful result).

### Locked by prior phases / design spec (do not re-litigate)
- Package layout `src/mcp_server/` (`__init__.py`, `server.py`, `wiring.py`, `evidence.py`); `limits.py` is Phase 11.
- Dependency pin `mcp>=1.28,<2.0`, official SDK's bundled FastMCP; NOT the standalone `fastmcp` PyPI package. `mcp` ships `py.typed`; no new mypy overrides. Expect `pydantic` to resolve upward in `uv.lock`; re-run the full suite after `uv sync`.
- Entry point `python -m src.mcp_server`, stdio default (`--transport http` arrives in Phase 11). `Makefile` gains `make mcp` and `make smoke-mcp` this phase.
- stderr-only logging configured before other imports (`logging.basicConfig(stream=sys.stderr, ...)`); stdout is reserved for JSON-RPC.
- `Settings.mcp_tier() -> Literal["thin", "full"]` mirrors `require_for_pipeline()`: thin needs `EXA_API_KEY` only; full also needs writer/judge + Browserbase keys; `MCP_DEMO_MODE=1` forces thin. Tier resolved and logged once at startup; missing EXA key fails fast with the missing-keys listing message.
- `readOnlyHint=True` / `destructiveHint=False` annotations on the tool; tool description carries the citation-numbering contract explicitly (research pitfall 6).
- Thin tier composes `collect_context` + `_number_justifications` -> `EvidencePack.from_context` in `src/mcp_server/evidence.py`; zero LLM involvement.
- Functional tests use the in-memory client from `mcp.shared.memory` (no subprocess, no network) with `FakeExa` / `NullBrowserbase` stubs.

### Claude's Discretion
- Exact cap constant values (the ~2000/~300/~10 numbers are targets, not contracts) and truncation mechanics (ellipsis markers, word boundaries).
- Startup tier log wording, including whether it notes the retrieval sub-mode (exa-only vs exa+browserbase).
- Smoke-test driver mechanics (stdio client subprocess handling, timeouts) and which of the two fixture domains to use.
- `Settings` field scope for this phase (add only what Phase 10 needs vs the spec's full field list) and exact error-message wording.
- Whether `wiring.py` owns a phase-10-local httpx.AsyncClient lifespan for thin-tier clients (it must own one somewhere, since `open_deps` is not called).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design authority
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md` — Approved MCP server design. §"Tool, resource, and prompt surface" defines `get_account_evidence`; §"Config and wiring changes" defines the `Settings`/Makefile additions; §"Error handling" and §"Testing" bind this phase. NOTE: D-01/D-02 above close its about_text gap against the shipped `EvidencePack`; D-04 above resolves its Browserbase-fallback wording against Phase 9 D-04.
- `.planning/research/SUMMARY.md` — Milestone research. Pins `mcp>=1.28,<2.0`; names this phase's research flags: confirm the exact `ToolError` import path and the lifespan-runs-once-per-process guarantee against the installed SDK BEFORE building on them. Pitfall 1 (stdout contamination) and pitfall 5 (oversized JSON) land in this phase.

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — MCP-01, MCP-06, MCP-07, HOST-01, TEST-02 are this phase's requirements.
- `.planning/ROADMAP.md` — Phase 10 goal and 5 success criteria.

### Prior phase decisions
- `.planning/phases/09-pipeline-extraction-supporting-models/09-CONTEXT.md` — D-04 (thin tier wires itself, `open_deps` is full-tier only), D-07 (`NullBrowserbase` returns `None`), D-09 (`retrieval_status` thresholds), D-10 (capping at MCP boundary, not in model).

### Code seams consumed
- `src/pipeline.py` — `open_deps()` (line ~70) exists but is NOT called by the thin tier; reference for wiring conventions only.
- `src/enrich.py` — `collect_context(account, *, exa, browserbase) -> RawContext` (line ~34); `_number_justifications` (module-level); `ABOUT_TEXT_MIN_CHARS = 200` feeds `from_context`.
- `src/models.py` — `EvidencePack` + `RetrievalStatus` (lines ~175-200); `from_context` factory to extend with `about_text`; `Account` validator is the domain gate.
- `src/clients/browserbase_client.py` — `NullBrowserbase` (line ~87) and `BrowserbaseClient` for the key-aware selection.
- `src/config.py` — `Settings` + `require_for_pipeline()` pattern that `mcp_tier()` mirrors.
- `tests/smoke/fixtures.csv` — notion.so / linear.app, the smoke domain pool (D-06).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `collect_context` + `RawContext` (`src/enrich.py`): the complete thin-tier retrieval path; `evidence.py` is a thin composition over it.
- `EvidencePack.from_context` (`src/models.py`): status logic already unit-tested; this phase adds the `about_text` field and passes the capped text through.
- `NullBrowserbase` (`src/clients/browserbase_client.py`): drop-in for the no-keys case; already threads through `collect_context`'s continue path.
- `ExaClient`/`BrowserbaseClient` constructor-injection pattern with a shared `httpx.AsyncClient`: the thin-tier wiring replicates this inside the FastMCP lifespan.
- Test stubs (`FakeExa` etc. across `tests/`): reusable behind `ExaLike` for in-memory MCP functional tests.

### Established Patterns
- Frozen pydantic models, `extra="forbid"`, tuple collections; additive fields need defaults to stay backward compatible.
- Logging: `%` placeholders, WARNING for recoverable failures, truncate untrusted strings; now additionally stderr-only.
- Strict mypy, fully annotated; `mcp` ships types so no new overrides.
- 5-layer test strategy; smoke opt-in via marker, skipped in CI.

### Integration Points
- `pyproject.toml` gains `mcp>=1.28,<2.0` (first new prod dependency of the milestone; charter amendment itself is Phase 13 DOCS-01).
- `Makefile` gains `mcp` and `smoke-mcp` targets.
- `src/config.py` gains `mcp_tier()` and the Phase-10-needed settings fields.
- Dependency arrow is one-directional: `src/mcp_server/` imports from `src/`, never the reverse.

</code_context>

<specifics>
## Specific Ideas

- The user again consistently chose spec-faithful, convention-preserving options: close the spec's about_text gap rather than deviate, key-aware Browserbase per the spec's own wording, caps as constants not knobs.
- Two deliberate refinements of prior artifacts to carry forward so verification does not flag them: (1) `EvidencePack` gains `about_text` (Phase 9 shipped without it; the spec always listed it); (2) Phase 9 D-04's "Exa + NullBrowserbase" is refined to key-aware selection — the no-`open_deps` core of D-04 is untouched.
- Sanitization is front-loaded: HOST-05 behavior (no stack traces/env/keys in error payloads) is built in Phase 10 and merely verified in Phase 13.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Rate limits, HTTP transport, resources/prompt, full-tier tool, and README/CLAUDE.md docs were repeatedly kept in Phases 11-13 where the roadmap places them.)

</deferred>

---

*Phase: 10-Stdio MCP Server (Thin Tier)*
*Context gathered: 2026-07-16*
