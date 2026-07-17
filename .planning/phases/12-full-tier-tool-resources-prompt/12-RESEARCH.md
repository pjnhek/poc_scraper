# Phase 12: Full-Tier Tool, Resources & Prompt - Research

**Researched:** 2026-07-17
**Domain:** MCP SDK surface extension (tools/resources/prompts) over an existing, locked pipeline
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Full-tool result shape (MCP-05)**
- **D-01:** `research_account_full` returns `ScoredAccount.model_dump()` verbatim: no MCP-boundary caps, no second serialization path (per the design spec and Phase 10 D-02's one-model-one-serialization principle). Size is bounded upstream (enrichment caps, 3 personas, 3 hooks) and BYOK-local means no hosted-payload concern. `ScoredAccount.enrichment` carries the numbered justifications, so `[N]` citations in hooks resolve within the payload itself.
- **D-02:** `run_eval=False` must never read as a failure: `eval_score` stays `None` AND the status precedence logic must NOT apply the `eval_score=None -> judge_failed` mapping (which today distinguishes "evaluated clean" from "eval crashed" in `src/pipeline.py`'s D-03 precedence block). A deliberate skip yields `clean` or `hook_suppressed` exactly as the pipeline determined without the judge; `judge_failed`/`low_groundedness` are impossible outcomes when the caller opted out. How this threads through (parameter on `process_account` vs status recomputation) is the planner's call, but the honesty semantics are locked.
- **D-03:** Degraded stages mirror the sheet exactly: `process_account`'s per-stage isolation is inherited unchanged. Unscoreable accounts return a SUCCESSFUL result with `error` text and empty score/hooks; `hook_suppressed` and `low_groundedness` flow through as-is. Never promoted to `isError`; empty retrieval is honest data, not an error (Phase 10 precedent).

**Long-call ergonomics (MCP-05)**
- **D-04:** The server reports per-stage progress during the 30-60s call via `ctx.report_progress`/`ctx.info` at stage boundaries (enrich, score, personas, outreach, eval). Clients that ignore progress lose nothing; a silent 60s call invites assumed-hang retries that burn a second full run.
- **D-05:** Progress escapes the sealed pipeline via an ADDITIVE optional callback: `process_account` gains an `on_stage: ... | None = None` style parameter, default `None`, so `make run`, the CLI path, and every existing test are untouched. The MCP wrapper passes a closure that forwards to `ctx`. Do NOT re-compose stages in the MCP layer and do NOT settle for coarse before/after-only progress. Exact callback signature is the planner's call.
- **D-06:** Tool description carries the 30-60s runtime warning and notes `run_eval=False` skips the judge for roughly half the latency (spec-locked wording intent; exact phrasing Claude's discretion).

**Resource serving (MCP-02, MCP-03)**
- **D-07:** Both resources read from disk per request, no startup caching. Files are small (icp.yaml ~5KB, REPORT.md ~21KB) and per-request reads keep the "edit the rubric, retarget the vertical" story true without a server restart.
- **D-08:** Missing/unreadable resource file returns a sanitized "resource unavailable"-style message with the real cause logged to stderr (HOST-05 discipline, same as tool errors). Never fail startup over a missing doc artifact; never serve empty content (conflicts with the no-fake-data rule).

**Prompt design (MCP-04)**
- **D-09:** The `research_account(domain)` prompt POINTS at the `icp://rubric` resource rather than embedding rubric content: read the rubric, call `get_account_evidence(domain)`, score each axis 1-5 with the stated weights, propose top-3 personas, draft outreach. Keeps the prompt static, the rubric the single editable source of truth, and teaches the resource surface.
- **D-10:** Citation discipline is a HARD rule mirroring the `get_account_evidence` docstring contract: every claim MUST carry an `[N]` index from `justifications`; claims without a matching index MUST be dropped; if `retrieval_status` is `empty`, state that the account cannot be researched, never fabricate. This is the grounding-by-instruction story the README will contrast with grounding-by-construction (Phase 13 DOCS-02).
- **D-11:** One static prompt on every tier: no tier-conditional mention of `research_account_full`. The prompt works identically on the hosted demo and BYOK local; the two-tier contrast stays a clean README story.

**Locked by prior phases / requirements (do not re-litigate)**
- Tier resolved once at startup by `Settings.mcp_tier()`; `MCP_DEMO_MODE=1` forces thin and the full tool is NOT REGISTERED (hidden, not visible-but-refusing) — roadmap criterion 2 demands a test proving this with full keys present.
- Full tier wires through `open_deps()` (Phase 9 D-04); thin tier keeps wiring itself via `make_thin_lifespan`. `open_deps` owns replay/record branching, so the full tool inherits replay fixtures for free.
- All domain failures surface as sanitized `isError: true` tool results with plain messages, never protocol errors (MCP-07, Phase 10 D-07/D-08). Invalid domains pass through the `Account` validator message; the full tool validates through `Account` exactly like the thin tool.
- `readOnlyHint=True`/`destructiveHint=False` annotations on `research_account_full` (MCP-07 covers "both tools").
- Server stays read-only: no Sheets writes from the MCP surface; `run_eval` default is `True` (spec).
- Demo mode forces `NullBrowserbase` regardless of credentials (locked rail, re-asserted by commit `4fbc1bf`).
- Stack pin `mcp>=1.28,<2.0`; strict mypy, no new overrides; 5-layer test strategy with in-memory functional tests via `mcp.shared.memory`.

### Claude's Discretion
- Resource MIME types (text/yaml-style for the rubric, text/markdown for the report suggested), exact URI registration mechanics, and resource docstrings.
- Exact progress-callback signature and stage-name strings; exact progress/log API mix (`report_progress` vs `info`).
- Exact tool-description phrasing (runtime warning, run_eval hint) and prompt paragraph structure within D-09/D-10/D-11 constraints.
- How run_eval=False threads through the eval stage and status computation, provided D-02's semantics hold.
- Full-tier lifespan composition (how `open_deps` nests with the FastMCP lifespan alongside thin-tier deps).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Public-hostname allowlist setting + `0.0.0.0` bind integration test stay in Phase 13 per the post-review closeout; README grounding contrast is Phase 13 DOCS-02.)

Out of this phase entirely (per CONTEXT.md phase boundary): Fly.io deploy, Dockerfile, `fly.toml`, the public-hostname `TransportSecuritySettings` allowlist entry, hardened-error verification, and README/CLAUDE.md docs (all Phase 13).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-02 | An MCP client can read the ICP rubric via the `icp://rubric` resource | Pattern 2 (registration), Pattern 5 (sanitized-read-failure handling), Pitfall 5 (MIME type), Wave 0 gap: `tests/unit/test_mcp_resources.py` |
| MCP-03 | An MCP client can read the eval calibration report via the `icp://eval-report` resource | Same as MCP-02; reuses `evals/report.py::REPORT_PATH` as the path source of truth (see Sources) instead of a hardcoded string |
| MCP-04 | A user can invoke the `research_account` prompt, guiding rubric-based scoring where every claim cites an `[N]` justification index and unciteable claims are dropped | Code Examples ("Prompt decorator: a plain str return becomes one UserMessage"); Architecture Patterns Pattern 2 (registration); test map row for MCP-04 |
| MCP-05 | A BYOK user (writer/judge + Browserbase keys) can call `research_account_full(domain, run_eval)` and receive the complete grounded `ScoredAccount` JSON including `AccountStatus` | Pattern 1 (lifespan composition), Pattern 2 (tier-gated registration), Pattern 3 (D-02 run_eval honesty), Pattern 4 (D-04/D-05 progress), Pitfalls 1-4, full Validation Architecture test map |

</phase_requirements>

## Summary

This phase adds three new MCP surfaces to an already-shipped, well-tested server (Phase 10/11): a gated
`research_account_full` tool, two read-only resources (`icp://rubric`, `icp://eval-report`), and a static
`research_account` prompt. There is no new external dependency, no new provider integration, and no new
retrieval logic — every piece of business logic this phase touches already exists and is locked
(`process_account`, `open_deps`, `ScoredAccount`, `configs/icp.yaml`, `evals/REPORT.md`). The work is
almost entirely **wiring**: gating tool registration on the resolved tier, composing a lifespan that
satisfies both the always-registered thin tool and the new full tool, and writing two small resource
functions plus one prompt function.

The one piece of genuine design work — and the one place the plan can go wrong — is **full-tier lifespan
composition**. `get_account_evidence` (the thin tool) is *always* registered per the design spec, including
on a full-tier server, so the full-tier lifespan's context object must satisfy both `get_account_evidence`'s
needs (`exa`, `browserbase`, `limiter`) and `research_account_full`'s needs (the `Deps` bundle: enricher,
scorer, contacts, outreach, eval_rubric). This research found that `Deps` currently has exactly one
construction site (`build_deps` inside `src/pipeline.py`), which makes extending `Deps` with `exa`,
`browserbase`, and `limiter` fields a safe, additive, zero-test-breakage change — and it lets the full-tier
lifespan collapse to a single `async with open_deps(settings) as deps: yield deps` (see Architecture
Patterns below). This is the single most consequential decision the plan needs to lock, because it
determines whether the full-tier server runs one httpx connection pool or two.

Everything else — `run_eval=False` status semantics (D-02), progress reporting (D-04/D-05), resource error
handling (D-08), and the static prompt (D-09/D-10/D-11) — is a small, well-scoped, additive change to code
this research read directly and verified against the installed `mcp==1.28.1` SDK source. mypy strict
compliance is achievable but requires one specific fix: `get_account_evidence`'s `Context[ServerSession,
ThinDeps, Request]` type parameter must become a `Protocol` (or the extended `Deps` type) so the same
function type-checks when registered against a full-tier lifespan whose context object is not literally
`ThinDeps`.

**Primary recommendation:** Extend `Deps` with `exa: ExaLike`, `browserbase: BrowserbaseLike`, and
`limiter: DemoLimiter | None = None` fields (populated in `build_deps`, always `None` for `limiter` since
full tier is never demo mode); make the full-tier lifespan a thin wrapper around `open_deps(settings)`
directly (no second Exa/Browserbase construction, no second httpx pool); introduce a
`EvidenceDeps(Protocol)` structural type so `get_account_evidence` type-checks against both `ThinDeps` and
the extended `Deps`; add `run_eval: bool = True` and `on_stage: Callable[[str], Awaitable[None]] | None =
None` as additive keyword parameters on `process_account`, both defaulting to today's exact behavior.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tier-gated tool registration | API/Backend (`src/mcp_server/server.py::build_server`) | — | `build_server` is the single place tools are attached to the FastMCP instance; registration must branch on the resolved tier here, not in `__main__.py` |
| Full-tier client/deps wiring | API/Backend (`src/mcp_server/wiring.py`, `src/pipeline.py::open_deps`) | — | Lifespan composition owns client lifetime; `open_deps` already owns replay/record branching per Phase 9 D-01, so full-tier wiring must not duplicate it |
| Resource serving (rubric, eval report) | API/Backend (`src/mcp_server/server.py`, new resource functions) | Database/Storage (reads `configs/icp.yaml`, `evals/REPORT.md` from disk) | Both files are committed source-of-truth artifacts on disk; the resource function is a thin per-request file read, no new storage layer |
| Prompt orchestration guidance | API/Backend (prompt text authored server-side) | Browser/Client (the calling agent executes the guided steps) | The prompt is static text the server serves; the actual multi-step research work happens client-side in the calling agent's own reasoning loop, which is why D-09 has the prompt *point at* the rubric resource and the evidence tool rather than re-implementing scoring server-side |
| Progress reporting during the 30-60s full-tier call | API/Backend (`process_account`'s `on_stage` callback, forwarded via `ctx.report_progress`/`ctx.info`) | — | Must originate inside the pipeline stage loop (only place stage boundaries are known); the MCP layer only supplies the callback closure, never re-implements stage sequencing (explicitly forbidden by D-05) |
| Run-eval honesty semantics (D-02) | API/Backend (`process_account`'s status-precedence block) | — | `AccountStatus` is computed in the same function for both the CLI/sheet path and the MCP path; a second, MCP-local status-recomputation would violate the "one model, one serialization path" principle already locked in Phase 10 D-02 |

## Standard Stack

No new packages this phase. The MCP SDK is already pinned (`mcp>=1.28,<2.0`, installed `1.28.1`) and provides
everything needed: `FastMCP.tool()`, `FastMCP.resource()`, `FastMCP.prompt()`, and `Context.report_progress`
/`Context.info`/`Context.debug`/`Context.warning`/`Context.error`. All verified directly against the
installed SDK source at `.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py` (this session).

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (official Python SDK, FastMCP) | 1.28.1 (installed; pin `mcp>=1.28,<2.0` unchanged) | Tool/resource/prompt decorators, `Context` progress/logging API | Already locked in Phase 10; no version bump needed for this phase's surface [VERIFIED: installed package `uv pip show mcp` + source inspection] |
| `pyyaml` | already a dependency | Not touched by resource serving — `icp://rubric` serves the raw YAML text file verbatim (D-07: no parsing, no re-serialization), so `configs/icp.yaml`'s existing loader (`src/icp_config.py`) is not on this phase's critical path | [VERIFIED: `src/icp_config.py` read this session] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib.Path` (stdlib) | — | Resource functions read `configs/icp.yaml` and `evals/REPORT.md` from disk per request (D-07) | Every resource read |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-request disk read (D-07, locked) | Startup caching of resource content | Locked out by D-07: files are small (~5KB, ~21KB) and per-request reads keep "edit the rubric, retarget the vertical" true without a server restart |
| `Deps` gains `exa`/`browserbase`/`limiter` fields (recommended) | Independent second Exa/Browserbase construction in the full-tier lifespan (mirroring `make_thin_lifespan`) | The independent-construction path duplicates client lifetime management, opens a second httpx pool, and — critically — does NOT inherit `open_deps`'s replay/record branching (Phase 9 D-01), so `get_account_evidence` calls on the full tier would silently skip replay fixtures in demo-bundle mode. See Common Pitfalls. |

**Installation:** None required. `mcp` is already in `pyproject.toml` and `uv.lock`.

**Version verification:**
```bash
uv pip show mcp
```
Confirmed this session: `mcp==1.28.1`, matching the `pyproject.toml` pin `mcp>=1.28,<2.0`. No action needed.

## Package Legitimacy Audit

No new external packages are introduced by this phase. All required functionality (`FastMCP.resource()`,
`FastMCP.prompt()`, `Context.report_progress`) ships in the already-installed and already-audited `mcp`
package (legitimacy verified in Phase 10 per `.planning/STATE.md`: "mcp SDK SUS heuristic flag resolved as
false positive via uv pip show + Project-URL metadata cross-check against official
modelcontextprotocol/python-sdk repo"). No package-legitimacy gate action is required for this phase.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │           MCP Client (agent)             │
                         └───────────────┬───────────────────────────┘
                                          │ JSON-RPC (stdio or streamable HTTP)
                                          ▼
                         ┌─────────────────────────────────────────┐
                         │        FastMCP server (build_server)      │
                         │                                           │
                         │  tier = resolve_and_log_tier(settings)    │
                         │        (Settings.mcp_tier(), Phase 10)    │
                         └───────────────┬───────────────────────────┘
                                          │
                    ┌─────────────────────┼──────────────────────────┐
                    │                     │                          │
         always registered      always registered           tier == "full" only
                    │                     │                          │
                    ▼                     ▼                          ▼
        ┌───────────────────┐  ┌──────────────────────┐   ┌──────────────────────────┐
        │ get_account_evidence│  │ icp://rubric          │   │ research_account_full     │
        │ (thin tool, Phase10)│  │ icp://eval-report     │   │ (NEW, this phase)         │
        └─────────┬───────────┘  │ research_account       │   └─────────────┬─────────────┘
                   │              │ prompt (NEW)           │                 │
                   │              └───────────┬────────────┘                 │
                   │                          │                              │
                   ▼                          ▼                              ▼
        deps.exa / deps.browserbase   read configs/icp.yaml           process_account(account, deps,
        (from lifespan context)       read evals/REPORT.md            run_eval, on_stage)
                   │                  per request, disk (D-07)              │
                   │                                                        ▼
                   │                                          ┌──────────────────────────┐
                   │                                          │ enrich → score → contacts  │
                   │                                          │ → outreach → eval (D-02/03)│
                   │                                          │ same process_account body   │
                   │                                          │ used by make run / CLI      │
                   │                                          └─────────────┬─────────────┘
                   │                                                        │
                   └──────────────────┬─────────────────────────────────────┘
                                       ▼
                         Both draw exa/browserbase/writer/judge
                         from the SAME open_deps(settings) call
                         (recommended lifespan composition, below)
```

### Recommended Project Structure

No new files. Every change lands in existing modules:
```
src/
├── pipeline.py          # Deps gains exa/browserbase/limiter fields; process_account gains
│                         # run_eval and on_stage kwargs; open_deps unchanged
├── mcp_server/
│   ├── server.py         # research_account_full tool body + tier-gated registration;
│   │                     # icp://rubric and icp://eval-report resource functions;
│   │                     # research_account prompt function
│   └── wiring.py         # make_full_lifespan(settings) alongside make_thin_lifespan
```

### Pattern 1: Full-tier lifespan as a thin wrapper around `open_deps`

**What:** Rather than reconstructing Exa/Browserbase clients a second time for the full-tier server (which
would duplicate `open_deps`'s replay/record branching), extend `Deps` with the fields
`get_account_evidence` needs, and make the full-tier lifespan nothing more than `open_deps(settings)`.

**When to use:** Any tier whose deps type must satisfy both the thin tool's and the full tool's needs
simultaneously (this phase, and any future full-tier addition).

**Example:**
```python
# src/pipeline.py — additive fields on Deps, populated from build_deps's existing params
@dataclass(frozen=True)
class Deps:
    enricher: Enricher
    scorer: Scorer
    contacts: ContactExtractor
    outreach: OutreachGenerator
    eval_rubric: EvalRubric
    exa: ExaLike                              # NEW — same instance Enricher already wraps
    browserbase: BrowserbaseLike              # NEW — same instance Enricher already wraps
    limiter: DemoLimiter | None = None        # NEW — always None; full tier is never demo mode


def build_deps(
    writer: LLMClient, judge: LLMClient, exa: ExaLike, browserbase: BrowserbaseLike,
) -> Deps:
    return Deps(
        enricher=Enricher(exa=exa, browserbase=browserbase, llm=writer),
        scorer=Scorer(llm=writer),
        contacts=ContactExtractor(llm=writer),
        outreach=OutreachGenerator(llm=writer),
        eval_rubric=EvalRubric(llm=judge),
        exa=exa,
        browserbase=browserbase,
    )
```
```python
# src/mcp_server/wiring.py — full-tier lifespan is now this simple
def make_full_lifespan(settings: Settings) -> Callable[[FastMCP], AbstractAsyncContextManager[Deps]]:
    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[Deps]:
        async with open_deps(settings) as deps:
            yield deps
    return lifespan
```
```python
# src/mcp_server/server.py — a Protocol lets get_account_evidence type-check against
# both ThinDeps and the extended Deps without inheritance
class EvidenceDeps(Protocol):
    exa: ExaLike
    browserbase: BrowserbaseLike
    limiter: DemoLimiter | None

async def get_account_evidence(
    domain: str, ctx: Context[ServerSession, EvidenceDeps, Request]
) -> EvidencePack:
    ...  # body unchanged
```
This means one httpx connection pool per full-tier server process (not two), and `get_account_evidence`
called on a full-tier server automatically inherits replay-mode behavior when `DEMO_BUNDLE` is set, exactly
like `research_account_full` does — because both draw from the same `open_deps` call.

**Why not the alternative (independent second client stack, mirroring `make_thin_lifespan`'s body inside
the full-tier lifespan):** it works, is lower-risk to `Deps`'s existing shape, but opens a second httpx
pool and a second set of Exa/Browserbase instances that do NOT go through `open_deps`'s replay/record
branching — so `get_account_evidence` on a full-tier replay-mode server would hit the live network while
`research_account_full` replays from fixtures in the same process. This is a real behavioral inconsistency,
not just an efficiency concern, and is the reason this research recommends the `Deps`-extension pattern.

### Pattern 2: Tier-gated tool registration

**What:** `build_server` decides whether to attach `research_account_full` based on the resolved tier, not
on whether `settings` is `None` (that flag is reserved for HTTP-transport-only kwargs and is `None` on the
stdio path even for a full-tier server today — see Common Pitfalls).

**Example:**
```python
def build_server(
    lifespan: Callable[[FastMCP], AbstractAsyncContextManager[EvidenceDeps]],
    tier: Literal["thin", "full"] = "thin",
    settings: Settings | None = None,
) -> FastMCP:
    server = FastMCP(...)  # unchanged construction logic
    server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
        get_account_evidence
    )
    server.resource("icp://rubric", mime_type="application/yaml")(read_icp_rubric)
    server.resource("icp://eval-report", mime_type="text/markdown")(read_eval_report)
    server.prompt()(research_account)
    if tier == "full":
        server.tool(
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
            description=(
                "Runs the complete grounded research pipeline for one domain "
                "(enrich, score, personas, cited outreach, judge eval). "
                "Takes 30-60 seconds; run_eval=False skips the judge for roughly half the latency."
            ),
        )(research_account_full)
    return server
```
`tier` defaults to `"thin"` so every pre-existing call site (`build_server(lifespan=...)` in the current
test suite) keeps registering exactly one tool, unchanged — this is the same additive-parameter-with-default
convention already used for `max_tokens` (Phase 5 precedent, cited in CONTEXT.md).

### Pattern 3: `run_eval` honesty in the status-precedence block (D-02)

**What:** `process_account` gains `run_eval: bool = True`. When `False`, the eval-rubric call is skipped
entirely (never attempted, so it can never "fail"), and the precedence block gets one new branch that must
be evaluated BEFORE the existing "`eval_score is None` -> `judge_failed`" branch, but AFTER the
`hook_suppressed` check (hook suppression must still win regardless of whether eval ran).

**Example:**
```python
async def process_account(
    account: Account,
    deps: Deps,
    *,
    run_eval: bool = True,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> ScoredAccount:
    ...  # enrich/score/contacts/outreach stages unchanged; call on_stage(name) at each boundary if set

    eval_score: EvalScore | None = None
    if run_eval:
        try:
            eval_score = await deps.eval_rubric.evaluate_account(sa)
        except (RateLimitError, APIStatusError, APIError, ValidationError) as exc:
            log.warning("eval failed [%s] for %s: %s", type(exc).__name__, account.domain, exc)
            eval_score = None

    if eval_score is not None and eval_score.eval_failed:
        final_status = AccountStatus.judge_failed
    elif all(h.paragraph == "" for h in hooks):
        final_status = AccountStatus.hook_suppressed
    elif not run_eval:
        # D-02: a deliberate skip must never read as a failure.
        final_status = AccountStatus.clean
    elif eval_score is None:
        final_status = AccountStatus.judge_failed
    elif eval_score.is_flagged:
        final_status = AccountStatus.low_groundedness
    else:
        final_status = AccountStatus.clean
```
Default `run_eval=True` means every existing call site (`make run`, all pipeline tests, `evals/run_live.py`)
takes the exact same code path as before — the new branch is unreachable unless a caller explicitly passes
`run_eval=False`.

### Pattern 4: Progress reporting via an additive callback (D-04/D-05)

**What:** `on_stage: Callable[[str], Awaitable[None]] | None = None` is called at each stage boundary
inside `process_account`. The MCP wrapper supplies a closure over `ctx`; every other caller passes nothing
and gets the exact pre-Phase-12 behavior.

**Example:**
```python
# src/mcp_server/server.py
async def research_account_full(
    domain: str, ctx: Context[ServerSession, Deps, Request], run_eval: bool = True
) -> ScoredAccount:
    try:
        account = Account(domain=domain)
    except ValidationError as exc:
        raise ValueError(_sanitized_validation_message(exc)) from None

    deps = ctx.request_context.lifespan_context
    stages = ("enrich", "score", "contacts", "outreach", "eval") if run_eval else (
        "enrich", "score", "contacts", "outreach",
    )
    total = len(stages)
    seen = {"n": 0}

    async def on_stage(stage: str) -> None:
        seen["n"] += 1
        await ctx.report_progress(seen["n"], total, message=f"{stage} complete")

    return await process_account(account, deps, run_eval=run_eval, on_stage=on_stage)
```
`ctx.report_progress` is a documented no-op when the calling client did not attach a `progressToken` to the
request [VERIFIED: `mcp/server/fastmcp/server.py:1162-1180`, installed SDK source, this session] — so
clients that ignore progress genuinely lose nothing, confirming D-04's premise without further testing
required for that specific guarantee.

### Pattern 5: Resource functions catch, never raise (D-08)

**What:** A resource function that raises has its exception logged via the SDK's own `logger.exception`
(unsanitized `str(e)`, which for a missing-file `OSError` includes the full path) and re-raised as
`mcp.server.fastmcp.exceptions.ResourceError`, which becomes a **protocol-level JSON-RPC error**, not a
successful resource read with sanitized text [VERIFIED: `mcp/server/fastmcp/server.py:382-395`, installed
SDK source, this session]. This is a different failure model than tools (`isError: true` inside a
successful `CallToolResult`) — resources have no such honesty channel. D-08's "sanitized message, never
fail, never leak the cause" therefore has to happen INSIDE the resource function, before any exception can
reach the SDK's dispatch layer.

**Example:**
```python
def read_icp_rubric() -> str:
    """Serve configs/icp.yaml verbatim so any MCP client can inspect the ICP rubric this
    server scores against. Read from disk on every call (no startup caching) so an edited
    rubric is visible without a server restart."""
    try:
        return Path("configs/icp.yaml").read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("icp rubric resource unavailable: %s", exc)
        return "resource unavailable: the ICP rubric could not be read on the server."
```
Never returns `""` (violates "never serve empty content" / no-fake-data rule) and never lets the real
`OSError` message (which contains a filesystem path) reach the client.

### Anti-Patterns to Avoid

- **Passing `settings=None` to gate tier-conditional registration:** `build_server`'s existing `settings`
  parameter is deliberately `None` on the stdio path today (it only carries HTTP-transport kwargs), so
  reusing it to decide "is this a full-tier server?" would make stdio full-tier servers register only the
  thin tool. Use an explicit `tier` parameter instead (Pattern 2).
- **Re-composing pipeline stages inside the MCP tool body** to get finer-grained progress than
  `process_account` exposes: explicitly forbidden by D-05 — it would duplicate the per-stage exception
  isolation and D-02/D-03 status-precedence logic that already lives in `process_account`, creating two
  places that can drift out of sync.
- **Raising from a resource function on a missing/unreadable file:** produces a protocol-level error with
  an unsanitized path in the message (see Pattern 5); catch inside the resource function instead.
- **Manually calling `.model_dump()` on the returned `ScoredAccount`:** the existing `get_account_evidence`
  tool already proves FastMCP auto-converts a returned Pydantic `BaseModel` into `structuredContent` via its
  own serialization path (see `tests/functional/test_mcp_server.py::test_happy_path_returns_structured_evidence_pack`,
  which asserts `result.structuredContent` populated from a function that returns an `EvidencePack` instance
  directly, not a dict). Returning the `ScoredAccount` instance directly is the established, single-path
  pattern; calling `.model_dump()` manually would be a second, redundant serialization path that D-01
  explicitly says not to introduce.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress notification transport | A custom SSE/log-based progress channel | `Context.report_progress` / `Context.info` | Already ships in the SDK, already handles the "no progressToken -> no-op" case correctly, already used nowhere else in this codebase so there is no existing pattern to diverge from |
| Structured tool output serialization | Hand-written `json.dumps(scored_account_dict)` | Return the `ScoredAccount` Pydantic instance directly from the tool function | FastMCP's `structured_output` auto-detection already does this correctly for `EvidencePack` today; a hand-rolled path would be a second serializer, explicitly barred by D-01 |
| Resource content negotiation | Custom URI routing / manual JSON-RPC resource handlers | `@server.resource("icp://rubric", mime_type=...)` | The decorator handles URI registration, listing (`resources/list`), and reads (`resources/read`) end to end |

**Key insight:** every piece of infrastructure this phase needs (progress, resources, prompts, structured
tool output) already exists in the installed SDK and has at least one proven-working precedent in this
codebase (`get_account_evidence`) or in the SDK's own docstring examples. The only genuinely new design
surface is the lifespan composition question (Pattern 1), which is a wiring decision, not a hand-roll risk.

## Common Pitfalls

### Pitfall 1: `settings=None` silently disables full-tier registration on stdio
**What goes wrong:** `__main__.py` currently calls `build_server(lifespan=..., settings=settings if
args.transport == "http" else None)`. If tier-conditional registration is implemented by checking
`if settings is not None and settings.mcp_tier() == "full"`, a full-keys BYOK user running `make mcp`
(stdio) would never see `research_account_full`, because `settings` is `None` on that path by design.
**Why it happens:** the existing `settings` parameter conflates two unrelated concerns: "should I pass
HTTP-transport kwargs to the FastMCP constructor" and "what tier is this server." Phase 12 needs the second
concern independent of the first.
**How to avoid:** add an explicit `tier: Literal["thin", "full"] = "thin"` parameter to `build_server`,
resolved once in `__main__.py` via the existing `resolve_and_log_tier(settings)` call (already happens
before `build_server` is invoked) and passed through regardless of transport.
**Warning signs:** a test that calls `build_server(lifespan=full_lifespan, settings=None)` (stdio-style) and
expects `research_account_full` in `list_tools()` — if it fails, this pitfall has been reintroduced.

### Pitfall 2: mypy strict breaks on `get_account_evidence`'s `Context` type parameter
**What goes wrong:** `get_account_evidence` is currently annotated `Context[ServerSession, ThinDeps,
Request]`. Registering the same function object against a full-tier lifespan whose context type is `Deps`
(or any other non-`ThinDeps` type) type-checks fine at runtime (Python doesn't enforce generic parameters)
but fails mypy strict, because the function's declared parameter type doesn't match the value it will
actually receive when wired to the full-tier lifespan.
**Why it happens:** `mcp>=1.28`'s `Context` is `Generic[ServerSessionT, LifespanContextT, RequestT]`
[VERIFIED: `mcp/server/fastmcp/server.py:1098`, installed SDK source] — a concrete type parameter locks the
function to exactly one lifespan-context shape unless a shared abstraction is introduced.
**How to avoid:** define a `typing.Protocol` (e.g. `EvidenceDeps`) exposing exactly the attributes
`get_account_evidence` reads (`exa`, `browserbase`, `limiter`), and annotate the function as
`Context[ServerSession, EvidenceDeps, Request]`. Both `ThinDeps` (existing, frozen dataclass) and the
extended `Deps` (Pattern 1) structurally satisfy the protocol without inheriting from it — this is exactly
the codebase's existing `*Like` protocol convention (`ExaLike`, `BrowserbaseLike`), just applied to the
lifespan-context shape instead of a client shape.
**Warning signs:** `mypy src` reporting an incompatible type for `deps` inside `get_account_evidence` or at
its call sites once the full-tier lifespan is wired in.

### Pitfall 3: `run_eval=False` status branch placed in the wrong position
**What goes wrong:** if the new `not run_eval -> clean` branch is placed BEFORE the `hook_suppressed` check
in the precedence `if/elif` chain, an account whose enrichment produced zero usable hooks (empty content)
but with `run_eval=False` would incorrectly read as `clean` instead of `hook_suppressed`, breaking D-03's
"degraded stages mirror the sheet exactly" rule and D-02's own scope (D-02 only governs the eval-skip
signal, not hook suppression).
**Why it happens:** the two rules interact — hook suppression must be evaluated independent of whether the
judge ran, since it is about content delivery, not evaluation.
**How to avoid:** order matters: `judge_failed` (from a real crash) first among the "something is wrong"
checks -> `hook_suppressed` next -> `not run_eval -> clean` third -> `eval_score is None -> judge_failed`
(the crash case, now unambiguous because the skip case was already handled) -> `is_flagged` -> `clean`.
See Pattern 3's ordered example.
**Warning signs:** a test asserting `run_eval=False` + empty hooks -> `hook_suppressed` (not `clean`) is the
canary; write it explicitly.

### Pitfall 4: full-tier `research_account_full` accidentally callable in demo mode
**What goes wrong:** `MCP_DEMO_MODE=1` must force thin tier and hide the full tool even when full BYOK keys
are present in the environment (roadmap success criterion 2, explicitly requires a test).
**Why it happens:** `Settings.mcp_tier()` already handles this correctly today (checked `mcp_demo_mode`
before the key-presence branch, per `src/config.py:213-219`, confirmed this session) — the risk is entirely
in the registration wiring NOT re-deriving tier independently (e.g. checking key presence directly instead
of calling `settings.mcp_tier()`), which would bypass the existing, already-tested demo-mode override.
**How to avoid:** the tier passed to `build_server` must always originate from `settings.mcp_tier()` (or the
already-existing `resolve_and_log_tier(settings)` wrapper), never from an independent key-presence check in
`__main__.py` or `server.py`.
**Warning signs:** a test setting `mcp_demo_mode=True` with all four full-tier keys present, then asserting
`research_account_full` is absent from `list_tools()` — this is roadmap criterion 2 and must be a functional
test, not just a unit test of `mcp_tier()` (which Phase 10 already covers).

### Pitfall 5: resource MIME type omission defaults to `text/plain`, breaking client-side syntax highlighting
**What goes wrong:** omitting `mime_type` on `@server.resource(...)` leaves clients unable to
distinguish YAML from Markdown from plain text, degrading the "read the rubric" UX the phase is building
toward.
**Why it happens:** `mime_type` is an optional kwarg on `FastMCP.resource()` with no inferred default from
content [VERIFIED: `mcp/server/fastmcp/server.py:534-544`, installed SDK source].
**How to avoid:** pass `mime_type="application/yaml"` for `icp://rubric` (the IANA-registered YAML media
type per RFC 9512, effective Feb 2024) [CITED: RFC 9512, https://www.rfc-editor.org/rfc/rfc9512] and
`mime_type="text/markdown"` for `icp://eval-report` (IANA-registered per RFC 7763).

## Code Examples

Verified patterns from the installed SDK and this codebase's own precedent (all read directly this
session, not from training data):

### Registering a tool programmatically (existing pattern, reused for the full tool)
```python
# Source: src/mcp_server/server.py:148-150 (existing code, this codebase)
server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
    get_account_evidence
)
```

### Resource decorator signature
```python
# Source: mcp/server/fastmcp/server.py:534-545 (installed mcp==1.28.1)
def resource(
    self,
    uri: str,
    *,
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    mime_type: str | None = None,
    icons: list[Icon] | None = None,
    annotations: Annotations | None = None,
    meta: dict[str, Any] | None = None,
) -> Callable[[AnyFunction], AnyFunction]: ...
```

### Prompt decorator: a plain `str` return becomes one `UserMessage`
```python
# Source: mcp/server/fastmcp/prompts/base.py:161-174 (installed mcp==1.28.1)
if not isinstance(result, list | tuple):
    result = [result]
for msg in result:
    if isinstance(msg, str):
        content = TextContent(type="text", text=msg)
        messages.append(UserMessage(content=content))
```
This means `research_account(domain: str) -> str` is sufficient; no need to construct `Message`/
`UserMessage` objects by hand for a single-turn static prompt.

### `report_progress` no-ops without a client-attached progress token
```python
# Source: mcp/server/fastmcp/server.py:1162-1180 (installed mcp==1.28.1)
async def report_progress(self, progress: float, total: float | None = None, message: str | None = None) -> None:
    progress_token = self.request_context.meta.progressToken if self.request_context.meta else None
    if progress_token is None:
        return
    await self.request_context.session.send_progress_notification(...)
```

### Tool-call error dispatch (confirms the existing `raise ValueError(...)` pattern is correct for the new tool too)
```python
# Source: mcp/server/lowlevel/server.py:589-590 (installed mcp==1.28.1)
except Exception as e:
    return self._make_error_result(str(e))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — this is the first phase to add resources/prompts to this server | Tools, resources, and prompts registered on one `FastMCP` instance, gated per-tier at registration time | This phase | No mid-lifecycle SDK changes affect this work; `mcp==1.28.1` is current and the pin (`<2.0`) has headroom |

**Deprecated/outdated:** None identified. The MCP Python SDK's `FastMCP` resource/prompt/progress APIs used
here are the current, documented surface as of the installed `1.28.1` (no legacy/experimental flags
involved).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `application/yaml` is the "correct" MIME type to use for `icp://rubric` (vs. the also-common but unregistered `text/yaml`) | Common Pitfalls (Pitfall 5), Architecture Patterns (Pattern 2) | Low — this is Claude's Discretion per CONTEXT.md ("Resource MIME types... suggested"); either value works functionally, this is purely a correctness-of-labeling recommendation backed by an IANA RFC, not a locked decision |
| A2 | Extending `Deps` with `exa`/`browserbase`/`limiter` fields is lower-risk than an independent second client stack, based on a full-codebase grep finding exactly one `Deps(...)` construction site | Architecture Patterns (Pattern 1), Summary | Medium — if a `Deps(...)` construction site exists that this grep missed (e.g. added by a very recent uncommitted change), the "safe additive field" claim would need re-verification; the audit command (`grep -rn "Deps(" src tests evals`) is cheap to re-run at plan time |

**If this table is empty:** N/A — two low/medium-risk labeling and audit-scope assumptions are logged above; both are within Claude's Discretion per CONTEXT.md and do not require a user checkpoint before planning proceeds.

## Open Questions (RESOLVED)

1. **Exact progress-callback signature and stage-name strings (D-05, Claude's Discretion)**
   - What we know: `on_stage` must be additive (default `None`), async-compatible, and called at each of
     the five stage boundaries the design spec names (enrich, score, personas/contacts, outreach, eval).
   - What's unclear: whether `on_stage` should receive just a stage-name string, or a richer payload (e.g.
     `(stage: str, index: int, total: int)`) so the MCP wrapper doesn't have to recompute the index itself.
   - Recommendation: keep it to a single `str` stage name (Pattern 4's example) — the MCP wrapper closure
     already knows the total stage count from `run_eval`, so a richer payload would just move state the
     wrapper already has back into the pipeline layer, which should stay MCP-agnostic per the "dependency
     arrow stays one-directional" constraint in CONTEXT.md's code_context section.
   - RESOLVED: locked as recommended by Plan 12-01 Task 1 — `on_stage: Callable[[str], Awaitable[None]]
     | None = None` receiving a single plain stage-name string, exactly `"enrich"`, `"score"`,
     `"contacts"`, `"outreach"`, `"eval"`. The MCP wrapper closure computes index/total itself from
     `run_eval` (Plan 12-03 Task 2); the pipeline layer stays MCP-agnostic.

2. **Whether `on_stage` failures should be caught inside `process_account`**
   - What we know: a disconnected MCP client mid-call could make `ctx.report_progress`/`ctx.info` raise.
   - What's unclear: whether that should abort the account (arguably correct — the client is gone) or be
     swallowed so a flaky progress channel never breaks a working pipeline run.
   - Recommendation: do not add a try/except around `on_stage` calls inside `process_account` — if the
     client disconnected, the underlying MCP session/task will already be torn down and the exception
     propagating is the correct, honest behavior; adding a swallow here would be unlocked, unrequested
     scope.
   - RESOLVED: locked as recommended by Plan 12-01 Task 1 — no try/except around `on_stage` inside
     `process_account`; a raise propagates (honest teardown of the MCP session). Accepted as T-12-03
     (low, DoS) in Plan 12-01's threat register; the CLI path never passes a callback so `make run`
     is unaffected.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` SDK | Tool/resource/prompt registration | Yes | 1.28.1 (matches pin) | — |
| `EXA_API_KEY` | Live full-tier smoke extension only (functional tests use stub `ExaLike`/`BrowserbaseLike`/`LLMClient`) | Unknown (operator-local `.env`, not inspectable from this sandbox) | — | Functional/in-memory tests (the majority of this phase's test surface) never touch live keys; only an opt-in smoke test would need them, and that is out of this phase's locked scope per Phase 10's `make smoke-mcp` precedent |
| `DEEPSEEK_API_KEY` / `NVIDIA_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` | Live full-tier tool exercised end-to-end (not required for this phase's committed test suite) | Unknown (operator-local) | — | Same as above; `open_deps`'s replay-mode fixtures (`DEMO_BUNDLE`) are the existing, already-tested fallback path for exercising full-tier code without live keys, per Phase 9 |

**Missing dependencies with no fallback:** None — this phase's required test coverage (functional,
in-memory, stub-based, matching the existing `tests/functional/test_mcp_server.py` pattern) has zero live
external dependency.

**Missing dependencies with fallback:** Live BYOK keys for an optional smoke-level exercise of
`research_account_full` — fallback is the existing replay/record fixture infrastructure (`DEMO_BUNDLE`),
already proven in `tests/functional/test_pipeline_open_deps.py` and `tests/functional/test_replay_pipeline.py`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+, `pytest-asyncio` (auto mode), `pytest-cov` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/functional/test_mcp_server.py -x` |
| Full suite command | `make test` (offline; `smoke` marker excluded by default per `Makefile`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-05 (criterion 1) | BYOK caller gets full `ScoredAccount` JSON incl. `AccountStatus` from `research_account_full` | functional | `uv run pytest tests/functional/test_mcp_server.py -k full_tool -x` | ❌ Wave 0 — extend `tests/functional/test_mcp_server.py` with a full-tier lifespan fixture using stub `Deps` |
| MCP-05 (criterion 2) | `MCP_DEMO_MODE=1` forces thin tier and hides `research_account_full` even with full keys present | functional | `uv run pytest tests/functional/test_mcp_server.py -k demo_hides_full_tool -x` | ❌ Wave 0 — new test, this is roadmap success criterion 2 explicitly |
| MCP-02 | Client reads `configs/icp.yaml` via `icp://rubric` | functional | `uv run pytest tests/functional/test_mcp_server.py -k rubric_resource -x` | ❌ Wave 0 |
| MCP-03 | Client reads `evals/REPORT.md` via `icp://eval-report` | functional | `uv run pytest tests/functional/test_mcp_server.py -k eval_report_resource -x` | ❌ Wave 0 |
| MCP-04 | `research_account` prompt guides `[N]`-cited, rubric-based scoring and drops unciteable claims | functional | `uv run pytest tests/functional/test_mcp_server.py -k research_account_prompt -x` | ❌ Wave 0 — assert prompt text mentions `icp://rubric`, `get_account_evidence`, and the `[N]`/drop-uncited rule (mirrors the existing `test_annotations_and_description_over_the_wire` assertion style on `get_account_evidence`'s own docstring) |
| D-02 (run_eval honesty, cross-cutting) | `run_eval=False` never yields `judge_failed`; hooks-empty still yields `hook_suppressed` regardless of `run_eval` | unit/functional | `uv run pytest tests/unit/test_pipeline_status.py -x` (new file, or extend `tests/integration/test_pipeline.py`'s status-precedence coverage) | ❌ Wave 0 |
| D-04/D-05 (progress) | `on_stage` callback invoked at each stage boundary; default `None` leaves existing pipeline tests untouched | unit | existing `tests/integration/test_pipeline_failures.py` and `tests/integration/test_pipeline.py` re-run unmodified (regression proof) plus one new assertion collecting callback invocations | ❌ Wave 0 for the new assertion; ✅ existing files are the regression gate |
| D-08 (resource error sanitization) | Missing/unreadable resource file returns sanitized text, not a raised protocol error | unit | `uv run pytest tests/unit/test_mcp_resources.py -x` (new file, monkeypatch `Path.read_text` to raise `OSError`) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/functional/test_mcp_server.py -x` (fast, in-memory, no subprocess)
- **Per wave merge:** `make test` (full offline suite; strict mypy via `make typecheck`)
- **Phase gate:** `make test && make typecheck && make lint` green before `/gsd-verify-work`, matching the
  precedent set by every prior MCP phase (10/11) per `.planning/STATE.md`.

### Wave 0 Gaps
- [ ] Extend `tests/functional/test_mcp_server.py` with a full-tier lifespan test fixture: a stub `Deps`
  bundle (fake enricher/scorer/contacts/outreach/eval_rubric matching the existing pipeline test fakes in
  `tests/integration/test_pipeline_failures.py`) wrapped in a `_full_lifespan_factory`, mirroring the
  existing `_lifespan_factory` for `ThinDeps`.
- [ ] `tests/unit/test_pipeline_status.py` (new) — covers D-02's status-precedence ordering, specifically
  the `run_eval=False` + empty-hooks -> `hook_suppressed` (not `clean`) canary from Pitfall 3.
- [ ] `tests/unit/test_mcp_resources.py` (new) — covers D-08's sanitized-message-on-read-failure behavior
  for both `icp://rubric` and `icp://eval-report`, independent of the FastMCP dispatch layer (call the
  resource functions directly, not through a client session, so the test isolates the sanitization logic
  from SDK error-wrapping behavior).
- [ ] Framework install: none — pytest/pytest-asyncio already configured.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Server remains unauthenticated (locked, HOST/MCP-07 scope; no change this phase) |
| V3 Session Management | No | `stateless_http=True` already locked (Phase 11 D-locked); no session state introduced by resources/prompts |
| V4 Access Control | Yes | Tier-gated tool registration IS the access-control mechanism for `research_account_full` — enforced entirely server-side at registration time (the tool is absent from `list_tools()`, not merely refused at call time), which is the correct pattern per MCP-06's "hidden, not visible-but-refusing" requirement (CONTEXT.md, locked) |
| V5 Input Validation | Yes | `research_account_full`'s `domain` argument validated through the same `Account` normalizer as `get_account_evidence` (locked, reused verbatim) |
| V6 Cryptography | No | Not touched this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path/error-message leakage via resource read failures | Information Disclosure | Catch `OSError` inside the resource function and return a sanitized placeholder string (Pattern 5); never let the SDK's own `ResourceError(str(e))` re-raise carry the real filesystem path to the client |
| Full tool reachable when demo-mode env misconfigured (e.g. keys accidentally present on the hosted demo instance) | Elevation of Privilege | `Settings.mcp_tier()` checks `mcp_demo_mode` before any key-presence branch (already true, verified this session); the plan must ensure `build_server`'s `tier` argument is *always* derived from `settings.mcp_tier()`, never re-derived independently (Pitfall 4) |
| Stack-trace/env-name leakage in tool error payloads | Information Disclosure | Already covered by HOST-05 discipline (locked, Phase 10 precedent) and reused verbatim for `research_account_full`'s error path — no new sanitization logic needed, just apply the existing `except (...) as exc: raise ValueError(sanitized) from None` pattern |
| Long-running tool call (30-60s) as a resource-exhaustion vector | Denial of Service | Out of this phase's scope by design — `research_account_full` is gated to BYOK/full-tier only, which per MCP-06 is never reachable in demo mode; the hosted demo (Phase 13) never exposes this tool at all |

## Sources

### Primary (HIGH confidence)
- Installed `mcp==1.28.1` SDK source, read directly this session:
  `.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py` (tool/resource/prompt decorators,
  `Context.report_progress`/`read_resource`), `.venv/lib/python3.12/site-packages/mcp/server/fastmcp/prompts/base.py`
  (prompt rendering, str-to-Message coercion), `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py`
  (tool-call error dispatch confirming `except Exception -> _make_error_result(str(e))`)
- This codebase's own source, read directly this session: `src/pipeline.py`, `src/mcp_server/server.py`,
  `src/mcp_server/wiring.py`, `src/mcp_server/evidence.py`, `src/mcp_server/__main__.py`, `src/config.py`,
  `src/models.py`, `src/icp_config.py`, `tests/functional/test_mcp_server.py`, `tests/smoke/test_mcp_e2e.py`
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md` §"Tool, resource, and prompt surface"
  (design authority for this phase)
- `.planning/phases/12-full-tier-tool-resources-prompt/12-CONTEXT.md` (locked decisions D-01 through D-11)

### Secondary (MEDIUM confidence)
- RFC 9512 (YAML media type registration) via WebSearch, cross-referenced against the IANA media-types
  registry listing (`https://www.iana.org/assignments/media-types/application/yaml`) returned in the same
  search — used only for the Claude's-Discretion MIME-type recommendation (Pitfall 5, Assumption A1)

### Tertiary (LOW confidence)
- None. All claims in this document trace either to direct source-code inspection of the installed SDK and
  this codebase, or to a cross-referenced IANA/RFC citation for the one cosmetic MIME-type recommendation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing pin already installed and verified via `uv pip show`
- Architecture: HIGH for the registration/error-handling patterns (directly read from installed SDK source
  and existing codebase precedent); MEDIUM for the specific `Deps`-extension lifespan-composition
  recommendation (Pattern 1) since it is a genuinely new design decision this research is making, not one
  it is merely confirming against an existing precedent — flagged in the Assumptions Log (A2)
- Pitfalls: HIGH — all five pitfalls trace to either a direct code-reading finding (Pitfalls 1, 2, 4, 5) or
  a locked CONTEXT.md decision interaction this research worked through explicitly (Pitfall 3)

**Research date:** 2026-07-17
**Valid until:** 30 days (stable SDK surface, `mcp<2.0` pin has headroom; re-verify if `mcp` is bumped past
1.28.x before this phase plans)
