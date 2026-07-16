# Phase 9: Pipeline Extraction & Supporting Models - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure refactor plus additive, convention-following code that gives the MCP server phases (10-13) their seams: `open_deps()` extracted from `pipeline.main()`, a public `collect_context()`, a `NullBrowserbase` null object, and a frozen `EvidencePack` model. `make run` behavior and the existing pipeline test suite stay unchanged. No `mcp` SDK dependency in this phase. Requirements: INTEG-01, INTEG-02, INTEG-03.

</domain>

<decisions>
## Implementation Decisions

### open_deps() seam (INTEG-01)
- **D-01:** `open_deps(settings)` is an async context manager yielding the existing frozen `Deps` dataclass (`async with open_deps(settings) as deps:`). No new bundle type.
- **D-02:** `open_deps` creates and owns the shared `httpx.AsyncClient` lifetime internally (opens on enter, closes on exit). Callers get a fully self-contained seam; no injected-client parameter.
- **D-03:** The replay/record branching (`settings.demo_bundle` -> Replay* clients; `settings.record_bundle` -> Recording* wrappers) moves into `open_deps` verbatim with the rest of the client-construction block. The MCP server inherits replay capability for free.
- **D-04:** `open_deps` is tier-agnostic in Phase 9: it constructs everything from settings exactly as `main()` does today (construction does not validate keys; `require_for_pipeline()` does). Phase 10 wires the thin tier itself (Exa + `NullBrowserbase` via `collect_context`) and only calls `open_deps` for the full tier. No tier/mode parameter now.

### collect_context() promotion (INTEG-02)
- **D-05:** `_collect_context` is extracted to a module-level function in `src/enrich.py`: `async def collect_context(account, *, exa, browserbase) -> RawContext`. `Enricher.enrich()` calls it. The thin tier imports it with zero LLM involvement (avoids the trap that `Enricher.__init__` requires an `llm` argument the thin tier does not have).
- **D-06:** `_RawContext` is promoted to public `RawContext` (still a frozen dataclass). A public function returning a private type is a half-promotion; the type is part of the seam Phase 10's `evidence.py` consumes.
- **D-07 (spec deviation, deliberate):** `NullBrowserbase.render()` returns `None` (logging "browserbase disabled") instead of raising `BrowserbaseError`. The design spec's wording ("raises BrowserbaseError ... which collect_context already catches") is inconsistent with the code: the catch-and-continue path lives inside `BrowserbaseClient.render()` (`src/clients/browserbase_client.py:56-61`), not in `collect_context`. A raising null object would propagate to `process_account`'s enrich catch and mark the whole account unscoreable, the opposite of Exa-only continue. Returning `None` satisfies `BrowserbaseLike` (`render(url) -> RenderedPage | None`) verbatim and leaves `collect_context` untouched. ROADMAP success criterion 3 ("raises BrowserbaseError on fetch") must be reworded at planning to match: the test verifies `NullBrowserbase` threads through `collect_context`'s existing `rendered is not None` continue path with Exa-only results.

### EvidencePack (INTEG-03)
- **D-08:** Phase 9 ships the model plus a factory classmethod (e.g. `EvidencePack.from_context(ctx, justifications)`) that computes `retrieval_status`, following the existing factory convention (`Citation.make`, `ScoredAccount.unscoreable`). The status logic is pure and unit-testable now; Phase 10's `evidence.py` becomes a trivial wrapper.
- **D-09:** `retrieval_status` thresholds reuse existing semantics, no new tuning knobs: `empty` = no about text AND no news (mirrors `Enrichment.is_empty` / the unscoreable rule); `thin` = about text below the existing `ABOUT_TEXT_MIN_CHARS = 200` constant (the same threshold that triggers the Browserbase fallback today); `ok` otherwise.
- **D-10:** `EvidencePack` nests the existing frozen models: `justifications: tuple[Justification, ...]`, `news: tuple[NewsItem, ...]`. Keeps the 1-based index contract intact and `model_dump()` gives JSON for free. Snippet-size capping happens at the MCP boundary in Phase 10, not in the model.

### Refactor safety net
- **D-11:** Regression gate = the existing offline suite run untouched, PLUS new functional tests for `open_deps` itself: replay-bundle settings yield Replay* clients, record settings yield Recording* wrappers, live settings yield the real client types, and the httpx client is closed on context exit.
- **D-12:** Offline gates close the phase: full offline tests + strict mypy + lint. No live `make run` required; `make smoke` stays opt-in per CLAUDE.md (rate-limited endpoint, credits).

### Claude's Discretion
- Exact module placement of `NullBrowserbase` within `src/clients/` (own file vs alongside `browserbase_client.py`), naming/signature details of `RawContext` fields, docstring wording, and test file placement all follow existing conventions at the planner/executor's judgment.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design authority
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md` — Approved MCP server design (commit 3a46444). §"Config and wiring changes to existing code" defines Phase 9's four-file touch list; §"Testing" maps to the 5-layer strategy. NOTE: D-07 above deliberately deviates from its NullBrowserbase raise wording.
- `.planning/research/SUMMARY.md` — Milestone research; source of the dependency-driven build order and per-phase testing guidance.

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — INTEG-01/02/03 are this phase's requirements (v1.1 traceability table maps them to Phase 9).
- `.planning/ROADMAP.md` — Phase 9 goal and success criteria; criterion 3 needs rewording per D-07.

### Code seams being touched
- `src/pipeline.py` — `main()` lines ~295-327 hold the client-construction block to extract; `build_deps` and `Deps` at lines 43-64; `open_deps` lives next to `build_deps`.
- `src/enrich.py` — `_collect_context` (line 63) and `_RawContext` (line 27) to promote; `ABOUT_TEXT_MIN_CHARS = 200` is the thin threshold; `_number_justifications` already module-level.
- `src/clients/protocols.py` — `BrowserbaseLike.render(url) -> RenderedPage | None` is the contract `NullBrowserbase` must satisfy.
- `src/clients/browserbase_client.py` — `BrowserbaseClient.render` (lines 56-61) is where catch-and-continue actually lives; `BrowserbaseError` defined here.
- `src/models.py` — model conventions (`_Frozen` base, `extra="forbid"`, tuple collections, factory classmethods) that `EvidencePack` must follow.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Deps` dataclass + `build_deps()` (`src/pipeline.py:43-64`): the bundle `open_deps` yields; no changes needed to either.
- Replay/record infrastructure (`src/clients/replay.py`): Replay*/Recording* wrappers move into `open_deps` with the construction block; their tests double as wiring fixtures.
- `Enrichment.is_empty` and `ABOUT_TEXT_MIN_CHARS`: the exact semantics `EvidencePack.from_context` reuses for `empty`/`thin`.
- Factory-classmethod convention (`Citation.make`, `ScoredAccount.unscoreable`): the pattern `EvidencePack.from_context` follows.

### Established Patterns
- Frozen pydantic models with `extra="forbid"` and tuple collections; protocol-typed client boundaries (`ExaLike`, `BrowserbaseLike`, `LLMClient`) enable stub injection in tests without inheritance.
- Per-stage exception isolation in `process_account`; the null object must not introduce a new exception path through it (drives D-07).
- Strict mypy; every new function fully annotated; no new `ignore_missing_imports`.

### Integration Points
- `main()` becomes a thin consumer: `async with open_deps(settings) as deps:` replacing the inline block; Sheets writing and account loading stay in `main()`.
- Phase 10's `src/mcp_server/wiring.py` will consume `open_deps`; `src/mcp_server/evidence.py` will consume `collect_context` + `EvidencePack.from_context`.

</code_context>

<specifics>
## Specific Ideas

- The user consistently chose the convention-preserving option in every trade-off: reuse existing types and thresholds over inventing parallel ones, verbatim block moves over restructuring, and testing moved logic where it now lives.
- D-07 is the one place discussion overrode the written spec; planning must carry the deviation note forward so verification does not flag it as a miss.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Tier-aware `open_deps` was considered and explicitly rejected for Phase 9; Phase 10 owns thin-tier wiring.)

</deferred>

---

*Phase: 9-Pipeline Extraction & Supporting Models*
*Context gathered: 2026-07-15*
