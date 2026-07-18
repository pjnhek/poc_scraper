# Phase 14: Deterministic Scoring & Guided Flow - Research

**Researched:** 2026-07-17
**Domain:** MCP tool registration, pydantic-schema-driven arg validation (`mcp` Python SDK), pure-arithmetic reuse of `src/score.py`/`src/icp_config.py`
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**score_account input contract**
- D-01: Axis scores are **integers only**, 1-5. Fractional values (e.g. 3.5) are rejected with the sanitized error. Rationale: the rubric anchors in `configs/icp.yaml` define meaning only at integer points, and the pipeline's own writer path clips to integers. The weighted total remains fractional via `compute_total`.
- D-02: Omitted per-axis reason strings become **empty strings** when constructing `RubricBreakdown` (which requires all four `*_reason` fields). No server-invented placeholder text ever enters the agent's judgment fields.
- D-03: **No server-side check of `[N]` citation markers** in reason strings. The server is stateless and never sees the evidence pack, so it cannot verify indices; the prompt owns citation discipline. This is the hybrid-grounding frame applied literally: judgment is grounding-by-instruction, math is grounding-by-construction.
- D-04: Axis-range validation lives **in the tool body**, not in schema-level `Field(ge/le)` annotations: the signature takes plain ints, the tool range-checks 1-5 and raises the project's standard sanitized `ValueError` (same pattern as `get_account_evidence`), so error wording is owned end to end (SCORE-03).

**score_account return shape**
- D-05: Return a **new small frozen pydantic model** defined in `src/mcp_server/` (ScoreResult-style) holding the rubric breakdown, weighted total, and verdict label. `src/models.py` stays untouched; `ICPScore` is NOT reused (its required `supporting_indices`/`justification` fields do not fit a stateless scoring call).
- D-06: The response **echoes the rubric context used**: per-axis weights and the verdict thresholds that produced the result. Every score is reproducible by inspection, and an `icp.yaml` edit between calls cannot silently change the meaning of an earlier result.
- D-07: `score_account` accepts an **optional `domain` string, echoed back verbatim** in the result for attribution. It is an opaque label: no `Account` validation, no retrieval, no limiter. The guided prompt tells the agent to pass it.

**Prompt orchestration**
- D-08: `research_account` is **rewritten as an explicit numbered step sequence**: 1) call `get_account_evidence` (optionally with `news_days`), 2) read `icp://rubric`, 3) score each axis 1-5 with `[N]` citations from the evidence, 4) call `score_account` with those scores plus domain and reasons, 5) present the returned verdict, then 6) personas and hooks (D-09).
- D-09: **Personas + cited outreach hooks stay** in the prompt as the closing steps. Trimming to scoring-only would regress the hosted demo's showcase value.
- D-10: **Explicit skip rule for empty evidence:** when `retrieval_status` is `empty`, the agent must NOT call `score_account`; it reports the account as unscoreable, mirroring the pipeline's `unscoreable` semantics. Closes the fabricated-scores loophole that grounding-by-instruction can reach.
- D-11: The prompt carries a **one-line aside** (not a numbered step) noting `news_days` can widen or narrow the news lookback when recency matters.

**news_days clamping**
- D-12: Clamp range is **7 to 365**, default stays **90** when omitted. Floor keeps a neural news query meaningful on the demo; ceiling keeps "recent context" honest.
- D-13: The clamp is **silent**: out-of-range values are clamped and the call proceeds; the tool's parameter description documents the range. No new field on the frozen `EvidencePack`. Matches the existing `DemoClampedExa` min()-clamp posture.

### Claude's Discretion
- Handling of malformed (non-integer-typed) `news_days` and `score_account` argument values that the MCP SDK's own schema validation rejects before tool code runs: acceptable to leave to SDK-level rejection; verify during planning what wording the SDK emits and confirm it leaks nothing (no paths, env names, stack traces). **Resolved by this research below — see Common Pitfalls #1.**
- Exact name/field-naming of the new ScoreResult-style response model, and whether verdict thresholds are echoed as a mapping or a small nested structure. **A concrete recommendation is given below (Code Examples); still the planner's call.**
- Precise prompt wording, subject to D-08..D-11.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Per-call rubric-weight overrides and arbitrary-axis rubrics were already parked in REQUIREMENTS.md Future Requirements before this discussion.)

### Locked at milestone level (do not re-litigate)
No new axes, no changes to `RubricBreakdown` or any `src/models.py` model, no server-side LLM scoring on the thin tier, `DemoLimiter` never consulted for `score_account`, per-call rubric-weight overrides deferred to v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCORE-01 | `score_account` tool: 4 axis scores (+ optional reasons) -> rubric breakdown, weighted total, verdict, via `compute_total`/`verdict_for` over unchanged `RubricBreakdown` | `compute_total`/`verdict_for` read verbatim below (Code Examples); confirmed pure, no I/O, already unit-tested math in `tests/unit/test_score_math.py` |
| SCORE-02 | Registered on both tiers, pure arithmetic, no `DemoLimiter` consumption | `build_server`'s tier-gating structure read verbatim; registration point identified (before `if tier == "full":`); `score_account` needs no `ctx: Context[...]` parameter at all, which structurally rules out limiter/exa/browserbase access |
| SCORE-03 | `ToolAnnotations(readOnlyHint=True, destructiveHint=False)`, sanitized one-line error on invalid input | Exact annotation call-site identified in `build_server`; sanitized-error wrapper pattern (`ValueError` -> SDK's `"Error executing tool <name>: <msg>"`) verified live against the installed SDK (see Common Pitfalls #1) |
| PROMPT-01 | `research_account` prompt orchestrates the full flow | Current `research_account` function body read verbatim; rewrite target identified; existing prompt-content functional tests (`test_research_account_prompt_contains_required_elements`) show the required-substring assertion pattern to extend |
| EVID-01 | `news_days` param on `get_account_evidence`, clamped server-side, threads to `ExaClient.search_news(days=...)` | Full threading chain traced: `get_account_evidence` -> `build_evidence_pack` -> `collect_context` -> `exa.search_news(domain)`; confirmed `ExaClient.search_news` and `ExaLike` protocol already accept `days: int = 90`, and `FakeExa`/`RecordingExa` test doubles already implement the parameter -- only the *threading*, not the protocol, is missing |
| DOCS-03 | Oracle landing page mentions scoring | `deploy/oracle/setup.sh` heredoc (the landing-page source of truth) read verbatim; exact lines identified that currently say "Evidence retrieval only" and will become stale once `score_account` ships unrationed on the same tier |
| DOCS-04 | README documents `score_account` with hybrid framing | Existing "Grounding by instruction vs grounding by construction" README section read verbatim; identified as needing a third nuance (math-grounding-by-construction inside the thin tier), not just an appended blurb |
| TEST-03 | Unit + in-memory MCP functional tests for `score_account`; full offline gate green, no new mypy overrides | Existing test file conventions read verbatim (`tests/unit/test_score_math.py`, `tests/functional/test_mcp_server.py`); `make typecheck` scope confirmed as `mypy src evals` (tests/ excluded from strict gate) |
| TEST-04 | `news_days` clamp + default tested at MCP boundary | `RecordingExa`/`DemoClampedExa` test patterns identified as the extension point for asserting the clamped `days` value reaches `exa.search_news` |
</phase_requirements>

## Summary

This phase adds exactly one new pure-arithmetic MCP tool (`score_account`), threads one new optional parameter through an existing tool (`get_account_evidence`'s `news_days`), rewrites one prompt (`research_account`), and updates two documentation surfaces. There is no new external dependency, no new library, and no `src/models.py` change. Every piece of math the new tool needs (`compute_total`, `ICPConfig.verdict_for`) already exists, is already pure, and is already unit-tested. The work is entirely a *composition* exercise inside `src/mcp_server/`, following two patterns the codebase already establishes: (1) `server.py` stays a thin registration/wiring layer while the actual tool logic lives in a sibling module (`evidence.py` is the existing precedent -- `get_account_evidence` is a thin wrapper around `build_evidence_pack`); (2) sanitized one-line errors are raised as plain `ValueError` inside the tool body and the SDK's own error path (`Tool.run()` -> `ToolError(f"Error executing tool {name}: {e}")`) prepends a fixed, non-leaking prefix.

The one genuinely new technical fact this research surfaces (not knowable from reading the codebase alone) is how the installed `mcp` SDK (confirmed via live probe against `.venv/lib/python3.12/site-packages/mcp`) handles **type-level** argument validation. Because D-04 locks `score_account`'s axis parameters to plain `int` (no `Annotated[int, Field(ge=1, le=5)]`), a caller sending `3.5` or `"abc"` never reaches the tool body at all -- pydantic's own arg-model validation rejects it first, with a *different*, unsanitized wire format than the project's own `ValueError` convention. This is fully compatible with D-01 (fractional values are rejected) and does not leak secrets/paths/stack traces, but it is multi-line and echoes a truncated repr of the raw input. This must be an explicit, tested code path in the plan, not an assumption. Full detail in Common Pitfalls #1.

**Primary recommendation:** Add `src/mcp_server/scoring.py` (mirroring `evidence.py`'s role) holding a new frozen `ScoreResult` model and a `build_score_result(...)` pure function that does the 1-5 range check, builds `RubricBreakdown`, calls `compute_total`/`verdict_for`, and echoes weights + verdict thresholds as plain `dict[str, float]`/`dict[str, str]` maps (JSON-friendly, no new nested model types). `server.py`'s `score_account` becomes a thin sync wrapper (no `ctx` parameter, no `async`) that calls `build_score_result` and converts its `ValueError` for out-of-range input into the sanitized wire error, registered unconditionally (both tiers) via the same `server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(...)` call-site pattern already used for `get_account_evidence`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `score_account` arithmetic (weighted total, verdict lookup) | API / Backend (MCP tool layer) | — | Pure function over caller-supplied ints and the server's own `configs/icp.yaml`; no client-side computation possible since the rubric config is server-owned |
| Axis judgment (1-5 scoring, citation discipline) | Client (the connecting agent's own model) | — | Explicitly out of server scope per milestone frame ("Option A" server-side LLM scoring is Out of Scope); the server only ever sees the agent's already-formed integers |
| `news_days` clamping | API / Backend (MCP tool layer, `get_account_evidence`) | — | Caller-supplied value is untrusted input; clamping must happen server-side before it reaches `ExaClient.search_news` (a paid/rationed external call) |
| Evidence retrieval (`get_account_evidence`) | API / Backend (MCP tool layer) -> External (Exa) | — | Unchanged from Phase 10-13; `news_days` is an additional pass-through parameter on an existing seam, not a new tier |
| Rubric definition source of truth | Config / Storage (`configs/icp.yaml`, read via `ICPConfig`) | — | Both the writer path (`src/score.py`) and the new `score_account` tool must read the same cached `get_config()` singleton so an edited rubric is consistently reflected everywhere without divergence |
| Prompt orchestration (`research_account`) | API / Backend (MCP prompt layer) | Client (agent execution of the steps) | The prompt text lives server-side, but its numbered steps are *instructions* the calling agent executes; the server does not enforce step order (grounding-by-instruction, consistent with the thin tier's existing framing) |
| Documentation (README, Oracle landing page) | Docs / Static | — | No runtime tier; purely descriptive surfaces that must stay truthful about what the two tiers now do |

## Standard Stack

No new external dependency is introduced by this phase. `mcp>=1.28,<2.0` (already locked, per CLAUDE.md) is the only SDK involved, and it is already installed and in use for every existing tool/resource/prompt.

**Installed version verified locally:**
```bash
$ .venv/bin/python -c "import importlib.metadata as m; print(m.version('mcp'))"
```
`[VERIFIED: local .venv inspection]` — the installed `mcp` package matches the project's declared `mcp>=1.28,<2.0` constraint (`pyproject.toml`); no upgrade action needed for this phase.

No `## Package Legitimacy Audit` section is required: this phase adds zero new packages to `pyproject.toml`.

## Architecture Patterns

### System Architecture Diagram

```
                         MCP client (connecting agent)
                                    |
                 (1) get_account_evidence(domain, news_days?)
                                    v
        +-------------------------------------------------+
        |  src/mcp_server/server.py  (thin registration)   |
        |  - Account validation -> sanitized ValueError    |
        |  - DemoLimiter check_and_consume (if demo mode)  |
        +----------------------+----------------------------+
                                v
        +-------------------------------------------------+
        |  src/mcp_server/evidence.py                       |
        |  build_evidence_pack(account, exa, browserbase,   |
        |                       news_days=clamp(...))       |  <- NEW: days threaded here
        +----------------------+----------------------------+
                                v
        +-------------------------------------------------+
        |  src/enrich.py :: collect_context(..., days=...)  |  <- NEW: days param added
        +----------------------+----------------------------+
                                v
                  ExaClient.search_news(domain, days=N)  (external, already accepts days)
                                |
                                v
                    EvidencePack (justifications [N], retrieval_status)
                                |
                                v
                       returned to the agent
                                |
        (2) agent reads icp://rubric resource (unchanged)
                                |
        (3) agent scores each axis 1-5, cites [N] from justifications
                                |
                 (4) score_account(support_volume=.., ..., domain=?)
                                v
        +-------------------------------------------------+
        |  src/mcp_server/server.py :: score_account         |
        |  (NEW, thin wrapper, no ctx, no async needed)      |
        +----------------------+----------------------------+
                                v
        +-------------------------------------------------+
        |  src/mcp_server/scoring.py  (NEW)                  |
        |  - range-check each axis in [1,5] -> ValueError    |
        |  - build RubricBreakdown(reason="" if omitted)     |
        |  - compute_total(breakdown, config)  <- REUSED     |
        |  - config.verdict_for(total)         <- REUSED     |
        |  - assemble ScoreResult (echoes weights/thresholds)|
        +----------------------+----------------------------+
                                v
                     ScoreResult -> agent (verdict shown)
                                |
        (5) agent proceeds to personas + cited outreach hooks
            (prompt text only -- no new tool; D-09)
```

Every box left of "external Exa call" and right of "agent scores axes" is server-owned and deterministic (grounding-by-construction). The axis-scoring step in the middle is agent-owned and instruction-grounded. This split is the literal shape DOCS-04 must describe.

### Recommended Project Structure

No new top-level directories. One new file, following the existing `src/mcp_server/` layout:

```
src/mcp_server/
├── evidence.py       # existing: build_evidence_pack, MCP-boundary caps -- gains `days` threading
├── scoring.py         # NEW: ScoreResult model + build_score_result() pure function
├── server.py          # existing: gains score_account wrapper + news_days param on get_account_evidence + rewritten research_account
├── limits.py          # existing: unchanged (score_account never touches DemoLimiter)
├── wiring.py           # existing: unchanged (score_account needs no lifespan deps)
└── __main__.py        # existing: unchanged
```

### Pattern 1: Thin tool wrapper delegates to a sibling module

**What:** `server.py`'s tool functions stay short: validate/adapt input, delegate to a pure function in a sibling module, translate exceptions to sanitized `ValueError`.
**When to use:** Every new MCP tool in this codebase, established by `get_account_evidence` -> `build_evidence_pack` (`src/mcp_server/evidence.py`).
**Example (existing code, verbatim):**
```python
# Source: src/mcp_server/server.py:61-107 (read from this repo, not external docs)
async def get_account_evidence(
    domain: str, ctx: Context[ServerSession, EvidenceDeps, Request]
) -> EvidencePack:
    try:
        account = Account(domain=domain)
    except ValidationError as exc:
        raise ValueError(_sanitized_validation_message(exc)) from None
    ...
    try:
        return await build_evidence_pack(account, exa=deps.exa, browserbase=deps.browserbase)
    except (httpx.HTTPError, BrowserbaseError) as exc:
        ...
        raise ValueError("retrieval unavailable, try again") from None
```
`score_account` should follow the identical shape but needs neither `ctx` nor `try/except` around external I/O (there is none) -- only the range-check `try/except` around `RubricBreakdown`/manual validation.

### Pattern 2: Registration precedes tier gating, tools are grouped by which tier gets them

**What:** `build_server` registers thin-tier tools unconditionally at the top, then gates full-tier-only tools inside `if tier == "full":`.
**Example (existing code, verbatim):**
```python
# Source: src/mcp_server/server.py:305-323
server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
    get_account_evidence
)
server.resource("icp://rubric", mime_type="application/yaml")(read_icp_rubric)
server.resource("icp://eval-report", mime_type="text/markdown")(read_eval_report)
server.prompt()(research_account)
if tier == "full":
    server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
        description=(...),
    )(research_account_full)
return server
```
`score_account` registration goes in the unconditional block (alongside `get_account_evidence`), *before* the `if tier == "full":` line, per SCORE-02.

### Pattern 3: Sanitized-error wrapper, and what "sanitized" means at each layer

**What:** Every tool that can fail on bad input raises a plain `ValueError(<short message>)` from inside the tool body (after `from None` to drop the original traceback context). The SDK wraps it as `"Error executing tool <name>: <message>"` and returns it as `CallToolResult(isError=True, content=[TextContent(text=that string)])`. Existing tests assert `<message> in text`, tolerant of the SDK's own prefix.
**Example (existing code, verbatim):**
```python
# Source: src/mcp_server/server.py:47-58
def _sanitized_validation_message(exc: ValidationError) -> str:
    msg = exc.errors()[0]["msg"]
    prefix = "Value error, "
    if msg.startswith(prefix):
        msg = msg[len(prefix) :]
    return msg
```
`score_account`'s range-check error does not need this helper (there is no pydantic `ValidationError` to strip a prefix from, since D-04 keeps the check manual) -- it raises `ValueError("<axis> must be an integer 1-5")` or similar directly.

### Anti-Patterns to Avoid
- **Using `Annotated[int, Field(ge=1, le=5)]` on `score_account`'s axis parameters.** This would push range validation into the pydantic arg-model layer, contradicting D-04 (validation must live in the tool body) and producing the *pydantic* multi-line error format instead of the project's sanitized one-liner for the in-range-check case. (It cannot be avoided for the *type*-level check -- see Common Pitfalls #1 -- but must be avoided for the *range* check.)
- **Reusing `_json_utils.clip_score` for axis validation.** `clip_score` silently *coerces* out-of-range/non-numeric values to the nearest bound (a writer-degradation-tolerance helper for LLM output) -- the opposite of `score_account`'s reject-on-invalid contract (SCORE-03).
- **Adding a `days` field to the frozen `EvidencePack` model.** D-13 explicitly forbids this; `news_days` is a call-time parameter, not a piece of retrieved evidence, and `src/models.py` must stay untouched per the milestone-level lock.
- **Giving `score_account` an `async def` signature and a `ctx: Context[...]` parameter "just in case."** This would silently reopen the door to future I/O/limiter access and defeats the "structurally guarantees no I/O" property the codebase notes call out as a feature, not an accident.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Weighted rubric total | A new summation function inside the MCP tool | `src.score.compute_total(breakdown, config)` | Already correct, already unit-tested (`tests/unit/test_score_math.py`), already handles the `round(raw, 1)` convention the rest of the codebase (Sheets, eval) expects |
| Verdict-label lookup from a total | A new threshold-comparison loop | `ICPConfig.verdict_for(total)` (`src/icp_config.py:66-71`) | Already handles the "highest threshold the total meets or exceeds, falling back to the lowest verdict" ranking logic correctly; re-deriving it risks an off-by-one at the threshold boundary |
| Clamping `news_days` to a range | A hand-rolled `if/elif` clamp | `max(min(value, 365), 7)` -- one-liner, matching the existing `DemoClampedExa` `min()`-clamp idiom already in the codebase (`src/mcp_server/wiring.py:32-42`) | Consistency: the codebase already has exactly one clamping idiom; a second, differently-shaped clamp function is unnecessary surface area |
| Fractional-input rejection for axis scores | A manual `isinstance(x, int)` / `x != int(x)` check inside the tool body | The plain `int` type annotation on the tool signature (SDK arg-model validation) | D-04 locks the signature to plain `int`; pydantic's own lax-mode `int` coercion already rejects a JSON float with a nonzero fractional part (verified live, see Common Pitfalls #1) -- writing a redundant in-body check duplicates work the type system already does for free |

**Key insight:** every piece of math this phase needs is already implemented, already pure, and already covered by an existing unit test suite. The entire "Don't Hand-Roll" risk here is not about external libraries (there are none) but about *duplicating internal logic* that already exists one import away.

## Common Pitfalls

### Pitfall 1: SDK-level type validation produces a different (but still safe) error shape than the project's own sanitized-error convention
**What goes wrong:** A caller sends `score_account` a non-integer axis value (a string, or a float with a fractional part like `3.5`). Because D-04 mandates plain `int` parameter types (no `Field(ge=1, le=5)`), this value never reaches the tool body -- the MCP SDK's own pydantic arg-model (`func_metadata`, `mcp/server/fastmcp/utilities/func_metadata.py`) rejects it during `call_fn_with_arg_validation`, before `score_account`'s code runs at all.
**Why it happens:** FastMCP builds a dynamic pydantic model from the function's type-hinted parameters and validates all incoming JSON arguments against it *before* invoking the tool function. This is a different code path than the tool-body `ValueError`s the rest of this codebase relies on for sanitized wording.
**Confirmed wire format** `[VERIFIED: live probe against the installed .venv/lib/python3.12/site-packages/mcp package, 2026-07-17]`:
```
Error executing tool score_account: 1 validation error for score_accountArguments
support_volume
  Input should be a valid integer, unable to parse string as an integer [type=int_parsing, input_value='abc', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/int_parsing
```
and for a fractional value (`3.5`):
```
Error executing tool score_account: 1 validation error for score_accountArguments
support_volume
  Input should be a valid integer, got a number with a fractional part [type=int_from_float, input_value=3.5, input_type=float]
```
For a pathologically long string input, pydantic's own `input_value=` repr is already bounded/truncated by pydantic itself (confirmed: a 500-character input string produced a ~350-character total error message with the value visibly truncated), so this does **not** reopen the "unbounded raw-input reflection" issue `test_invalid_domain_error_is_bounded_without_raw_input_reflection` guards against for `Account` domains -- but it is bounded by pydantic's own defaults, not by any project code.
**How to avoid / what the plan must do:**
1. Accept this as the correct, D-01-compliant behavior for fractional/malformed axis input (it already satisfies "fractional values are rejected" -- no in-body code needed for that half of SCORE-03).
2. Add an explicit functional test asserting this SDK-level error path contains none of the codebase's `BANNED_SUBSTRINGS` (`tests/integration/test_mcp_error_sanitization.py`'s existing list: `Traceback`, `EXA_API_KEY`, etc.) -- it will pass today, but the plan should make this assertion *explicit and committed*, not assumed, since it is SDK-owned behavior the project does not control and could change on a `mcp` package upgrade.
3. Do **not** attempt to intercept/reformat this error inside `score_account`'s own body -- pydantic's `ValidationError` is raised and converted by the SDK's `ToolManager`/`Tool.run()` layer, which sits *outside* the tool function's own `try/except`. There is no supported hook to sanitize it further without a custom `arg_model` (out of scope; the codebase does not do this anywhere today).
**Warning signs:** A test asserting an *exact* one-line message for a malformed-type axis input will fail -- the message is multi-line by construction. Any acceptance criterion phrased as "returns the project's standard sanitized one-line error... via the existing error-wrapper pattern" (SCORE-03's literal wording) applies cleanly to the **range** check (0, 6, etc. -- handled in-body) but only loosely to the **type** check (non-integer JSON values -- handled by the SDK). The plan should scope SCORE-03's acceptance test for the type-check path to "no banned substrings, isError=True" rather than "exact one-line sanitized wording."

### Pitfall 2: `news_days` threading has three call sites, not one, and two of them (`ExaLike` protocol, test fakes) already look "done"
**What goes wrong:** It is easy to add `news_days` only to `get_account_evidence`'s signature and stop there, because `ExaClient.search_news` and the `ExaLike` protocol *already* declare `days: int = 90` -- so a naive grep for "does `days` exist" returns yes everywhere and the actual gap (the two intermediate call sites that drop the parameter on the floor) gets missed.
**Why it happens:** `collect_context` (`src/enrich.py:34-56`) calls `exa.search_news(account.domain)` with no `days` kwarg, silently falling back to the client's own default of 90 regardless of what the MCP caller asked for. `build_evidence_pack` (`src/mcp_server/evidence.py:164-168`) likewise calls `collect_context(account, exa=exa, browserbase=browserbase)` with no way to pass `days` through at all.
**How to avoid:** The threading chain that must change is exactly:
```
get_account_evidence(domain, news_days=None, ctx) -> clamp(news_days or 90, 7, 365)
    -> build_evidence_pack(account, exa=deps.exa, browserbase=deps.browserbase, news_days=clamped)
        -> collect_context(account, exa=exa, browserbase=browserbase, days=clamped)
            -> exa.search_news(account.domain, days=clamped)   # already accepts days, unchanged
```
`collect_context` is also called directly by `Enricher.enrich()` (`src/enrich.py:82`) for the full pipeline -- that call site must keep its existing no-`days`-argument behavior (defaults to 90) since `news_days` is an MCP-only, thin/full-tier-tool-level concept per D-13 ("no new field on the frozen `EvidencePack`" implies no pipeline-wide behavior change). Adding `days: int = 90` as a keyword-only default-90 parameter on `collect_context` keeps `Enricher.enrich()`'s existing call site unchanged (it doesn't pass `days`, so it keeps getting 90) while allowing `build_evidence_pack` to pass a different value.
**Warning signs:** A functional test that clamps `news_days=1000` down to 365 and asserts on `get_account_evidence`'s *output* (e.g. `retrieval_status`) will pass even if the threading is broken, because `FakeExa`/`RecordingExa`-style stubs ignore `days` for retrieval logic. The correct test asserts on the **received `days` kwarg itself** (extend `RecordingExa` in `tests/functional/test_mcp_server.py` to also record `days`, mirroring how it already records `num_results`), not on downstream output shape.

### Pitfall 3: `score_account` must not accidentally become reachable through `DemoLimiter`'s code path by copy-pasting `get_account_evidence`'s structure too literally
**What goes wrong:** Following Pattern 1 too mechanically (copy `get_account_evidence`, rename) risks pulling in the `ctx: Context[ServerSession, EvidenceDeps, Request]` parameter, the `deps = ctx.request_context.lifespan_context` line, and the `if deps.limiter is not None:` block -- all of which would (a) require lifespan wiring `score_account` doesn't need and (b) violate SCORE-02's "never consumes the `DemoLimiter` quota" requirement if the copy-paste isn't fully cleaned up.
**Why it happens:** `get_account_evidence` is the only existing precedent for a thin-tier, sanitized-error tool, so it's the natural template -- but it's a template for a tool *with* external I/O, and `score_account` deliberately has none.
**How to avoid:** `score_account`'s signature should have **zero** MCP-SDK-specific parameters (no `ctx`, no `Context[...]` generic). This is not just a style preference -- it is the structural proof, checkable by a reviewer or a plan-checker at a glance, that the tool cannot reach `DemoLimiter`, `exa`, or `browserbase`, satisfying SCORE-02 by construction rather than by convention.
**Warning signs:** Any import of `EvidenceDeps`, `ServerSession`, or `Request` inside the function body or signature of `score_account`.

## Code Examples

### `compute_total` and `verdict_for` (the math being reused, verbatim)
```python
# Source: src/score.py:105-114 (read from this repo)
def compute_total(breakdown: RubricBreakdown, config: ICPConfig | None = None) -> float:
    cfg = config or get_config()
    weights = {name: axis.weight for name, axis in cfg.axes.items()}
    raw = (
        breakdown.support_volume * weights["support_volume"]
        + breakdown.ai_maturity * weights["ai_maturity"]
        + breakdown.stage_fit * weights["stage_fit"]
        + breakdown.channel_breadth * weights["channel_breadth"]
    )
    return round(raw, 1)
```
```python
# Source: src/icp_config.py:66-71 (read from this repo)
def verdict_for(self, total: float) -> Verdict:
    ranked = sorted(self.verdicts.values(), key=lambda v: v.min_total, reverse=True)
    for v in ranked:
        if total >= v.min_total:
            return v
    return ranked[-1]
```

### Recommended `ScoreResult` shape (new, not yet in the codebase -- a concrete proposal for the planner)
```python
# Proposed: src/mcp_server/scoring.py
from __future__ import annotations

from pydantic import ConfigDict, BaseModel

from src.icp_config import ICPConfig, get_config
from src.models import RubricBreakdown
from src.score import compute_total


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScoreResult(_Frozen):
    domain: str | None = None
    breakdown: RubricBreakdown
    total: float
    verdict: str
    verdict_description: str
    # Echoed rubric context (D-06): plain str/float maps keep the wire
    # payload flat and directly JSON-serializable, no new nested model
    # types beyond what src/icp_config.py already exposes as data.
    weights: dict[str, float]
    verdict_thresholds: dict[str, float]


_AXIS_NAMES = ("support_volume", "ai_maturity", "stage_fit", "channel_breadth")


def build_score_result(
    *,
    support_volume: int,
    ai_maturity: int,
    stage_fit: int,
    channel_breadth: int,
    support_volume_reason: str = "",
    ai_maturity_reason: str = "",
    stage_fit_reason: str = "",
    channel_breadth_reason: str = "",
    domain: str | None = None,
    config: ICPConfig | None = None,
) -> ScoreResult:
    cfg = config or get_config()
    scores = {
        "support_volume": support_volume,
        "ai_maturity": ai_maturity,
        "stage_fit": stage_fit,
        "channel_breadth": channel_breadth,
    }
    for name in _AXIS_NAMES:
        value = scores[name]
        if not 1 <= value <= 5:
            raise ValueError(f"{name} must be an integer 1-5")

    breakdown = RubricBreakdown(
        support_volume=support_volume,
        ai_maturity=ai_maturity,
        stage_fit=stage_fit,
        channel_breadth=channel_breadth,
        support_volume_reason=support_volume_reason,
        ai_maturity_reason=ai_maturity_reason,
        stage_fit_reason=stage_fit_reason,
        channel_breadth_reason=channel_breadth_reason,
    )
    total = compute_total(breakdown, cfg)
    verdict = cfg.verdict_for(total)
    return ScoreResult(
        domain=domain,
        breakdown=breakdown,
        total=total,
        verdict=verdict.label,
        verdict_description=verdict.description,
        weights={name: axis.weight for name, axis in cfg.axes.items()},
        verdict_thresholds={v.label: v.min_total for v in cfg.verdicts.values()},
    )
```
`server.py`'s `score_account` then becomes:
```python
# Proposed addition to src/mcp_server/server.py
def score_account(
    support_volume: int,
    ai_maturity: int,
    stage_fit: int,
    channel_breadth: int,
    support_volume_reason: str = "",
    ai_maturity_reason: str = "",
    stage_fit_reason: str = "",
    channel_breadth_reason: str = "",
    domain: str | None = None,
) -> ScoreResult:
    """Deterministically score four ICP rubric axes and return the weighted
    total and verdict. Pure arithmetic: no LLM, no retrieval, no rate limit.
    Call get_account_evidence and read icp://rubric first, then score each
    axis 1-5 yourself with an [N] citation from the evidence in your reason
    text (not verified server-side). Axis scores must be integers 1-5.
    """
    try:
        return build_score_result(
            support_volume=support_volume,
            ai_maturity=ai_maturity,
            stage_fit=stage_fit,
            channel_breadth=channel_breadth,
            support_volume_reason=support_volume_reason,
            ai_maturity_reason=ai_maturity_reason,
            stage_fit_reason=stage_fit_reason,
            channel_breadth_reason=channel_breadth_reason,
            domain=domain,
        )
    except ValueError:
        raise
```
(The bare `except ValueError: raise` above is deliberately a no-op passthrough shown for clarity that no catch-all `except Exception` is needed here -- `build_score_result` cannot raise anything else, since it does no I/O. A plan should drop the redundant `try/except` entirely and let the `ValueError` propagate directly; it is shown only to make explicit that no additional wrapping occurs.)

### `news_days` clamp (proposed, matching the existing `DemoClampedExa` idiom)
```python
# Proposed addition to src/mcp_server/evidence.py, alongside the existing
# MCP-boundary caps (ABOUT_TEXT_MCP_CAP etc.)
NEWS_DAYS_MIN = 7
NEWS_DAYS_MAX = 365
NEWS_DAYS_DEFAULT = 90


def clamp_news_days(value: int | None) -> int:
    if value is None:
        return NEWS_DAYS_DEFAULT
    return max(NEWS_DAYS_MIN, min(NEWS_DAYS_MAX, value))
```

### `collect_context` and `build_evidence_pack` signature changes (proposed)
```python
# src/enrich.py -- add a keyword-only days param, default 90 preserves the
# existing Enricher.enrich() call site unchanged
async def collect_context(
    account: Account, *, exa: ExaLike, browserbase: BrowserbaseLike, days: int = 90
) -> RawContext:
    ...
    news_results = await exa.search_news(account.domain, days=days)
    ...
```
```python
# src/mcp_server/evidence.py
async def build_evidence_pack(
    account: Account, *, exa: ExaLike, browserbase: BrowserbaseLike, news_days: int | None = None
) -> EvidencePack:
    ctx = await collect_context(
        account, exa=exa, browserbase=browserbase, days=clamp_news_days(news_days)
    )
    return pack_from_context(ctx)
```

## State of the Art

Not applicable in the "library moved on" sense -- this phase touches no external library API surface beyond the already-locked, already-installed `mcp` SDK. The one relevant "state of the art" fact is the confirmed installed-SDK behavior documented in Common Pitfalls #1, which is specific to this project's exact installed version and was verified live rather than assumed from training data or general MCP documentation (which does not typically document the exact wire format of arg-model validation errors).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ScoreResult`'s exact field names/shape (as proposed in Code Examples) is a recommendation, not a locked decision -- CONTEXT.md explicitly leaves this to Claude's Discretion during planning. | Code Examples | Low -- if the planner picks different field names, no other requirement depends on the exact shape; SCORE-01's acceptance criterion only requires breakdown + total + verdict to be present and correct. |
| A2 | The `news_days` clamp function's exact placement (`src/mcp_server/evidence.py` vs. inline in `server.py`) is a recommendation based on where the existing `ABOUT_TEXT_MCP_CAP`-style constants already live, not an explicit CONTEXT.md lock. | Code Examples | Low -- either placement satisfies D-13's "no new EvidencePack field" constraint; this is a code-organization choice only. |
| A3 | `score_account` should be a synchronous (non-`async def`) function, since it performs no I/O and the FastMCP SDK supports sync tool functions (confirmed structurally via `_is_async_callable` branching in `Tool.run()`, and via existing sync resource/prompt functions `read_icp_rubric`/`research_account` in this codebase). | Architecture Patterns, Code Examples | Low -- if the planner prefers `async def score_account(...)` with an immediate synchronous body for consistency with the other two tools' `async def` signatures, that is equally correct; the SDK handles both. This is a style choice, not a correctness requirement. |

**If this table is empty:** N/A -- see entries above. All three assumptions are explicitly flagged in CONTEXT.md as "Claude's Discretion" already, so none require new user confirmation; they are documented here so the planner has a concrete default rather than an open blank.

## Open Questions

1. **Does DOCS-03 require an actual live redeploy of the Oracle instance, or only committing the updated `deploy/oracle/setup.sh` source?**
   - What we know: `deploy/oracle/setup.sh` is the single source-of-truth artifact used both as first-boot cloud-init user-data and as a manually re-run redeploy script (per STATE.md's Phase 13-04 decision log). Editing its landing-page heredoc is a normal, low-risk source change. `make deploy-oracle` / `make provision-oracle` exist as the actual push mechanism.
   - What's unclear: Success Criterion 5 says the landing page "documents `score_account`," which is satisfiable by the committed script alone; it does not explicitly require the plan to execute `make deploy-oracle` against the live 170.9.7.144 host during this phase.
   - Recommendation: scope DOCS-03 to editing and committing `deploy/oracle/setup.sh`'s heredoc content only. Treat an actual live redeploy (verifying the public landing page reflects the change) as an optional, explicitly-flagged manual/checkpoint step the user can choose to run afterward via the existing `make deploy-oracle` target -- not a blocking phase-completion gate, since no offline test can verify a live redeploy anyway and the phase's own offline gate (TEST-03) does not exercise the deploy script.

2. **Exact wording for the range-check `ValueError` message and whether it should name the offending axis.**
   - What we know: `_sanitized_validation_message`'s existing precedent (for `Account`) is generic ("invalid domain," no field name). The proposed `f"{name} must be an integer 1-5"` in Code Examples names the axis for usability, which is a minor departure from that precedent (but axis names are not sensitive, unlike raw user-supplied domains).
   - What's unclear: whether the planner/user prefers strict precedent-matching (a single generic message for any axis, e.g. `"axis score must be an integer 1-5"`) over the more specific, per-axis wording.
   - Recommendation: use the per-axis wording (more actionable for the calling agent, no sensitivity concern) unless the planner has reason to prefer the generic form for stylistic consistency; either satisfies SCORE-03 literally.

## Environment Availability

Skipped -- this phase has no new external dependency, no new service, and no new CLI tool. The `mcp` SDK, `EXA_API_KEY`, and all other environment prerequisites are already required and already verified by the existing Phase 10-13 test suite; nothing new is added.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=8.2.0` + `pytest-asyncio>=0.23.0` (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest -m "not smoke" tests/unit/test_score_math.py tests/functional/test_mcp_server.py -x` |
| Full suite command | `make test` (== `uv run pytest -m "not smoke"`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCORE-01 | `score_account` math delegates correctly to `compute_total`/`verdict_for` | unit | `pytest tests/unit/test_mcp_scoring.py -x` | ❌ Wave 0 (new file) |
| SCORE-02 | `score_account` registered on both tiers, never touches `DemoLimiter`, no `ctx` param | functional (in-memory MCP client) | `pytest tests/functional/test_mcp_server.py -k score_account -x` | ❌ Wave 0 (extend existing file) |
| SCORE-03 | `readOnlyHint`/`destructiveHint` annotations; sanitized error on range-violation; SDK-level error on type-violation contains no banned substrings | functional + integration | `pytest tests/functional/test_mcp_server.py tests/integration/test_mcp_error_sanitization.py -k score_account -x` | ❌ Wave 0 (extend both existing files) |
| PROMPT-01 | `research_account` prompt text contains the numbered steps, `score_account`, and the empty-evidence skip rule | functional | `pytest tests/functional/test_mcp_server.py -k research_account_prompt -x` | ❌ Wave 0 (extend `test_research_account_prompt_contains_required_elements`-style tests) |
| EVID-01 | `news_days` clamps 7-365, omitted preserves 90, threads to `exa.search_news(days=...)` | unit + functional | `pytest tests/unit/test_evidence.py -k news_days -x` and `pytest tests/functional/test_mcp_server.py -k news_days -x` | ❌ Wave 0 (extend both existing files) |
| TEST-04 | Explicit clamp-boundary coverage (6 -> 7, 366 -> 365, omitted -> 90) | unit | `pytest tests/unit/test_evidence.py -k clamp_news_days -x` | ❌ Wave 0 (new test function in existing file) |

### Sampling Rate
- **Per task commit:** targeted `pytest <changed test file> -x`
- **Per wave merge:** `make test` (full offline suite, `-m "not smoke"`)
- **Phase gate:** `make test && make typecheck && make lint` green, plus `uv run python scripts/check_public_discipline.py` (`verify-public-repo`), before `/gsd-verify-work`. `make typecheck` scope is `mypy src evals` (verified in `Makefile:57`) -- `tests/` is not under the strict mypy gate, matching the project's existing precedent of tests being exempt from strict typing enforcement (though `[tool.mypy]` `strict = true` in `pyproject.toml` still nominally applies project-wide; the Makefile target is the actual enforced gate).

### Wave 0 Gaps
- [ ] `tests/unit/test_mcp_scoring.py` -- new file, unit-tests `build_score_result` directly (no MCP transport), mirroring `tests/unit/test_score_math.py`'s style: all-5s, all-1s, weighted-average-matches-manual, out-of-range rejection (0, 6, -1), fractional-not-applicable-at-this-layer (ints only, no float test needed here since the type boundary is upstream)
- [ ] Extend `tests/functional/test_mcp_server.py` with `score_account` wire-level tests: happy path (structuredContent has breakdown/total/verdict/weights/verdict_thresholds), range-violation sanitized error, type-violation (string/float axis) SDK-level error assertion (no banned substrings, `isError=True`), tier registration (`score_account` present in both `tier="thin"` (default) and `tier="full"` tool listings), annotations (`readOnlyHint`/`destructiveHint`)
- [ ] Extend `tests/integration/test_mcp_error_sanitization.py`'s `BANNED_SUBSTRINGS` assertion pattern to cover `score_account`'s SDK-level type-violation error text
- [ ] Extend `tests/unit/test_evidence.py` with `clamp_news_days` boundary tests
- [ ] Extend `tests/functional/test_mcp_server.py`'s `RecordingExa` (or a new fake) to record the `days` kwarg it receives from `search_news`, then assert clamped/default values reach it via `get_account_evidence(domain, news_days=...)`
- [ ] Extend `tests/functional/test_mcp_server.py::test_research_account_prompt_contains_required_elements`-style assertions to require `score_account`, the numbered-step structure, and the empty-evidence skip-rule wording in the rewritten prompt text

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Unauthenticated MCP endpoint by design (existing project posture, unchanged by this phase) |
| V3 Session Management | no | `stateless_http=True` (existing, unchanged) |
| V4 Access Control | no | No new access-control surface; `score_account` is intentionally available to every caller on every tier (SCORE-02) |
| V5 Input Validation | yes | Plain-`int` type coercion (SDK-level, D-04) + explicit in-body range check (`1 <= value <= 5`) for `score_account`; `max(7, min(365, value))` clamp for `news_days` -- both are allowlist-style bounded validation, not denylist |
| V6 Cryptography | no | No new cryptographic operation |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unbounded resource consumption via a very large/adversarial `news_days` value forcing an oversized Exa query window | Denial of Service (resource) | Server-side clamp to [7, 365] before the value ever reaches `ExaClient.search_news` (D-13); the clamp happens regardless of tier, so even the full (unrationed) tier cannot be pushed past 365 days |
| Information disclosure via verbose type-validation error echoing raw caller input | Information Disclosure | Confirmed (Common Pitfalls #1) that pydantic's own `input_value=` repr is bounded/truncated by pydantic itself, and contains no server-side secrets/paths -- explicitly test this with the existing `BANNED_SUBSTRINGS` pattern rather than assuming it holds across `mcp` package upgrades |
| Fabricated/ungrounded ICP verdicts reaching a client despite empty evidence | Tampering (of the demo's own honesty guarantee, not a classic security threat, but a project-specific integrity property) | D-10's explicit prompt-level skip rule (agent must not call `score_account` when `retrieval_status == "empty"`) -- this is grounding-by-instruction, not enforced server-side, since `score_account` is stateless and has no way to know what evidence the caller saw; document this limitation honestly in DOCS-04 rather than implying server-side enforcement that does not exist |
| A future caller passing out-of-range or negative axis integers to force an unexpected `RubricBreakdown` state | Tampering | In-body range check (`1 <= value <= 5`) rejects before `RubricBreakdown` construction; `RubricBreakdown`'s own `Field(ge=1, le=5)` constraint (`src/models.py:172-175`) is a second, independent layer of defense-in-depth even if the manual check had a bug -- both layers should be validated by tests, not just the outer one |

## Sources

### Primary (HIGH confidence)
- `src/mcp_server/server.py`, `src/mcp_server/evidence.py`, `src/mcp_server/wiring.py`, `src/mcp_server/limits.py`, `src/mcp_server/__main__.py` -- read verbatim from this repo, 2026-07-17
- `src/score.py`, `src/icp_config.py`, `src/models.py`, `src/enrich.py`, `src/clients/exa_client.py`, `src/clients/protocols.py`, `src/_json_utils.py` -- read verbatim from this repo, 2026-07-17
- `tests/functional/test_mcp_server.py`, `tests/integration/test_mcp_error_sanitization.py`, `tests/unit/test_score_math.py`, `tests/unit/test_evidence.py`, `tests/functional/test_enrich.py` -- read verbatim from this repo, 2026-07-17
- `README.md` (MCP server section, lines 152-213), `deploy/oracle/setup.sh` (landing-page heredoc, lines 140-217) -- read verbatim from this repo, 2026-07-17
- `configs/icp.yaml` -- axis weights, verdict thresholds read verbatim, 2026-07-17
- `.venv/lib/python3.12/site-packages/mcp/server/fastmcp/utilities/func_metadata.py`, `.venv/.../tools/base.py`, `.venv/.../server/lowlevel/server.py` -- the exact installed `mcp` SDK version in this project's `.venv`, read verbatim, 2026-07-17
- Live probe scripts run against the installed `mcp` SDK via `uv run python` (in-memory `create_connected_server_and_client_session` harness, matching the project's own test pattern) confirming: (a) SDK-level type-validation error wire format for malformed int/float axis inputs, (b) that pydantic bounds/truncates long raw-input reflection by default, (c) the exact `"Error executing tool <name>: <message>"` prefix the SDK applies uniformly to tool-body-raised `ValueError`s -- executed 2026-07-17, `[VERIFIED: local execution against installed dependency]`

### Secondary (MEDIUM confidence)
None used -- no web/docs lookup was needed for this phase; every question was answerable by reading the local codebase and the installed dependency directly, which is a stronger source than external documentation for "what does *this exact installed version* do."

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependency; installed `mcp` version confirmed locally
- Architecture: HIGH -- every seam (`server.py`, `evidence.py`, `enrich.py`, `score.py`, `icp_config.py`) read verbatim; the new module's shape is a direct extrapolation of an existing, working pattern (`evidence.py`)
- Pitfalls: HIGH -- the one non-obvious finding (SDK-level type-validation error format) was verified by executing code against the actual installed dependency, not inferred from training data or general MCP documentation
- Docs surfaces: HIGH -- exact line ranges in `README.md` and `deploy/oracle/setup.sh` identified and quoted

**Research date:** 2026-07-17
**Valid until:** 30 days (stable, internal-only phase; no external API surface to drift) -- shorter validity only if `mcp` is upgraded past the `<2.0` pin before planning starts, in which case Pitfall 1's exact error wording should be re-verified
