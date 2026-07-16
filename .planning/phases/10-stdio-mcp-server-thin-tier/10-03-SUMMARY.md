---
phase: 10-stdio-mcp-server-thin-tier
plan: 3
subsystem: testing
tags: [mcp, stdio, subprocess, smoke-test, codex-client, error-sanitization]

requires:
  - phase: 10-stdio-mcp-server-thin-tier
    plan: 2
    provides: thin-tier FastMCP server, get_account_evidence tool, stderr-first stdio entrypoint
provides:
  - Opt-in make smoke-mcp gate that launches python -m src.mcp_server as a real subprocess over stdio
  - Live client proof that grounded evidence survives the stdio boundary with retrieval_status, about_text, numbered justifications, and citation URLs
  - Live invalid-domain and reconnect proof showing sanitized tool errors do not disconnect the server
affects: [11-rate-limits-streamable-http-transport, 12-full-tier-tool-resources-prompt, 13-hosted-deploy-docs-close]

tech-stack:
  added: []
  patterns:
    - "Transport smoke tests use the installed Python interpreter plus mcp.client.stdio so stdout framing is exercised without a nested uv process"
    - "Live-client verification requires valid, invalid, then valid calls so error sanitization and connection survival are proven together"

key-files:
  created:
    - tests/smoke/test_mcp_e2e.py
  modified:
    - Makefile

key-decisions:
  - "Codex was used as the real MCP client instead of Claude Code after Claude's session quota terminated the executor; the substitution was explicitly approved and exercised the same local stdio server plus an additional cross-client interoperability path"
  - "The live subprocess smoke was not repeated during closeout: it had already passed against notion.so before the quota interruption, and the resumed Codex client independently completed two live notion.so calls around the invalid-domain test"

patterns-established:
  - "Real-client gate: valid evidence call -> sanitized invalid-domain call -> second valid call, with no shell/web/direct-HTTP fallback allowed"

requirements-completed: [TEST-02, HOST-01]

coverage:
  - id: D1
    description: "make smoke-mcp launches the stdio server as a real subprocess against notion.so, asserts non-empty numbered cited evidence plus retrieval_status, skips without EXA_API_KEY, and stays excluded from make test"
    requirement: "TEST-02"
    verification:
      - kind: e2e
        ref: "make smoke-mcp (live notion.so run completed before executor quota termination)"
        status: pass
      - kind: integration
        ref: "env EXA_API_KEY= uv run pytest tests/smoke/test_mcp_e2e.py -v -rs (1 skipped)"
        status: pass
      - kind: integration
        ref: "make test (357 passed, 3 smoke tests deselected)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A real Codex MCP client connects to the local stdio server and receives grounded notion.so evidence with retrieval_status=ok, 1,974 characters of about_text, and 13 sequentially numbered justifications whose 13 citation URLs are all non-empty"
    requirement: "HOST-01"
    verification:
      - kind: manual_procedural
        ref: "Codex MCP tool mcp__poc_scraper__get_account_evidence live verification, valid notion.so call"
        status: pass
    human_judgment: false
  - id: D3
    description: "The real client receives a sanitized invalid-domain error with no stack trace, file path, environment detail, or secret, then completes another valid notion.so call on the same connection"
    requirement: "HOST-01"
    verification:
      - kind: manual_procedural
        ref: "Codex MCP tool valid-invalid-valid verification sequence"
        status: pass
    human_judgment: false

duration: 1h13m
completed: 2026-07-16
status: complete
---

# Phase 10 Plan 3: Real Stdio Transport Gates Summary

**Added a real-subprocess MCP smoke gate and verified the thin-tier server end to end through a real Codex stdio client, including grounded evidence, sanitized invalid-domain handling, and connection survival.**

## Performance

- **Duration:** 1h 13m elapsed across a provider-quota interruption and client substitution
- **Started:** 2026-07-16T18:56:35Z
- **Completed:** 2026-07-16T20:09:25Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Added `tests/smoke/test_mcp_e2e.py`, which launches `python -m src.mcp_server` as a real subprocess through `mcp.client.stdio`, initializes an MCP session, calls `get_account_evidence` for notion.so, and requires non-empty numbered justifications with citation URLs plus a `retrieval_status` honesty field.
- Added the opt-in `make smoke-mcp` target while retaining CI isolation through the existing `smoke` marker. The live run passed before the executor's quota interruption; the resumed closeout proved the no-key path skips cleanly and `make test` excludes all smoke tests.
- Verified the server through the configured Codex MCP client without shell, web, Python, or HTTP fallbacks: notion.so returned `ok`, 1,974 characters of about text, and 13 cited justifications; an invalid domain returned a sanitized error; a second valid call succeeded on the same connection.

## Task Commits

1. **Task 1: Subprocess smoke test over real stdio plus make smoke-mcp** - `1233455` (test)
2. **Task 2: Real-client verification session** - human checkpoint, no production-file commit

**Plan metadata:** committed separately during interrupted-plan closeout.

## Files Created/Modified

- `tests/smoke/test_mcp_e2e.py` - opt-in real-subprocess stdio smoke test against notion.so
- `Makefile` - `smoke-mcp` target and `.PHONY` registration

## Decisions Made

- Accepted Codex as the real MCP client after Claude Code credits were unavailable. This is an explicit client substitution, not a claim that Claude Code was exercised. It preserves the phase's transport purpose because Codex launches and calls the same local stdio MCP server, and it adds cross-client evidence.
- Did not repeat the paid Exa subprocess smoke during closeout. The interrupted executor had already completed it successfully, and the Codex verification made two additional live notion.so calls around the invalid-domain call.

## Deviations from Plan

### Approved client substitution

**1. Claude Code replaced by Codex for the real-client checkpoint**
- **Found during:** Task 2 (real-client verification)
- **Issue:** Claude's session quota terminated the executor and the user's remaining Claude surfaces shared the same exhausted credit pool.
- **Resolution:** The user configured the local stdio server in Codex and ran the plan's valid, invalid, then valid verification sequence using only `mcp__poc_scraper__get_account_evidence`.
- **Verification:** All requirements passed: 13/13 justifications had URLs, invalid-domain output contained no sensitive diagnostics, and the follow-up valid call succeeded.
- **Files modified:** None

---

**Total deviations:** 1 approved client substitution
**Impact on plan:** The named client changed, but the real stdio transport, structured evidence, error sanitization, and connection-survival properties were all exercised successfully. No production scope changed.

## Issues Encountered

- The original executor was terminated after Task 1 by a provider session-limit error. Safe-resume inspection found commit `1233455` but no summary or async-job manifest, so the plan was resumed manually at its blocking human-verification checkpoint instead of redispatching duplicate implementation work.
- Initial closeout gates could not access uv's cache inside the filesystem sandbox. The same commands were rerun with scoped approval and passed.

## Verification Results

- `env EXA_API_KEY= uv run pytest tests/smoke/test_mcp_e2e.py -v -rs` - 1 skipped, 0 failed
- `make test` - 357 passed, 3 smoke tests deselected
- `make typecheck` - strict mypy clean across 32 source files
- `make lint` - Ruff clean; Black would leave all 76 files unchanged
- Real Codex client - valid notion.so call passed, invalid-domain sanitization passed, follow-up notion.so call passed

## User Setup Required

The real-client check used a personal Codex MCP configuration pointing at this repository. It is not part of the public project and may be removed after verification if no longer needed.

## Next Phase Readiness

- Phase 10's thin-tier stdio surface is ready for Phase 11 to add rate limits and streamable HTTP transport.
- The Codex-for-Claude-Code client substitution must remain visible to the phase verifier; no other blocker is known.

---
*Phase: 10-stdio-mcp-server-thin-tier*
*Completed: 2026-07-16*
