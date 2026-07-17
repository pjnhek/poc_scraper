---
phase: 12-full-tier-tool-resources-prompt
verified: 2026-07-17T05:07:15Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 12: Full-Tier Tool, Resources & Prompt Verification Report

**Phase Goal:** BYOK users get the complete grounded pipeline as a gated MCP tool, and any client can read the rubric, the eval report, and a guided research prompt.
**Verified:** 2026-07-17T05:07:15Z
**Status:** passed
**Re-verification:** No — initial verification

> **Scope note:** This report verifies feature must-haves (MCP-02..05 behavior) only. It is not a security verdict. `12-REVIEW.md` records 3 warnings (full-tier HTTP exposure unmetered, progress-failure discarding completed runs, unguarded tier/lifespan pairing); their resolution is tracked in `12-REVIEW-FIX.md` and the phase security audit in `12-SECURITY.md`.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A BYOK user (writer/judge and Browserbase keys present) calls `research_account_full(domain, run_eval)` and receives the complete grounded `ScoredAccount` JSON including `AccountStatus` (Roadmap SC1 / MCP-05) | ✓ VERIFIED | `src/mcp_server/server.py::research_account_full` (lines 152-202) delegates to `process_account`; `tests/functional/test_mcp_server.py::test_full_tool_happy_path_returns_complete_scored_account` calls the tool over a real in-memory JSON-RPC session and asserts all 8 `ScoredAccount` field names (`account`, `status`, `enrichment`, `score`, `contacts`, `hooks`, `eval_score`, `error`) are present in `structuredContent`, `status` is a valid `AccountStatus` value, and every hook's `cited_indices` is a subset of `enrichment.justifications` indices (D-01). Independently re-run: **PASS**. |
| 2 | `MCP_DEMO_MODE=1` forces thin tier and hides `research_account_full` even when full keys are present, verified by a test (Roadmap SC2 / MCP-05) | ✓ VERIFIED | `tests/functional/test_mcp_server.py::test_demo_hides_full_tool_even_with_full_keys_present` constructs `Settings` with all four full-tier keys plus `mcp_demo_mode=True`, asserts `settings.mcp_tier() == "thin"`, builds the server with that tier, and asserts `list_tools()` returns exactly `["get_account_evidence"]` — the tool is absent from the listing, not merely refusing calls. Independently re-run: **PASS**. Tier gating in `build_server` (server.py:205-228) is driven exclusively by the explicit `tier` parameter, never re-derived from key presence or the `settings=None/not-None` HTTP-vs-stdio check (`__main__.py:30-38`). |
| 3 | An MCP client reads `configs/icp.yaml` via the `icp://rubric` resource and `evals/REPORT.md` via the `icp://eval-report` resource (Roadmap SC3 / MCP-02, MCP-03) | ✓ VERIFIED | `read_icp_rubric`/`read_eval_report` (server.py:110-133) read `DEFAULT_CONFIG_PATH`/`REPORT_PATH` verbatim on every call, registered unconditionally with `application/yaml`/`text/markdown` MIME types (server.py:270-271). `tests/functional/test_mcp_server.py::test_rubric_resource_serves_verbatim_yaml`, `::test_eval_report_resource_serves_verbatim_markdown`, `::test_list_resources_includes_rubric_and_eval_report` byte-compare the wire content against the committed files. D-08 sanitized-failure behavior additionally verified by `tests/unit/test_mcp_resources.py` (4 tests: verbatim content x2, leak-proof sanitization x2, message distinguishability). Independently re-run: **PASS** (11/11 in test_mcp_resources.py, relevant subset in test_mcp_server.py). |
| 4 | Invoking the `research_account` prompt guides rubric-based scoring where every claim cites an `[N]` justification index and unciteable claims are dropped (Roadmap SC4 / MCP-04) | ✓ VERIFIED | `research_account(domain)` (server.py:136-149) returns prompt text pointing at `icp://rubric` and `get_account_evidence`, with hard rules: cite `[N]`, drop uncited claims, never fabricate on empty retrieval. Registered unconditionally on every tier (server.py:272). `tests/functional/test_mcp_server.py::test_research_account_prompt_contains_required_elements` asserts the rendered text contains `icp://rubric`, `get_account_evidence`, the interpolated domain, `[N]`, `drop`, and `fabricate`; `::test_research_account_prompt_never_mentions_full_tier_tool` asserts `research_account_full` never appears (D-11, tier-neutral); `::test_list_prompts_includes_research_account_with_required_domain_arg` confirms the prompt is discoverable with a required `domain` argument. Independently re-run: **PASS**. (This truth is inherently instruction-based — enforcement of citation discipline happens in the calling client's own LLM, not server-side code; the verifiable claim is that the prompt text carries the instruction, which it does.) |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline.py::Deps.exa/browserbase/limiter` | New fields mirroring `ThinDeps` shape | ✓ VERIFIED | Fields present (lines 52-59), populated by `build_deps` (line 68-76: `exa=exa, browserbase=browserbase`), `limiter` bare `None` default. `grep -c '^(from\|import) src\.mcp_server' src/pipeline.py` → 0 (one-directional dependency arrow intact). |
| `src/pipeline.py::process_account` | `run_eval`/`on_stage` keyword-only params | ✓ VERIFIED | Signature at line 141-147 matches exactly; D-02 precedence chain (`elif not run_eval:`) sits between `hook_suppressed` and `eval_score is None` checks (lines 249-262), verified in code and by 6 passing tests in `tests/integration/test_pipeline_run_eval.py`. |
| `tests/integration/test_pipeline_run_eval.py` | New test file, D-02/D-05 coverage | ✓ VERIFIED | 6 tests, all pass independently (re-run confirmed). |
| `src/mcp_server/server.py::read_icp_rubric`, `read_eval_report`, `research_account` | New functions + registration | ✓ VERIFIED | All three functions exist, registered unconditionally in `build_server` (lines 270-272). |
| `tests/unit/test_mcp_resources.py` | D-08 sanitization tests | ✓ VERIFIED | 5 tests, all pass independently. |
| `src/mcp_server/wiring.py::EvidenceDeps`, `make_full_lifespan` | Protocol + lifespan factory | ✓ VERIFIED | `EvidenceDeps(Protocol)` with `@property` members (lines 52-73); `make_full_lifespan` delegates to `open_deps` (lines 124-145, `async with open_deps(settings) as deps: yield deps`). |
| `src/mcp_server/server.py::research_account_full`, `_sanitized_validation_message`, `build_server(tier=)` | Full-tier tool + tier gating | ✓ VERIFIED | All present; `research_account_full` at lines 152-202; tier param at line 207; gated registration at lines 273-284. |
| `src/mcp_server/__main__.py` | Tier threaded through lifespan selection | ✓ VERIFIED | `tier = resolve_and_log_tier(settings)` (line 30), lifespan selected by tier (line 34), `tier=tier` passed to `build_server` (line 37). |
| `tests/functional/test_mcp_server.py` | Full-tool behavioral tests (12-04) | ✓ VERIFIED | `_full_lifespan_factory`, `HappyWriterLLM`/`HappyJudgeLLM`, 5 `test_full_tool_*` tests, all independently re-run and pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `process_account` D-02 branch | `AccountStatus` precedence | `elif not run_eval:` positioned between `all(h.paragraph == ""...)` and `elif eval_score is None:` | WIRED | Confirmed via direct read of pipeline.py lines 249-262: exact ordering matches plan spec. |
| `build_deps` | `Deps.exa`/`Deps.browserbase` | single construction site | WIRED | `grep -rn "Deps(" src tests evals` shows construction only at build_deps's return (line 68); no second construction site found. |
| `research_account_full` | `process_account` | `deps = ctx.request_context.lifespan_context; return await process_account(account, deps, run_eval=run_eval, on_stage=on_stage)` | WIRED | server.py lines 178-193 — no stage re-composition, one try/except catch-all wrapper only. |
| `make_full_lifespan` | `open_deps` | `async with open_deps(settings) as deps: yield deps` | WIRED | wiring.py lines 141-143 — single shared httpx pool confirmed by direct read, no independent client construction. |
| `build_server(tier=)` | tier-gated tool registration | `if tier == "full": server.tool(...)((research_account_full))` | WIRED | server.py lines 273-284; `list_tools()` functional tests (`test_demo_hides_full_tool_even_with_full_keys_present`, `test_full_tool_registered_and_described_over_stdio`, `test_build_server_default_tier_registers_thin_tool_only`) prove hidden-not-refusing behavior for all three tier states. |
| `__main__.py` tier resolution | `build_server(tier=)` | `tier = resolve_and_log_tier(settings)` → `build_server(..., tier=tier)` | WIRED | __main__.py lines 30-38; tier always derives from `settings.mcp_tier()`, never re-derived from key presence. |

### Behavioral Spot-Checks / Independent Test Re-Runs

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 12-specific functional tests (resources, prompt, full tool registration/behavior) | `uv run pytest tests/functional/test_mcp_server.py -k "full_tool or rubric_resource or eval_report_resource or list_resources or research_account_prompt or list_prompts or demo_hides_full_tool or full_tool_registered or default_tier_registers or make_full_lifespan" -q` | 15 passed | ✓ PASS |
| Pipeline run_eval/on_stage + resource sanitization units | `uv run pytest tests/integration/test_pipeline_run_eval.py tests/unit/test_mcp_resources.py -q` | 17 passed | ✓ PASS |
| Full offline suite | `make test` | 485 passed, 3 deselected | ✓ PASS |
| Strict mypy | `make typecheck` | Success: no issues found in 33 source files | ✓ PASS |
| Lint | `make lint` | ruff + black clean | ✓ PASS |
| Pre-existing pipeline tests untouched | `git log --oneline -5 -- tests/integration/test_pipeline_failures.py tests/integration/test_pipeline.py` | No commits since before Phase 12 | ✓ PASS |
| No new mypy overrides | `grep -A5 "tool.mypy.overrides" pyproject.toml` | Only pre-existing Google API override | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MCP-02 | 12-02 | MCP client reads ICP rubric via `icp://rubric` | ✓ SATISFIED | `read_icp_rubric` + functional/unit tests, verbatim byte match confirmed |
| MCP-03 | 12-02 | MCP client reads eval report via `icp://eval-report` | ✓ SATISFIED | `read_eval_report` + functional/unit tests, verbatim byte match confirmed |
| MCP-04 | 12-02 | `research_account` prompt enforces `[N]` citation discipline | ✓ SATISFIED | Prompt text verified to contain all required elements, tier-neutral (D-11) confirmed |
| MCP-05 | 12-01, 12-03, 12-04 | BYOK user calls `research_account_full(domain, run_eval)`, receives complete `ScoredAccount` JSON incl. `AccountStatus` | ✓ SATISFIED | Full wire-contract functional tests (happy path, run_eval=False, empty retrieval, invalid domain, progress) all independently re-run and pass |

**Orphaned requirements check:** `grep -n "Phase 12" .planning/REQUIREMENTS.md` returns exactly MCP-02, MCP-03, MCP-04, MCP-05 — all four are claimed in plan frontmatter (12-01: MCP-05; 12-02: MCP-02/03/04; 12-03: MCP-05; 12-04: MCP-05). No orphans.

### Anti-Patterns Found

None. `grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` across all phase-modified files (`src/pipeline.py`, `src/mcp_server/server.py`, `src/mcp_server/wiring.py`, `src/mcp_server/__main__.py`, and the three new/extended test files) returned zero matches. No stub-return patterns, no hardcoded empty data flowing to output, no console.log-only implementations. All functions read as complete, working implementations backed by passing tests.

### Human Verification Required

None. All four must-have truths are verifiable via automated tests, and all were independently re-run (not merely trusted from SUMMARY.md) and confirmed passing against the actual codebase.

### Gaps Summary

No gaps found. All four roadmap success criteria are backed by real, passing, independently-re-run tests exercising actual code paths (in-memory MCP JSON-RPC sessions, not mocked at the tool-dispatch layer). The full offline gate (485 tests, strict mypy with zero new overrides, ruff + black) is green. Source code was read directly (not just summaries) for `src/pipeline.py`, `src/mcp_server/server.py`, `src/mcp_server/wiring.py`, and `src/mcp_server/__main__.py`, confirming the SUMMARY.md claims match the actual implementation line-for-line on every checked point (D-02 precedence ordering, tier gating independence from `settings`, `EvidenceDeps` protocol shape, `make_full_lifespan`'s single-delegation body, resource sanitization, prompt content).

---

_Verified: 2026-07-17T05:07:15Z_
_Verifier: Claude (gsd-verifier)_
