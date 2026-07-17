---
phase: 12-full-tier-tool-resources-prompt
reviewed: 2026-07-17T05:03:33Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/mcp_server/__main__.py
  - src/mcp_server/server.py
  - src/mcp_server/wiring.py
  - src/pipeline.py
  - tests/functional/test_mcp_server.py
  - tests/integration/test_pipeline_run_eval.py
  - tests/unit/test_mcp_resources.py
findings:
  critical: 0
  warning: 3
  info: 7
  total: 10
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-17T05:03:33Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 12 diff (base `6448abc`): the `research_account_full` full-tier MCP tool, the `icp://rubric` and `icp://eval-report` resources, the `research_account` prompt, `process_account`'s new `run_eval`/`on_stage` seams, `Deps` extension (`exa`/`browserbase`/`limiter`), `make_full_lifespan`, and tier threading through `__main__`. Cross-references were traced into `src/config.py` (`mcp_tier`), `src/mcp_server/limits.py`, `src/models.py`, and the installed MCP SDK's `Context.report_progress`.

Verification performed: all 71 tests in the three reviewed test files pass; `mypy --strict` is clean on `src/mcp_server/` and `src/pipeline.py`; pattern scans found no debug artifacts, secrets, or dangerous calls. Every `Deps(...)` construction site was checked after the dataclass gained two required fields (only `build_deps` constructs it; `evals/run_live.py` goes through `build_deps`). The status-precedence ladder in `process_account` was traced for all `run_eval` x `hooks` x `eval_score` combinations and matches the documented D-02/D-03 contract, including the docstring's "judge_failed is never returned when run_eval=False" claim.

No Critical issues found. Three Warnings concern robustness and fail-open configuration seams: an unguarded tier/lifespan pairing that fails opaquely at call time, a progress-notification failure path that discards a completed paid pipeline run, and the absence of any rate limiting or auth on the full tier over HTTP. Info items are quality and consistency defects.

## Warnings

### WR-01: tier="full" can be paired with a thin lifespan; every full-tool call then fails opaquely

**File:** `src/mcp_server/server.py:205-284`
**Issue:** `build_server` types its `lifespan` parameter as `AbstractAsyncContextManager[EvidenceDeps]`, but `research_account_full` reads the lifespan context as a full `Deps` (`ctx: Context[ServerSession, Deps, Request]`, and `process_account` immediately calls `deps.enricher.enrich(...)`). Nothing, statically or at runtime, prevents registering the full tool over a `ThinDeps` lifespan. `tests/functional/test_mcp_server.py:664` builds exactly this mismatched server (`build_server(lifespan=_lifespan_factory(exa), tier="full")`) and it constructs without complaint; it only survives because that test never calls the tool. If this misconfiguration ever occurs in real wiring, every `research_account_full` call raises `AttributeError` on `deps.enricher`, which is not in `process_account`'s narrow except tuples, propagates to the catch-all at `server.py:194`, and surfaces to the client as the sanitized "internal error, try again" -- a wiring bug disguised as a transient fault. The FastMCP `Context` generic provides zero enforcement; the only correct pairing lives in `__main__.py:34` by convention.
**Fix:** Fail fast at registration time in `build_server`:
```python
if tier == "full":
    # research_account_full requires the full Deps bundle; refuse a thin lifespan
    # at startup instead of AttributeError-ing on every call.
    server.tool(...)(research_account_full)
```
Since the lifespan is opaque until entered, the cheapest hard guard is a first-line runtime check in `research_account_full` (`if not hasattr(deps, "enricher"): raise RuntimeError("full tool registered with thin lifespan")` logged at ERROR, not the generic catch-all), plus a functional test that calls (not just lists) `research_account_full` against a mismatched lifespan and asserts the distinct failure. Alternatively make `build_server`'s signature generic over the deps type so mypy rejects the mismatch.

### WR-02: A failed progress notification aborts a completed pipeline run and discards paid LLM output

**File:** `src/mcp_server/server.py:188-190` (and `src/pipeline.py:165-166,183-184,198-199,215-216,234-235`)
**Issue:** `on_stage` awaits `ctx.report_progress`, which in the installed SDK calls `session.send_progress_notification` whenever the client supplied a progress token. If that send raises -- client disconnects mid-run over streamable HTTP (closed/broken memory stream), or stdout closes over stdio -- the exception propagates out of `on_stage` into `process_account`, where every `on_stage` call site sits deliberately outside the per-stage `try/except` blocks. The in-flight (or, for the final `"eval"`/`"outreach"` boundary, fully computed) `ScoredAccount` is discarded, all writer/judge tokens already spent are lost, and the caller gets "internal error, try again" from the catch-all at `server.py:194`. This contradicts the tool's own docstring contract that progress is advisory ("clients that ignore it lose nothing"): a client that requests progress and then misbehaves loses everything.
**Fix:** Make progress strictly best-effort in the one place that owns it:
```python
async def on_stage(stage: str) -> None:
    seen["n"] += 1
    try:
        await ctx.report_progress(seen["n"], total, message=f"{stage} complete")
    except Exception as exc:
        log.warning("progress notification failed at %s for %s: %s", stage, domain, exc)
```
(For a dead session the final result send will still fail, but stdio-with-closed-progress and partial-stream cases keep the run's result intact, and the pipeline's stage isolation guarantees stay uncontaminated by transport concerns.)

### WR-03: Full tier over HTTP has no rate limiting and no auth; the only guard is a fail-open env var

**File:** `src/mcp_server/__main__.py:34-38`, `src/mcp_server/server.py:152-202`, `src/pipeline.py:54-59`
**Issue:** `main()` happily combines `tier == "full"` with `--transport http`. In that configuration `research_account_full` (30-60s of paid writer+judge tokens plus Browserbase per call) performs no quota check at all -- `Deps.limiter` is hard-typed `None` -- and `get_account_evidence`'s limiter branch is likewise skipped. There is no authentication on the endpoint. The only thing standing between "local full server" and "unmetered public LLM spend" is the operator remembering to set `MCP_DEMO_MODE=true`: forgetting it fails open into the full tier (config.py:213-218 only demotes to thin when demo mode is explicitly on). Mitigations today: the default bind is loopback (`mcp_http_host=127.0.0.1`) and no Dockerfile/fly.toml exists yet, so exposure requires deliberate host override -- which the config comment says the Phase 13 Dockerfile will do (`config.py:136-138`, "the Dockerfile overrides host to 0.0.0.0"). Note also that the Host allowlist is not a barrier against direct connections: with `mcp_http_host=0.0.0.0`, `0.0.0.0:{port}` is itself allowlisted (`server.py:255-259`), and a direct attacker controls the Host header anyway.
**Fix:** Make public full-tier exposure an explicit opt-in rather than an omission. In `main()`:
```python
if args.transport == "http" and tier == "full" and not settings.mcp_demo_mode:
    raise SystemExit(
        "refusing to serve the full tier over HTTP without MCP_DEMO_MODE=true "
        "or MCP_ALLOW_FULL_HTTP=true (unmetered paid tools, no auth)"
    )
```
with a new opt-in setting for the deliberate case. At minimum this must land before Phase 13 ships a 0.0.0.0-binding container.

## Info

### IN-01: Tier log can claim "exa+browserbase" while demo wiring forces NullBrowserbase

**File:** `src/mcp_server/server.py:38-43`
**Issue:** `resolve_and_log_tier` derives `sub_mode` from key presence, but in demo mode `make_thin_lifespan` overrides any key-built client with `NullBrowserbase()` (`wiring.py:111`). With demo mode on and Browserbase keys present, the startup log says `thin (exa+browserbase)` while the running server will never touch Browserbase -- a misleading breadcrumb during demo ops debugging.
**Fix:** Fold `settings.mcp_demo_mode` into the sub_mode derivation: demo mode always logs `exa-only`.

### IN-02: research_account prompt reflects unvalidated, unbounded domain input

**File:** `src/mcp_server/server.py:136-149`
**Issue:** Both tools validate `domain` through `Account` and keep error text bounded/non-reflective; the prompt interpolates the raw string verbatim (twice, once via `!r`). A megabyte-long or newline-laden `domain` is reflected wholesale in the prompt result. No trust boundary is crossed (the requester poisons only its own prompt), but it is inconsistent with the validation discipline the sibling handlers establish, and a normalized `account.domain` would also make the embedded `get_account_evidence(...)` call in the prompt actually succeed for inputs like `https://notion.so/`.
**Fix:** Validate via `Account(domain=domain)` (with the same `_sanitized_validation_message` handling) and interpolate `account.domain`.

### IN-03: read_icp_rubric and read_eval_report are structural duplicates

**File:** `src/mcp_server/server.py:110-133`
**Issue:** Identical try/read/log-warn/fallback-string shape differing only in path and label; a third resource would make it a copy-paste pattern.
**Fix:** Factor `_read_resource_file(path: Path, label: str) -> str` and keep the two named wrappers one line each.

### IN-04: Dead stage-name tuple and dict-as-counter in research_account_full

**File:** `src/mcp_server/server.py:180-190`
**Issue:** The `stages` tuple is computed but only its length is used (the stage names actually reported come from `process_account`); `seen = {"n": 0}` is a dict standing in for a mutable counter.
**Fix:** `total = 5 if run_eval else 4` and a `nonlocal` int (or `itertools.count`) inside `on_stage`.

### IN-05: research_account_full docstring and wire description are divergent near-duplicates

**File:** `src/mcp_server/server.py:152-172` and `276-283`
**Issue:** The explicit `description=` in registration overrides the docstring on the wire, but its first paragraph is a hand-copied condensation of the docstring; the `status` value contract exists only in the docstring copy. `get_account_evidence` takes the opposite approach (docstring is the wire description). Two sources of truth for one tool contract is a drift hazard.
**Fix:** Either let the docstring serve as the wire description (matching `get_account_evidence`), or reduce the docstring to implementation notes and treat `description=` as the single contract.

### IN-06: Replay mode via MCP still requires dummy real-key env vars, contradicting the "replay for free" claim

**File:** `src/mcp_server/wiring.py:124-137`, `src/config.py:201-219`
**Issue:** `make_full_lifespan`'s docstring says delegating to `open_deps` "inherits open_deps's replay/record branching for free", but reaching the full tier requires `mcp_tier() == "full"`, which checks provider/Browserbase key presence with no `demo_bundle` early-return (unlike `require_for_pipeline`, config.py:180-181). Running the full-tier MCP server against a replay bundle therefore requires setting placeholder keys that will never be used.
**Fix:** Either mirror `require_for_pipeline`'s replay early-return in `mcp_tier()` (return "full" when `demo_bundle` is set and not demo mode), or document the dummy-key requirement where the replay path is described.

### IN-07: Test-local RecordingExa shadows src.clients.replay.RecordingExa; FakeExa imported from a sibling test module

**File:** `tests/functional/test_mcp_server.py:25,67`
**Issue:** The file defines a local class named `RecordingExa` while `src/clients/replay.py` exports a different `RecordingExa` used by `pipeline.py` -- confusing when grepping. It also imports `FakeExa` from `tests/functional/test_enrich`, making one test module load-bearing for another; a refactor of `test_enrich.py` breaks this suite.
**Fix:** Rename the local class (e.g., `NumResultsSpyExa`) and move shared fakes like `FakeExa` into a `tests/` conftest or fixtures module.

---

_Reviewed: 2026-07-17T05:03:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
