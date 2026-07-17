---
phase: 12-full-tier-tool-resources-prompt
fixed_at: 2026-07-17T15:06:33Z
review_path: .planning/phases/12-full-tier-tool-resources-prompt/12-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-07-17T15:06:33Z
**Source review:** .planning/phases/12-full-tier-tool-resources-prompt/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (Warnings only; `fix_scope=critical_warning`, 0 Critical findings existed)
- Fixed: 3
- Skipped: 0

All three resolutions below were directed explicitly by the operator (see the fix-run's `<operator_direction>` block) rather than applied verbatim from the reviewer's suggested patches; each implementation follows the operator's specified approach.

## Fixed Issues

### WR-01: tier="full" can be paired with a thin lifespan; every full-tool call then fails opaquely

**Files modified:** `src/mcp_server/server.py`, `tests/functional/test_mcp_server.py`
**Commit:** `1206729`
**Applied fix:** Added an explicit `hasattr(deps, "enricher")` guard as the first check after resolving the lifespan context inside `research_account_full`, per the operator's chosen resolution (fail loudly at first-call time with an explicit misconfiguration message, ahead of the existing generic catch-all). On a thin lifespan it now logs at ERROR and raises `RuntimeError("server misconfiguration: ...")`, which the MCP SDK surfaces to the client verbatim (`isError=True`) instead of the sanitized "internal error, try again." Added `test_full_tool_thin_lifespan_misconfiguration_fails_loudly`, which reconstructs the exact mismatched wiring the review identified (`build_server(lifespan=_lifespan_factory(exa), tier="full")`), calls the tool, and asserts the distinct misconfiguration message and ERROR log line.

### WR-02: A failed progress notification aborts a completed pipeline run and discards paid LLM output

**Files modified:** `src/mcp_server/server.py`, `tests/functional/test_mcp_server.py`
**Commit:** `11f3b7f`
**Applied fix:** Per the operator's explicit direction, `process_account`'s generic `on_stage` callback contract in `src/pipeline.py` was left unchanged (no exception swallowing added there). Instead, the MCP wrapper's own `on_stage` closure inside `research_account_full` now wraps `await ctx.report_progress(...)` in a `try/except Exception`, logging at WARNING with `%`-placeholders on failure and swallowing the exception so it can never propagate into `process_account` and discard an already-completed `ScoredAccount`. Added `test_full_tool_progress_send_failure_does_not_discard_result`, which monkeypatches `ServerSession.send_progress_notification` (what `ctx.report_progress` calls) to raise `httpx.HTTPError`, then asserts the tool call still returns `isError=False` with a complete result (including non-empty `hooks`) and that the failure is logged at WARNING only.

### WR-03: Full tier over HTTP has no rate limiting and no auth; the only guard is a fail-open env var

**Files modified:** `src/config.py`, `src/mcp_server/__main__.py`, `tests/unit/test_mcp_main_guard.py`, `.env.example`
**Commit:** `8d76728`
**Applied fix:** Added `mcp_allow_full_http: bool = False` to `Settings` (`src/config.py`), wired through pydantic-settings identically to the other MCP env vars (`MCP_ALLOW_FULL_HTTP`), and documented it in `.env.example`. Extracted a small testable `guard_full_tier_http_exposure(settings, transport, tier)` function in `src/mcp_server/__main__.py`, called from `main()` right after tier resolution: it raises `SystemExit` with a clear operator-facing message whenever `transport == "http" and tier == "full"` and `MCP_ALLOW_FULL_HTTP` is not set. stdio full tier and demo/thin HTTP are untouched (the guard only fires on that one combination). Added `tests/unit/test_mcp_main_guard.py` with 5 unit tests covering: refusal without opt-in, the opt-in path succeeding, stdio full tier unaffected, thin tier over HTTP unaffected, and demo-mode thin tier over HTTP unaffected.

## Offline Gate (post-fix, run at operator's request)

All three commands were run against the fully fixed worktree (all three commits applied):

- `make test` -- **PASS**: 492 passed, 3 deselected (smoke tests, opt-in only), 6 warnings (pre-existing SDK deprecation notices, unrelated to this fix).
- `make typecheck` -- **PASS**: `mypy --strict` clean across 33 source files in `src/` and `evals/`.
- `make lint` -- **PASS**: `ruff check` all checks passed; `black --check` 82 files unchanged.

No regressions observed. No skipped or deferred findings.

---

_Fixed: 2026-07-17T15:06:33Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
