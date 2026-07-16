---
phase: 10-stdio-mcp-server-thin-tier
verified: 2026-07-16T21:19:11Z
status: gaps_found
score: 6/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/8
  gaps_closed:
    - "The original nested Citation snippet and NewsItem summary payload-cap bypass is closed by MCP-safe frozen copies and an exact 24000-byte UTF-8 serialization ceiling"
  gaps_remaining:
    - "MCP-01 remains partial because invalid provenance is filtered after the ten-item news slice, so later valid cited news can be discarded and retrieval_status can become falsely empty"
    - "MCP-07 remains partial because empty query/fragment delimiters, IPv4 literals, and invalid IDNA A-labels are accepted and reach Exa"
  regressions: []
gaps:
  - truth: "Calling get_account_evidence returns numbered, cited structured evidence with an honest retrieval_status and all evidence text capped at the MCP boundary"
    status: partial
    reason: "The byte and nested-text caps now hold, but pack_from_context slices news to ten before removing over-limit provenance. Ten invalid URL units followed by a valid eleventh produce an empty pack instead of the available cited evidence."
    artifacts:
      - path: "src/mcp_server/evidence.py"
        issue: "pack_from_context applies ctx.news_items[:NEWS_ITEM_MCP_CAP] before _url_within_cap filtering"
      - path: "tests/unit/test_evidence.py"
        issue: "No regression covers over-limit news before a later valid item"
    missing:
      - "Filter over-limit news units first while preserving relative order, then take the first NEWS_ITEM_MCP_CAP retained units"
      - "Add a regression with ten over-limit items followed by one safe item and assert the safe item, sequential numbering, and non-empty honest status"
  - truth: "Invalid domains surface as sanitized isError tool results before any provider request"
    status: partial
    reason: "The named malformed families from the first verification are rejected, but empty query/fragment delimiters, IPv4 literals, and invalid IDNA A-labels still normalize successfully and trigger Exa calls."
    artifacts:
      - path: "src/models.py"
        issue: "urlsplit value checks miss empty ?/# syntax; DNS_LABEL accepts numeric IP literals and does not validate xn-- labels by IDNA round-trip"
      - path: "tests/unit/test_models.py"
        issue: "The malformed-host matrix omits empty delimiters, IP literals, and invalid A-labels"
      - path: "tests/functional/test_mcp_server.py"
        issue: "The zero-provider-call matrix omits the residual accepted forms"
    missing:
      - "Reject query/fragment delimiter syntax even when its parsed value is empty"
      - "Reject IP literals and require xn-- labels to pass standard-library IDNA decode and round-trip validation"
      - "Add unit and in-memory MCP regressions proving each form returns isError true with zero Exa calls"
deferred:
  - truth: "MCP-07 annotations and error semantics also apply to research_account_full"
    addressed_in: "Phase 12"
    evidence: "Phase 12 explicitly introduces the gated research_account_full tool; Phase 10 can verify the contract only for get_account_evidence"
---

# Phase 10: Stdio MCP Server (Thin Tier) Verification Report

**Phase Goal:** A local user can run the thin-tier MCP server over stdio and connect a real MCP client to retrieve grounded, cited account evidence.
**Verified:** 2026-07-16T21:19:11Z
**Status:** gaps_found
**Re-verification:** Yes, after plan 10-04 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A local user can run `make mcp`, connect a real MCP client over stdio, and retrieve cited evidence | VERIFIED | Quick regression check: `Makefile` still launches `python -m src.mcp_server`; the existing user-approved Codex valid-invalid-valid session remains the real-client proof and was not repeated. |
| 2 | `get_account_evidence` returns numbered, cited structured JSON with honest status and all evidence text capped at the MCP boundary | FAILED | The original cap bypass is closed: nested citation title/snippet fields are cleared, text fields are bounded, and exact UTF-8 serialization is limited to 24,000 bytes. However, ten over-limit news URLs followed by one valid item produce `retrieval_status="empty"`, zero news, and zero justifications because filtering occurs after the ten-item slice. |
| 3 | Capability tier resolves correctly and is logged once at startup | VERIFIED | Quick regression check: `src/config.py` tier logic and `src/mcp_server/__main__.py` startup call remain wired; the orchestrator-confirmed offline suite includes the thin/full/demo/missing-key tests. |
| 4 | Invalid domains, provider failures, and unexpected exceptions become sanitized `isError: true` tool results before provider access | FAILED | Provider and unexpected-exception handling remain wired, and 12 malformed-domain cases pass with zero Exa calls. Independent in-memory probes show `example.com?`, `127.0.0.1`, and invalid A-label `xn--a.example` return `isError=False` and each trigger both Exa calls. |
| 5 | The evidence tool advertises read-only, non-destructive annotations and the `[N]` citation contract | VERIFIED | Quick regression check: annotations and tool description remain registered in `src/mcp_server/server.py`; the relevant functional test remains present and included in the green offline suite. |
| 6 | Logging stays on stderr and real stdio JSON-RPC framing remains clean | VERIFIED | Quick regression check: stderr-first entrypoint remains unchanged and `src/mcp_server` still has no `print(` call. Existing subprocess and Codex client transport evidence remains valid. |
| 7 | `make smoke-mcp` uses a real subprocess, succeeds live once, skips without Exa, and stays outside the offline suite | VERIFIED | Quick regression check: the smoke file and Make target remain wired. The paid live smoke was intentionally not rerun; prior live and no-key skip evidence remains unchanged. |
| 8 | The MCP SDK, EvidencePack wire field, and thin-tier server artifacts are substantive, wired, and pass offline gates | VERIFIED | All four artifact queries passed (17/17 artifacts) and all four key-link queries passed (11/11 links). The orchestrator reports 398 tests passed with 3 smoke tests deselected, strict mypy clean, Ruff clean, and Black clean. |

**Score:** 6/8 truths verified

### Prior Gap Closure

| Prior Gap | Re-verification Result | Evidence |
|---|---|---|
| Nested evidence text bypassed MCP caps | CLOSED | `src/mcp_server/evidence.py:54-146` creates safe frozen copies and measures final UTF-8 JSON bytes. Three focused evidence tests passed, including multibyte/escaping and indivisible URL cases. |
| Malformed hostnames reached Exa | REMAINS PARTIAL | The original path/query-value/fragment-value/userinfo/port/control/label-length matrix now passes with zero calls, but empty delimiters, IP literals, and invalid A-labels remain accepted and wired to Exa. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/mcp_server/evidence.py` | Complete MCP boundary composition and exact byte cap | PARTIAL | Nested fields and final serialization are bounded, but cap-before-filter ordering can discard later safe news. |
| `tests/unit/test_evidence.py` | Adversarial boundary regressions | PARTIAL | Original payload gap is well covered; later-safe-news ordering is not. |
| `src/models.py` | Strict shared domain normalization | PARTIAL | Most malformed inputs are rejected, but residual non-domain forms pass. |
| `tests/unit/test_models.py` | Valid/invalid hostname matrix | PARTIAL | Omits empty delimiters, IP literals, and invalid A-labels. |
| `tests/functional/test_mcp_server.py` | MCP errors before provider access | PARTIAL | Twelve malformed cases prove zero calls; residual accepted forms are uncovered. |
| `src/mcp_server/server.py` | FastMCP tool, annotations, and error translation | VERIFIED | Account construction still precedes lifespan access and retrieval; provider and unexpected errors use fixed client messages. |
| `src/mcp_server/wiring.py` | Thin-tier provider lifespan | VERIFIED | Shared client and key-aware Browserbase selection remain substantive and wired. |
| `src/mcp_server/__main__.py` | Stderr-first stdio entrypoint | VERIFIED | Tier resolution, server construction, and async stdio run remain wired. |
| `tests/smoke/test_mcp_e2e.py` / `Makefile` | Opt-in real-subprocess transport gate | VERIFIED | Artifact and key-link queries pass; no paid rerun was needed for this code-only gap closure. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/mcp_server/server.py` | `src/mcp_server/evidence.py` | tool delegates to `build_evidence_pack` | WIRED | Tool reaches real retrieval and packing code. |
| `src/mcp_server/evidence.py` | `src/enrich.py` | `collect_context`, shared numbering, shared status threshold | PARTIAL | Real data flows, but news filtering order can hide later valid evidence. |
| `src/mcp_server/server.py` | `src/models.py` | constructs `Account` before retrieval | WIRED | This correct wiring makes the residual validator acceptance observable as provider calls. |
| `tests/functional/test_mcp_server.py` | `FakeExa.calls` | proves boundary rejection before provider use | PARTIAL | Wired and passing for listed cases, but residual accepted forms are absent. |
| `src/mcp_server/__main__.py` | server and lifespan | startup resolution and stdio run | WIRED | Unchanged quick regression pass. |
| `Makefile` | smoke test | `smoke-mcp` target | WIRED | Unchanged quick regression pass. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `get_account_evidence` | `EvidencePack` | `Account` -> lifespan deps -> `collect_context` -> `pack_from_context` | Yes, Exa plus optional Browserbase | PARTIAL: real data and hard size bounds hold, but valid later news can be lost before packing. |
| Domain error path | tool argument -> `Account` -> Exa | MCP client input | Yes | PARTIAL: many invalid forms stop before Exa, but the residual forms normalize and cross the provider boundary. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Original nested payload-cap gap | Three focused `tests/unit/test_evidence.py` nodes | 3 passed | PASS |
| Original malformed-domain families stop before Exa | `test_invalid_domain_sanitized_error_before_provider_access` | 12 parameter cases passed; combined focused run was 15 passed | PASS |
| Empty delimiter, IPv4, and invalid A-label rejection | Direct `Account` plus in-memory MCP probes | All accepted; each MCP call returned `isError=False` and recorded `about:` plus `news:` Exa calls | FAIL |
| Preserve valid cited news after invalid provenance | Crafted `RawContext` with ten over-limit URLs then one safe URL | `retrieval_status='empty'`, zero news, zero justifications | FAIL |
| Invalid-domain error response size | One-million-character invalid input | Pydantic validator message length 1,000,031 characters | WARNING: unbounded client-input reflection, but not an independent failure of MCP-07's isError/no-provider contract |
| Offline regression gates | Orchestrator's full suite, strict mypy, Ruff, Black | 398 passed/3 deselected; all static gates clean | PASS |

### Probe Execution

No phase probe scripts were declared or discovered. The paid live MCP smoke was not rerun during this code-only re-verification.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| MCP-01 | 10-01, 10-02, 10-04 | BLOCKED | Exact byte/nested-text caps pass, but valid cited news can be discarded before the cap and status can become falsely empty. |
| MCP-06 | 10-01, 10-02 | SATISFIED | Tier implementation and startup wiring unchanged; offline tests green. |
| MCP-07 | 10-02, 10-04 | BLOCKED | Most malformed inputs stop before Exa, but residual empty-delimiter/IP/invalid-A-label forms reach Exa. The future full-tool portion remains deferred to Phase 12. |
| HOST-01 | 10-02, 10-03 | SATISFIED | Existing real Codex stdio client proof and stderr-only source wiring remain valid. |
| TEST-02 | 10-03 | SATISFIED | Real subprocess smoke remains present, wired, opt-in, and previously passed live. |

All five Phase 10 requirement IDs appear in plan frontmatter. No requirement is orphaned.

### Independent Review-Warning Assessment

| Review Finding | Verifier Classification | Must-Have Impact |
|---|---|---|
| Empty delimiters, IP literals, invalid A-labels accepted | BLOCKER | Directly falsifies the invalid-domain-before-provider truth and MCP-07. |
| Complete invalid input reflected in error text | WARNING | A real context-budget/DoS weakness. It does not independently falsify the explicit Phase 10 requirement, which requires sanitized `isError` results and no provider call; the echoed value is client-supplied rather than an internal diagnostic. Fixing it alongside the domain gap is recommended. |
| News sliced before provenance filtering | BLOCKER | Falsifies MCP-01's honest evidence/status truth for a valid later evidence unit and contradicts plan 10-04's filter-then-cap contract. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/mcp_server/evidence.py` | 155-157 | Applies count cap before validity filter | BLOCKER | Valid cited evidence after invalid units is never considered, yielding a false empty result. |
| `src/models.py` | 43-80 | Parser checks parsed values but not empty delimiter syntax; hostname regex is not an IP/IDNA validity check | BLOCKER | Malformed/non-domain inputs reach the paid provider boundary. |
| `src/models.py` | 31-34 | Reflects complete invalid input in the client-visible error | WARNING | A one-million-character input creates an approximately one-million-character error result. |

No unreferenced `TBD`, `FIXME`, or `XXX` markers, placeholder implementations, or stdout `print` calls were found in the Phase 10 source/test surface.

### Human Verification Required

None. Existing real-client transport evidence remains sufficient, and both remaining blockers are deterministic offline behaviors.

### Gaps Summary

Plan 10-04 closes the original serialized-payload bypass, but Phase 10 still has two requirement-level gaps. Evidence filtering must occur before the count cap so later valid citations are not lost, and the shared Account boundary must reject empty URL delimiters, IP literals, and invalid A-labels before Exa. The unbounded invalid-input reflection is a non-blocking warning that should be fixed in the same small boundary pass. No later phase explicitly owns the two blockers, so neither is deferred.

Tracking note: ROADMAP.md and REQUIREMENTS.md currently mark Phase 10 complete, but this re-verification result is `gaps_found`; closeout tracking should not advance until the structured gaps above are planned, executed, and re-verified.

---

_Verified: 2026-07-16T21:19:11Z_
_Verifier: the agent (gsd-verifier, generic-agent compatibility workaround)_
