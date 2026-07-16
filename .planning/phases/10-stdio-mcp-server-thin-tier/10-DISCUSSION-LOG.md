# Phase 10: Stdio MCP Server (Thin Tier) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 10-stdio-mcp-server-thin-tier
**Areas discussed:** Evidence payload shape, Thin-tier Browserbase policy, Client verification + smoke, Error result design

---

## Evidence payload shape

### Q1: Include cleaned about_text in the payload?

| Option | Description | Selected |
|--------|-------------|----------|
| Add about_text, capped (Recommended) | Spec-faithful; Phase 12 research prompt scores axes from this evidence; already computed | ✓ |
| Justifications + news only | Keep EvidencePack as Phase 9 shipped it; documented spec deviation | |

**User's choice:** Add about_text, capped

### Q2: Where does about_text live?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend EvidencePack (Recommended) | Additive `about_text: str = ""` field; one model owns wire format; model_dump() stays single serialization path | ✓ |
| Wrap at the tool layer | Payload schema split across two places | |

**User's choice:** Extend EvidencePack

### Q3: How are MCP-boundary caps defined?

| Option | Description | Selected |
|--------|-------------|----------|
| Module constants (Recommended) | SCREAMING_SNAKE constants in evidence.py per SUMMARY_MAX_CHARS precedent (~2000/~300/~10); no new env knobs | ✓ |
| Env-tunable Settings fields | Tunable but adds knobs nobody asked for | |
| You decide | Claude picks at planning time | |

**User's choice:** Module constants

---

## Thin-tier Browserbase policy

### Q1: Real Browserbase fallback for a local thin-tier user with keys?

| Option | Description | Selected |
|--------|-------------|----------|
| Key-aware fallback (Recommended) | Real BrowserbaseClient when keys set, NullBrowserbase otherwise; honors spec; refines Phase 9 D-04 wording | ✓ |
| Always NullBrowserbase in thin tier | D-04 literal; one code path; silently worse evidence than CLI | |

**User's choice:** Key-aware fallback

---

## Client verification + smoke

### Q1: Which real client gates HOST-01?

| Option | Description | Selected |
|--------|-------------|----------|
| Claude Code (Recommended) | claude mcp add + live tool call; scriptable, zero GUI friction | ✓ |
| Claude Desktop | GUI config; closer to Phase 13 stranger flow but slower | |
| Both | Most thorough, most friction | |

**User's choice:** Claude Code

### Q2: Which live domain for make smoke-mcp?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse a fixtures.csv domain (Recommended) | notion.so / linear.app; same well-understood accounts as pipeline smoke | ✓ |
| A different dedicated domain | New variable without clear benefit | |
| You decide | Claude picks at planning time | |

**User's choice:** Reuse a fixtures.csv domain

---

## Error result design

### Q1: How do unexpected exceptions surface?

| Option | Description | Selected |
|--------|-------------|----------|
| Sanitizing catch-all now (Recommended) | Generic isError message out, full traceback to stderr; brings HOST-05 forward | ✓ |
| Rely on SDK defaults until Phase 13 | Less code now; exception text may leak paths/env; Phase 13 retrofit | |

**User's choice:** Sanitizing catch-all now

### Q2: Machine-readable error codes?

| Option | Description | Selected |
|--------|-------------|----------|
| Plain message only (Recommended) | Human-readable text per category; codes are speculative structure | ✓ |
| Message + error code | Stable codes for programmatic branching; more contract to maintain | |

**User's choice:** Plain message only

---

## Claude's Discretion

- Exact cap constant values and truncation mechanics (ellipsis markers, word boundaries)
- Startup tier log wording, including exa-only vs exa+browserbase sub-mode note
- Smoke-test driver mechanics and which of the two fixture domains
- Settings field scope for Phase 10; exact error-message wording
- Thin-tier httpx.AsyncClient lifespan ownership in wiring.py

## Deferred Ideas

None — discussion stayed within phase scope.
