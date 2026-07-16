---
phase: 10-stdio-mcp-server-thin-tier
verified: 2026-07-16T21:41:23Z
status: passed
score: 8/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/8
  gaps_closed:
    - "MCP-01: invalid news provenance is filtered before the ten-item cap, so later valid cited news is retained with sequential numbering and an honest non-empty status"
    - "MCP-07: empty delimiters, IP literals, and invalid IDNA A-labels are rejected before provider access, and invalid-domain errors are bounded without raw-input reflection"
  gaps_remaining: []
  regressions: []
gaps: []
deferred:
  - truth: "MCP-07 annotations and error semantics also apply to research_account_full"
    addressed_in: "Phase 12"
    evidence: "Phase 12 explicitly introduces the gated research_account_full tool; Phase 10 verifies the contract for get_account_evidence"
---

# Phase 10: Stdio MCP Server (Thin Tier) Verification Report

**Phase Goal:** A local user can run the thin-tier MCP server over stdio and connect a real MCP client to retrieve grounded, cited account evidence.
**Verified:** 2026-07-16T21:41:23Z
**Status:** passed
**Re-verification:** Yes, after Plan 10-05 final gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A local user can run `make mcp`, connect a real MCP client over stdio, and retrieve cited evidence | VERIFIED | `Makefile` launches `python -m src.mcp_server`; Plan 10-03 records the accepted Codex real-client valid-invalid-valid session with two successful `notion.so` calls and 13/13 cited justifications. |
| 2 | `get_account_evidence` returns numbered, cited structured JSON with honest status and all evidence text capped at the MCP boundary | VERIFIED | `src/mcp_server/evidence.py:54-160` creates MCP-safe frozen copies, enforces the exact 24,000-byte UTF-8 serialization ceiling, filters invalid provenance before the ten-item cap, and rebuilds sequential justifications. Focused adversarial probes passed. |
| 3 | Capability tier resolves correctly and is logged once at startup | VERIFIED | `src/config.py::Settings.mcp_tier()` owns the thin/full/demo matrix; `src/mcp_server/__main__.py:21-25` resolves and logs once before running the server. The full offline suite covers the tier matrix. |
| 4 | Invalid domains, provider failures, and unexpected exceptions become sanitized `isError: true` tool results before provider access | VERIFIED | `src/models.py:31-99` rejects delimiter, authority, IP, and invalid IDNA forms with constant wording. The focused in-memory MCP matrix passed 22 malformed inputs with `FakeExa.calls == []`; the one-million-character case returned a bounded result. |
| 5 | The evidence tool advertises read-only, non-destructive annotations and the `[N]` citation contract | VERIFIED | `src/mcp_server/server.py` registers `ToolAnnotations(readOnlyHint=True, destructiveHint=False)` and documents the `[N]` requirement; the functional wire test is included in the green suite. |
| 6 | Logging stays on stderr and real stdio JSON-RPC framing remains clean | VERIFIED | `src/mcp_server/__main__.py:1-25` configures stderr before project imports and runs stdio with no `print(` calls under `src/mcp_server`; the prior live subprocess and Codex client sessions passed. |
| 7 | `make smoke-mcp` uses a real subprocess, succeeds live once, skips without Exa, and stays outside the offline suite | VERIFIED | `tests/smoke/test_mcp_e2e.py:35-60` launches the installed interpreter through `mcp.client.stdio`; Plan 10-03 records the successful live run and the no-key skip. The paid smoke was intentionally not repeated. |
| 8 | The MCP SDK, EvidencePack wire field, thin-tier server artifacts, and gap fixes are substantive, wired, and pass offline gates | VERIFIED | `mcp>=1.28,<2.0` remains pinned; all Phase 10 source and tests are present. Parent gates passed: 421 offline tests, 3 smoke tests deselected, strict mypy clean, Ruff clean, and Black clean. |

**Score:** 8/8 truths verified

## Re-verification of Prior Gaps

| Prior Gap | Result | Evidence |
|---|---|---|
| Valid news after ten invalid provenance units was discarded | CLOSED | `src/mcp_server/evidence.py:149-160` filters the complete ordered tuple before slicing. `tests/unit/test_evidence.py:221-261` proves the safe eleventh item survives, retains its URL, receives index 1, reports `ok`, and preserves first-ten retained ordering. |
| Empty `?`/`#`, IP literals, and invalid IDNA A-labels reached Exa | CLOSED | `src/models.py:37-98` rejects delimiter syntax, parsed authority violations, IP addresses, and A-labels that fail exact IDNA round-trip. `tests/functional/test_mcp_server.py:98-138` proves all listed families return `isError: true` with zero Exa calls. |
| Invalid-domain errors reflected arbitrarily large client input | CLOSED | `src/models.py:34-35` uses constant `invalid domain` wording. `tests/functional/test_mcp_server.py:141-156` sends an approximately one-million-character input and asserts a result no larger than 256 UTF-8 bytes, no raw suffix, and zero Exa calls. |

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/mcp_server/evidence.py` | Complete MCP boundary composition and exact byte cap | VERIFIED | Filter-before-cap selection, safe nested copies, exact serialization measurement, deterministic reduction, honest status, and unchanged retained URLs are implemented. |
| `tests/unit/test_evidence.py` | Adversarial boundary regressions | VERIFIED | Covers multibyte and escaping overhead, long URLs, nested citation text, deterministic reduction, valid-tail recovery, ordering, numbering, and status. |
| `src/models.py` | Strict shared domain normalization | VERIFIED | Accepts documented bare/root HTTP(S) ASCII or valid punycode hostnames; rejects all residual malformed and non-domain forms with bounded wording. |
| `tests/unit/test_models.py` | Valid and invalid hostname matrix | VERIFIED | Includes empty delimiters, IPv4/IPv6 literals, valid punycode, invalid A-labels, paths, ports, userinfo, controls, and length boundaries. |
| `tests/functional/test_mcp_server.py` | MCP errors before provider access | VERIFIED | In-memory client proves sanitized `isError` results, bounded error size, and zero `FakeExa` calls. |
| `src/mcp_server/server.py` | FastMCP tool, annotations, and error translation | VERIFIED | Account construction precedes lifespan access and retrieval; provider and unexpected failures use fixed client messages. |
| `src/mcp_server/wiring.py` | Thin-tier provider lifespan | VERIFIED | Shared HTTP client and key-aware Browserbase selection are substantive and do not construct LLM clients. |
| `src/mcp_server/__main__.py` | Stderr-first stdio entrypoint | VERIFIED | Tier resolution, server construction, and async stdio run are wired after stderr logging configuration. |
| `tests/smoke/test_mcp_e2e.py` / `Makefile` | Opt-in real-subprocess transport gate | VERIFIED | The smoke target and real stdio subprocess test remain wired and excluded from offline CI. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/mcp_server/server.py` | `src/mcp_server/evidence.py` | Tool delegates to `build_evidence_pack` | WIRED | Tool calls real retrieval and packing code and returns `EvidencePack` directly. |
| `src/mcp_server/evidence.py` | `src/enrich.py` | Shared collection, numbering, and status threshold | WIRED | The same retained news tuple drives both the `news` field and numbered justifications after provenance filtering. |
| `src/mcp_server/server.py` | `src/models.py` | Constructs `Account` before lifespan access | WIRED | Invalid domains stop at the shared model boundary before any provider collaborator is accessed. |
| `tests/functional/test_mcp_server.py` | `FakeExa.calls` | Direct provider-boundary assertion | WIRED | Every malformed-input case and the million-character case assert an empty call list. |
| `src/mcp_server/__main__.py` | Server and lifespan | Startup resolution and stdio run | WIRED | Logging configuration precedes project imports; startup resolves tier once and runs FastMCP stdio. |
| `Makefile` | Smoke test | `smoke-mcp` target | WIRED | Target runs the dedicated subprocess smoke module and remains separate from `make test`. |

## Behavioral Spot-Checks

| Behavior | Command / Evidence | Result | Status |
|---|---|---|---|
| Preserve valid cited news after invalid provenance | Focused `test_pack_from_context_filters_invalid_news_before_count_cap` | Safe eleventh item retained, URL unchanged, index 1, status `ok`, serialized budget held | PASS |
| Preserve first-ten retained order | Focused `test_pack_from_context_keeps_first_ten_valid_news_in_source_order` | First ten valid items retained in original relative order with sequential indices | PASS |
| Reject residual malformed domains before Exa | Focused parameterized in-memory MCP test | 22 cases passed, including empty delimiters, IPv4, IPv6, and invalid A-label; every case had zero Exa calls | PASS |
| Bound invalid-domain error response | Focused one-million-character in-memory MCP test | `isError: true`, contains `invalid domain`, no raw suffix, at most 256 UTF-8 bytes, zero Exa calls | PASS |
| Focused re-verification run | Four focused test nodes | 25 passed in 0.75s | PASS |
| Offline regression gates | Parent orchestrator gates after Plan 10-05 | 421 passed, 3 deselected; strict mypy, Ruff, and Black clean | PASS |
| Real transport and client interoperability | Existing Plan 10-03 live evidence | Live subprocess passed; Codex valid-invalid-valid sequence passed on one configured stdio connection | PASS |

## Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|---|---|---|---|
| MCP-01 | 10-01, 10-02, 10-04, 10-05 | SATISFIED | Structured numbered evidence, honest status, nested text and URL controls, exact UTF-8 byte ceiling, and filter-before-cap selection are implemented and tested. |
| MCP-06 | 10-01, 10-02 | SATISFIED | Thin/full/demo tier matrix and single startup logging are wired and covered offline. |
| MCP-07 | 10-02, 10-04, 10-05 | SATISFIED | Read-only annotations and sanitized `isError` domain/provider/unexpected failure paths are verified; invalid input cannot reach Exa. The future full-tool portion remains assigned to Phase 12. |
| HOST-01 | 10-02, 10-03 | SATISFIED | `make mcp`, stderr-only logging, real subprocess framing, and the accepted real Codex stdio client sequence all passed. |
| TEST-02 | 10-03 | SATISFIED | Opt-in real-subprocess smoke exists, is isolated from offline tests, skips without Exa, and passed live once. |

All five Phase 10 requirement IDs appear in plan frontmatter and in the current requirements traceability table. No requirement is orphaned.

## Prior Review Finding Resolution

`10-REVIEW.md` predates Plan 10-05. Its three warnings are now closed by commits `ac5e477` and `9c30397` plus focused regressions in `4d3f15f` and `871a4d1`:

1. Empty delimiters, IP literals, and invalid A-labels are rejected before provider access.
2. Invalid-domain errors no longer reflect raw client input and remain bounded.
3. Invalid provenance is removed before the news count cap, preserving later safe evidence.

No new blocker, warning, placeholder, stdout `print` call, or requirement-level regression was found in the Plan 10-05 surface.

## Probe Execution

No phase probe scripts were declared or discovered. The focused deterministic regressions were run directly. The paid live MCP smoke was not rerun because transport and live retrieval evidence already passed and Plan 10-05 changed only offline evidence-selection and input-validation boundaries.

## Human Verification Required

None. The real-client checkpoint is already complete, and all final gap-closure behaviors are deterministic and automated.

## Gaps Summary

No gaps remain. Plan 10-05 closes both requirement-level blockers and the related error-size warning from the previous 6/8 verification. Phase 10 now meets its stdio thin-tier goal and all five assigned requirements with 8/8 observable truths verified.

---

_Verified: 2026-07-16T21:41:23Z_
_Verifier: the agent (gsd-verifier, generic-agent compatibility workaround)_
