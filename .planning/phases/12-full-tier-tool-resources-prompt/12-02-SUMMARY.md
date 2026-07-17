---
phase: 12-full-tier-tool-resources-prompt
plan: 02
subsystem: api
tags: [mcp, fastmcp, resources, prompts, icp-rubric, eval-report]

# Dependency graph
requires:
  - phase: 10-stdio-mcp-server-thin-tier
    provides: FastMCP build_server, get_account_evidence tool, sanitizing except-chain pattern
  - phase: 12-full-tier-tool-resources-prompt (plan 01)
    provides: Deps exa/browserbase/limiter fields, process_account run_eval/on_stage params
provides:
  - icp://rubric resource serving configs/icp.yaml verbatim, application/yaml, per-request read
  - icp://eval-report resource serving evals/REPORT.md verbatim, text/markdown, per-request read
  - research_account(domain) static prompt teaching rubric-based, [N]-citation-disciplined scoring
affects: [12-03 (full-tier tool, will extend build_server further), 13-hosted-deploy-docs (README grounding-by-instruction vs grounding-by-construction contrast)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resource functions catch OSError inside the function body and return a sanitized string; never raise (a raise becomes an unsanitized protocol-level ResourceError, unlike tools which have an isError channel)"
    - "Prompts point at resources/tools rather than embedding their content, keeping the editable source of truth single (icp.yaml) and teaching the resource surface"

key-files:
  created:
    - tests/unit/test_mcp_resources.py
  modified:
    - src/mcp_server/server.py
    - tests/functional/test_mcp_server.py

key-decisions:
  - "Sanitized resource-failure messages differ per resource (\"the ICP rubric could not be read\" vs \"the eval calibration report could not be read\") so callers can tell which resource is degraded, verified by a distinguishability unit test"
  - "research_account prompt uses \"never fabricate\" (not an em dash) per CLAUDE.md's no-em-dash-in-published-markdown convention, applied here for consistency even though prompt text is not itself published markdown"

patterns-established:
  - "Resource read failure sanitization: try/except OSError inside the function body, log.warning with %-placeholders, return a non-empty 'resource unavailable: <what>' string"

requirements-completed: [MCP-02, MCP-03, MCP-04]

coverage:
  - id: D1
    description: "icp://rubric resource serves configs/icp.yaml verbatim with application/yaml mime type, read from disk on every request"
    requirement: "MCP-02"
    verification:
      - kind: unit
        ref: "tests/unit/test_mcp_resources.py::test_read_icp_rubric_returns_verbatim_file_content"
        status: pass
      - kind: unit
        ref: "tests/unit/test_mcp_resources.py::test_read_icp_rubric_sanitizes_read_failure"
        status: pass
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_rubric_resource_serves_verbatim_yaml"
        status: pass
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_list_resources_includes_rubric_and_eval_report"
        status: pass
    human_judgment: false
  - id: D2
    description: "icp://eval-report resource serves evals/REPORT.md verbatim with text/markdown mime type, read from disk on every request"
    requirement: "MCP-03"
    verification:
      - kind: unit
        ref: "tests/unit/test_mcp_resources.py::test_read_eval_report_returns_verbatim_file_content"
        status: pass
      - kind: unit
        ref: "tests/unit/test_mcp_resources.py::test_read_eval_report_sanitizes_read_failure"
        status: pass
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_eval_report_resource_serves_verbatim_markdown"
        status: pass
    human_judgment: false
  - id: D3
    description: "A missing/unreadable resource file degrades to a sanitized, non-empty, resource-naming message (never a protocol error, never empty content), with the real cause logged at WARNING"
    requirement: "MCP-02"
    verification:
      - kind: unit
        ref: "tests/unit/test_mcp_resources.py::test_rubric_and_eval_report_sanitized_messages_are_distinguishable"
        status: pass
    human_judgment: false
  - id: D4
    description: "research_account(domain) prompt points at icp://rubric and get_account_evidence, mandates [N] citation indices with drop-uncited and never-fabricate rules, and never mentions research_account_full"
    requirement: "MCP-04"
    verification:
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_research_account_prompt_contains_required_elements"
        status: pass
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_research_account_prompt_never_mentions_full_tier_tool"
        status: pass
      - kind: functional
        ref: "tests/functional/test_mcp_server.py::test_list_prompts_includes_research_account_with_required_domain_arg"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-17
status: complete
---

# Phase 12 Plan 02: Full-Tier Tool, Resources & Prompt Summary

**icp://rubric and icp://eval-report MCP resources plus a static research_account prompt enforcing [N]-citation discipline, all registered unconditionally on every tier**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-17T04:26:00Z
- **Completed:** 2026-07-17T04:33:00Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `icp://rubric` and `icp://eval-report` resources serve `configs/icp.yaml` and `evals/REPORT.md` verbatim, read from disk per request, with correct `application/yaml`/`text/markdown` mime types
- Resource read failures (D-08) degrade to sanitized, resource-naming, non-empty messages with the real `OSError` logged at WARNING and never reaching the client
- `research_account(domain)` static prompt teaches rubric-based scoring: read `icp://rubric`, call `get_account_evidence`, score axes 1-5, propose 3 personas, draft outreach, with hard `[N]`-citation and never-fabricate rules, identical on every tier (never mentions `research_account_full`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Serve icp://rubric and icp://eval-report with per-request reads and sanitized failures** - `5e4db08` (feat)
2. **Task 2: Add the static research_account prompt teaching rubric-based, citation-disciplined scoring** - `6f0f5c1` (feat)

**Tests (both tasks' RED phase, combined for efficiency):** `e651a7e` (test)

**Plan metadata:** (this commit)

_Note: RED tests for tasks 1 and 2 were written together in one commit (`e651a7e`) since both extend the same two test files and were designed together against the same read_first context; GREEN implementation was then split into two commits, one per task, for traceability._

## Files Created/Modified
- `tests/unit/test_mcp_resources.py` - 5 unit tests calling `read_icp_rubric`/`read_eval_report` directly: verbatim content, D-08 sanitized-failure behavior, and message distinguishability
- `tests/functional/test_mcp_server.py` - 6 new functional tests over the in-memory session: resource round-trips (`read_resource`, `list_resources`) and prompt round-trips (`get_prompt`, `list_prompts`)
- `src/mcp_server/server.py` - `read_icp_rubric`, `read_eval_report`, `research_account` functions plus their registration in `build_server`

## Decisions Made
- Sanitized failure messages are resource-specific ("the ICP rubric could not be read..." vs "the eval calibration report could not be read...") so a client-visible message names which resource degraded, without leaking the filesystem path (asserted by a dedicated distinguishability test)
- MIME types: `application/yaml` for the rubric (RFC 9512), `text/markdown` for the eval report (RFC 7763), per RESEARCH.md Pitfall 5
- Prompt wording uses "researched, never fabricate" rather than an em dash, consistent with the project's no-em-dash-in-published-markdown convention

## Deviations from Plan

None - plan executed exactly as written. RED tests for both tasks were combined into a single commit rather than one RED commit per task; this is a commit-sequencing choice, not a scope or behavior deviation, and every acceptance criterion in the plan (including per-task `-k` filtered pytest invocations) was independently verified to pass before its respective GREEN commit.

## Issues Encountered
- `black` reformatted two lines (a wrapped f-string and a multi-line tuple) after the initial GREEN implementation; ran `make lint` to catch it before committing, applied `black`, and re-verified all 476 offline tests, `mypy`, and `ruff`/`black` still pass clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `build_server` now serves both thin-tier resources and the static prompt unconditionally; Plan 12-03 (full-tier `research_account_full` tool) extends the same file with tier-conditional tool registration, reusing the sanitizing except-chain pattern documented here
- Phase 13's README can now cite the shipped `research_account` prompt as the concrete "grounding-by-instruction" example to contrast against the pipeline's "grounding-by-construction" (dropped-uncited-claims) story

---
*Phase: 12-full-tier-tool-resources-prompt*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files exist on disk and all referenced commit hashes (`e651a7e`, `5e4db08`, `6f0f5c1`) are present in git history.
