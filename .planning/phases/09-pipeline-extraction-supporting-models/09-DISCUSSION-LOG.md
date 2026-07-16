# Phase 9: Pipeline Extraction & Supporting Models - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-15
**Phase:** 9-pipeline-extraction-supporting-models
**Areas discussed:** open_deps() seam shape, collect_context() public form, EvidencePack scope, Refactor safety net

---

## open_deps() seam shape

### What should open_deps() yield to its caller?

| Option | Description | Selected |
|--------|-------------|----------|
| Deps bundle | Yields the existing frozen Deps dataclass; simplest seam, matches how main() consumes it | ✓ |
| Raw clients bundle | New dataclass of (writer, judge, exa, browserbase); callers run build_deps themselves | |
| Both (deps + clients) | Struct exposing Deps and underlying clients; widest seam surface | |

**User's choice:** Deps bundle (recommended)

### Who owns the httpx.AsyncClient lifetime?

| Option | Description | Selected |
|--------|-------------|----------|
| open_deps creates it | Context manager opens/closes the shared client internally; self-contained seam | ✓ |
| Injected parameter | Optional client param; slightly more testable but tests inject at protocol layer anyway | |

**User's choice:** open_deps creates it (recommended)

### Do the replay/record branches move into open_deps() or stay in main()?

| Option | Description | Selected |
|--------|-------------|----------|
| Move into open_deps | Whole construction block moves verbatim incl. Replay/Recording branching; MCP inherits replay for free | ✓ |
| Stay in main() | open_deps builds only live clients; splits construction logic in two | |

**User's choice:** Move into open_deps (recommended)

### Should open_deps() be tier-aware in Phase 9?

| Option | Description | Selected |
|--------|-------------|----------|
| Tier-agnostic | Constructs everything from settings as main() does today; Phase 10 wires the thin tier itself | ✓ |
| Tier/mode parameter now | Anticipates Phase 10 but designs an API against a server that doesn't exist yet | |

**User's choice:** Tier-agnostic (recommended)

---

## collect_context() public form

### How should collect_context() be promoted, given Enricher requires an LLM the thin tier won't have?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level function | async def collect_context(account, *, exa, browserbase); Enricher.enrich() calls it; zero LLM involvement for thin tier | ✓ |
| Public method, LLM still required | Rename only; Phase 10 must construct Enricher with a dummy LLM | |
| Make Enricher's llm optional | One class but a partially-functional state mypy can't protect against | |

**User's choice:** Module-level function (recommended)

### NullBrowserbase raise vs the actual catch location (spec discrepancy)

| Option | Description | Selected |
|--------|-------------|----------|
| Return None, deviate from spec | render() logs "browserbase disabled" and returns None, matching BrowserbaseLike and the real client's failure behavior; collect_context untouched | ✓ |
| Raise + add catch in collect_context | Follows spec text literally but adds a catch the real client can never trigger, touching enrich in the "unchanged" phase | |
| Raise internally, catch internally | Mirrors BrowserbaseClient's structure; theatrical code | |

**User's choice:** Return None, deviate from spec (recommended)
**Notes:** The design spec claims collect_context already catches BrowserbaseError; in reality the catch-and-continue lives inside BrowserbaseClient.render(). A raising null object would mark whole accounts unscoreable. ROADMAP success criterion 3 must be reworded at planning.

### What should the public collect_context() return?

| Option | Description | Selected |
|--------|-------------|----------|
| Promote to RawContext | Public frozen dataclass; the type is part of the seam Phase 10 consumes | ✓ |
| Keep _RawContext private | Minimal diff but violates the underscore-is-private naming convention | |
| Return EvidencePack directly | Forces retrieval_status logic into enrich.py; changes Enricher internals | |

**User's choice:** Promote to RawContext (recommended)

---

## EvidencePack scope

### Just the model, or also the factory computing retrieval_status?

| Option | Description | Selected |
|--------|-------------|----------|
| Model + factory classmethod | EvidencePack.from_context() computing ok/thin/empty now; pure, unit-testable, follows Citation.make convention | ✓ |
| Bare model only | Satisfies the roadmap criterion literally; leaves status semantics undefined until Phase 10 | |

**User's choice:** Model + factory classmethod (recommended)

### How should retrieval_status thin/empty thresholds be defined?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing semantics | empty mirrors Enrichment.is_empty; thin = below ABOUT_TEXT_MIN_CHARS=200; one source of truth | ✓ |
| New dedicated constants | Decouples MCP honesty semantics from the scrape-fallback heuristic; second threshold to calibrate | |
| Justification-count based | Simple and citation-centric but diverges from how the pipeline judges thinness | |

**User's choice:** Reuse existing semantics (recommended)

### Nest existing models or flat wire-shape fields?

| Option | Description | Selected |
|--------|-------------|----------|
| Nest existing models | tuple[Justification, ...] / tuple[NewsItem, ...]; DRY, index contract intact, model_dump() gives JSON | ✓ |
| Flat wire-shape fields | Decouples wire format from internal models but duplicates schema | |

**User's choice:** Nest existing models (recommended)

---

## Refactor safety net

### How should we verify the open_deps() extraction changed nothing?

| Option | Description | Selected |
|--------|-------------|----------|
| Existing suite + new open_deps tests | Suite untouched as regression gate plus functional tests for replay/record/live wiring and client closure | ✓ |
| Existing suite only | Cheapest but the moved construction block would land untested | |
| Characterization test of main() first | Most rigorous; heavy for a verbatim block move (needs Sheets/CSV scaffolding) | |

**User's choice:** Existing suite + new open_deps tests (recommended)

### Does closing Phase 9 require live verification of make run?

| Option | Description | Selected |
|--------|-------------|----------|
| Offline suite is the gate | Full offline tests + strict mypy + lint; make smoke stays opt-in per CLAUDE.md | ✓ |
| One live make run before close | Highest confidence; burns credits, depends on live services | |
| Opt-in smoke, operator's call | Middle ground | |

**User's choice:** Offline suite is the gate (recommended)

---

## Claude's Discretion

- Module placement of NullBrowserbase within src/clients/ (own file vs alongside browserbase_client.py)
- RawContext field naming/signature details, docstring wording, test file placement — follow existing conventions

## Deferred Ideas

None — discussion stayed within phase scope. Tier-aware open_deps was considered and explicitly rejected for Phase 9 (Phase 10 owns thin-tier wiring).
