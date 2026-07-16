---
phase: 10-stdio-mcp-server-thin-tier
verified: 2026-07-16T20:24:15Z
status: gaps_found
score: 6/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Calling get_account_evidence returns numbered, cited structured evidence whose evidence text is capped at the MCP boundary"
    status: partial
    reason: "about_text, justification summaries, and news count are capped, but nested Citation.snippet values and NewsItem.summary values survive unchanged and can dominate the serialized payload"
    artifacts:
      - path: "src/mcp_server/evidence.py"
        issue: "pack_from_context reuses original Citation and NewsItem objects after capping only the top-level about text and Justification.summary"
      - path: "tests/unit/test_evidence.py"
        issue: "tests never assert nested snippet or news-summary caps, nor a maximum serialized EvidencePack size"
    missing:
      - "Build MCP-safe copies of every nested Citation and NewsItem, removing or explicitly capping Citation.snippet and capping NewsItem.summary"
      - "Add a regression test covering every evidence-text path plus a defensible maximum serialized payload size"
  - truth: "Invalid domains surface as sanitized isError tool results before any provider request"
    status: partial
    reason: "the Account boundary rejects spaces and missing dots but accepts paths, queries, empty labels, leading hyphens, control characters, and overlength hostnames"
    artifacts:
      - path: "src/models.py"
        issue: "Account._normalize_domain is not a hostname validator and accepts malformed untrusted MCP input"
      - path: "tests/functional/test_mcp_server.py"
        issue: "the invalid-domain test covers only the literal value 'not a domain' and does not prove malformed hostnames are rejected before Exa is called"
    missing:
      - "Normalize supported HTTP(S) input to a hostname and reject paths, queries, fragments, userinfo, control characters, invalid labels, and overlength hostnames"
      - "Add unit and in-memory MCP tests proving malformed inputs return isError true without calling the provider"
deferred:
  - truth: "MCP-07 annotations and error semantics also apply to research_account_full"
    addressed_in: "Phase 12"
    evidence: "Phase 12 explicitly introduces the gated research_account_full tool; Phase 10 can verify the contract only for get_account_evidence"
---

# Phase 10: Stdio MCP Server (Thin Tier) Verification Report

**Phase Goal:** A local user can run the thin-tier MCP server over stdio and connect a real MCP client to retrieve grounded, cited account evidence.
**Verified:** 2026-07-16T20:24:15Z
**Status:** gaps_found
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A local user can run `make mcp`, connect a real MCP client over stdio, and retrieve cited evidence | VERIFIED | `Makefile:16-17` launches `python -m src.mcp_server`. The user-approved Codex client used only the configured MCP tool and received `retrieval_status=ok`, 1,974 characters of about text, and 13 sequential justifications with 13 non-empty URLs. The invalid call was followed by another successful valid call. The approved design names Codex among the intended MCP clients (`docs/superpowers/specs/2026-07-15-mcp-server-design.md:8`), so the substitution satisfies the real-client transport purpose while not claiming Claude Code-specific testing. |
| 2 | `get_account_evidence` returns numbered, cited structured JSON with honest status and all evidence text capped at the MCP boundary | FAILED | The structured model and visible caps exist, but `src/mcp_server/evidence.py:30-46` preserves raw nested citations and news. A production-equivalent crafted context serialized to 43,810 bytes with 2,000-character about citation snippets, 1,500-character news citation snippets, and 500-character news summaries. |
| 3 | Capability tier resolves correctly and is logged once at startup | VERIFIED | `src/config.py:183-201` implements missing-Exa failure, demo-forced thin, and full-tier key gating. `src/mcp_server/__main__.py:21-25` calls `resolve_and_log_tier` once before server run. Thin and full named tests passed. |
| 4 | Invalid domains, provider failures, and unexpected exceptions become sanitized `isError: true` tool results | FAILED | Provider and unexpected exception paths pass (`src/mcp_server/server.py:61-70`; named functional tests passed), and `not a domain` is sanitized. However `src/models.py:27-34` accepts malformed path, query, control-character, invalid-label, and overlength inputs, so those invalid domains proceed to retrieval instead of the promised invalid-domain result. |
| 5 | The evidence tool advertises read-only, non-destructive annotations and the `[N]` citation contract | VERIFIED | `src/mcp_server/server.py:41-49,73-80` registers the typed tool with both hints and a citation-contract description. `test_annotations_and_description_over_the_wire` passed. |
| 6 | Logging stays on stderr and real stdio JSON-RPC framing remains clean | VERIFIED | `src/mcp_server/__main__.py:1-18` configures root logging to stderr before project imports; no `print(` call exists under `src/mcp_server`. Both the real subprocess smoke and the configured Codex client completed MCP initialization/tool calls, which would fail on stdout contamination. |
| 7 | `make smoke-mcp` uses a real subprocess, succeeds live once, skips without Exa, and stays outside the offline suite | VERIFIED | `tests/smoke/test_mcp_e2e.py:35-60` uses `stdio_client` with `python -m src.mcp_server`; `Makefile:33-40` separates offline and opt-in targets. The prior live notion.so run is recorded as passing. Independent verifier run with `EXA_API_KEY=` produced one clean skip; collection found the smoke test under the registered marker. |
| 8 | The MCP SDK, EvidencePack wire field, and thin-tier server artifacts are substantive, wired, and pass offline gates | VERIFIED | `mcp==1.28.1` imports from the lockfile; `EvidencePack.about_text` is stored and serialized (`src/models.py:178-205`); all plan artifact and key-link queries passed. The orchestrator's closeout gates recorded 357 offline tests, strict mypy, Ruff, and Black green; verifier spot-checks added 9 passing named tests. |

**Score:** 6/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `pyproject.toml` / `uv.lock` | Official MCP SDK dependency | VERIFIED | Pin is `mcp>=1.28,<2.0`; lock resolves 1.28.1; FastMCP and ToolAnnotations import. |
| `src/models.py` | EvidencePack wire model and Account input model | PARTIAL | EvidencePack is substantive and wired. Account validation is too permissive for the MCP trust boundary. |
| `src/config.py` | MCP tier resolver | VERIFIED | Thin, full, demo-forced thin, and missing-Exa behavior are implemented and tested. |
| `src/mcp_server/evidence.py` | Boundary composition and caps | PARTIAL | Real data flows, but nested citation/news evidence text is not boundary-sanitized. |
| `src/mcp_server/wiring.py` | Thin lifespan and provider clients | VERIFIED | One shared HTTP client, Exa client, key-aware Browserbase fallback, and no LLM wiring. |
| `src/mcp_server/server.py` | FastMCP tool, annotations, and error translation | PARTIAL | Tool wiring and known error sanitization work; malformed domains pass the validation branch. |
| `src/mcp_server/__main__.py` | Stderr-first stdio entrypoint | VERIFIED | Tier resolution, server construction, and async stdio run are wired. |
| `tests/unit/test_evidence.py` | Evidence boundary regression coverage | PARTIAL | Visible caps/status are tested, but nested text and total payload size are not. |
| `tests/functional/test_mcp_server.py` | In-memory MCP behavior | PARTIAL | Happy/error/annotation/tier paths pass; malformed hostname-shaped arguments are uncovered. |
| `tests/smoke/test_mcp_e2e.py` | Real subprocess smoke | VERIFIED | Real stdio subprocess, initialization, structured result, status, numbering, and URLs are asserted. |
| `Makefile` | `mcp` and `smoke-mcp` entry points | VERIFIED | Both targets point to the intended module/test. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/mcp_server/__main__.py` | `src/mcp_server/server.py` | startup tier resolution and `build_server` | WIRED | Logging is configured before project imports; main calls both once. |
| `src/mcp_server/server.py` | `src/mcp_server/evidence.py` | `get_account_evidence` awaits `build_evidence_pack` | WIRED | Tool returns the typed EvidencePack directly. |
| `src/mcp_server/evidence.py` | `src/enrich.py` | `collect_context`, `_number_justifications`, shared status threshold | WIRED | Real Exa/Browserbase context flows into the pack. Boundary copy is incomplete. |
| `src/mcp_server/wiring.py` | Exa/Browserbase clients | lifespan dependency construction | WIRED | Thin tier uses Exa and optional Browserbase without LLM clients. |
| `Makefile` | `tests/smoke/test_mcp_e2e.py` | `smoke-mcp` target | WIRED | Opt-in target invokes the exact subprocess smoke module. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `get_account_evidence` | `EvidencePack` | `Account` -> lifespan deps -> `collect_context` -> `pack_from_context` | Yes, Exa plus optional Browserbase | PARTIAL: real data flows, but raw nested evidence text survives the MCP boundary |
| `test_mcp_e2e.py` | `structuredContent` | real child process and live Exa call | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Visible caps, structured result, sanitized errors, annotations, tier logs | Nine named unit/functional pytest nodes | 9 passed in 0.54s | PASS |
| No-key smoke behavior | `EXA_API_KEY= pytest ...::test_stdio_server_returns_live_evidence` | 1 skipped with the expected reason | PASS |
| Serialized boundary ceiling | Crafted production-equivalent `RawContext` -> `pack_from_context` -> `model_dump_json` | 43,810 bytes; nested snippets remained at 2,000/1,500 chars; news summaries remained at 500 | FAIL |
| Malformed domain rejection | Construct `Account` for path, query, empty-label, leading-hyphen, newline, tab, and overlength values | All seven values were accepted | FAIL |
| MCP SDK availability | Import installed SDK and print version | `mcp 1.28.1 imports ok` | PASS |

### Probe Execution

No phase probe scripts were declared or discovered. The smoke test is a pytest transport test, not a GSD probe script.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MCP-01 | 10-01, 10-02 | Numbered, cited structured evidence with honest status and boundary caps | BLOCKED | Structured evidence/status work; nested evidence text bypasses the intended boundary cap. |
| MCP-06 | 10-01, 10-02 | Resolve tier once and log it | SATISFIED | Source wiring plus passing thin/full/demo/missing-key tests. |
| MCP-07 | 10-02 | Tool annotations and domain failures as tool errors | BLOCKED | Current tool annotations and provider-error translation pass, but malformed domain inputs are accepted. The future full tool portion is recorded as deferred to Phase 12. |
| HOST-01 | 10-02, 10-03 | Run over stdio, stderr logging, real client connection | SATISFIED | Real Codex stdio client valid-invalid-valid sequence; design explicitly includes Codex as an intended client. This does not claim Claude Code-specific testing. |
| TEST-02 | 10-03 | Opt-in live subprocess smoke, skipped in CI | SATISFIED | Real subprocess test and Make target exist; live run recorded passing; independent no-key skip passed. |

All five Phase 10 requirement IDs appear in plan frontmatter. No Phase 10 requirement is orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/mcp_server/evidence.py` | 30-46 | Reuses raw nested evidence models across a trust boundary | BLOCKER | Violates MCP-01 boundary-cap contract and allows oversized agent-context payloads. |
| `src/models.py` | 27-34 | Weak hostname validation at untrusted MCP input boundary | WARNING with blocking truth impact | Malformed inputs can consume provider calls and inject control characters into logs instead of returning invalid-domain results. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers were found in Phase 10 source/test files. No placeholder implementation or stdout `print` call was found.

### Human Verification Required

None remaining. The external real-client checkpoint was completed by the user with an explicitly approved Codex substitution. The verifier did not repeat the paid live Exa smoke; the existing live-run record and the separate real-client valid-invalid-valid sequence are recorded with that limitation.

### Gaps Summary

Phase 10 has a functioning stdio MCP server and genuine real-client interoperability, but it is not complete against its own boundary contracts. The evidence pack must sanitize every nested evidence-text path before serialization, and the MCP input boundary must reject malformed domains before provider access. These gaps are not covered by a later phase's goal or success criteria, so they remain actionable Phase 10 gaps.

---

_Verified: 2026-07-16T20:24:15Z_
_Verifier: the agent (gsd-verifier, generic-agent compatibility workaround)_
