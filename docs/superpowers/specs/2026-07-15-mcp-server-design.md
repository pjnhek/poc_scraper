# MCP Server Design: Grounded Account Research over MCP

**Date:** 2026-07-15
**Status:** Approved design, pending implementation planning

## Goal

Expose the existing grounded account-research pipeline as an MCP server so any MCP client (Claude Desktop, Claude Code, Codex, Cursor) can use it. Primary motivations: hands-on experience building MCP servers, and a public, connectable portfolio artifact ("paste this URL into Claude Desktop and research an account with cited evidence").

## Decisions already made

| Decision | Choice | Rationale |
|---|---|---|
| Consumer | Public, URL-connectable, plus local stdio for cloned-repo users | Portfolio value; matches personal-site MCP servers the user wants to emulate |
| Economics | Hosted demo runs on the operator's Exa key with hard caps; full pipeline is BYOK local | Claude credits can pay for the caller's reasoning (thin tier) but can never pay for Exa retrieval; operator has $14.20 in unbilled Exa credits, so worst case is exhaustion, not a bill |
| Approach | One tiered server, two transports (Approach 1) | Single codebase teaches tools, resources, prompts, and both transports; hosted safety by construction |
| Scope boundary | Read-only server; no Sheets writes, no batch tool, no rubric editing | Zero blast radius on the public surface; config changes stay human-reviewed |

## Architecture

New package wrapping existing seams; no pipeline behavior changes.

```
src/mcp_server/
  __init__.py
  server.py        # FastMCP app: tool/resource/prompt registration, capability tiering
  wiring.py        # server lifespan management, uses pipeline.open_deps
  evidence.py      # thin tier: collect_context + _number_justifications -> EvidencePack
  limits.py        # demo mode: per-IP rate limit, global daily budget (in-memory)
```

### Capability tiering (resolved once at startup)

- `EXA_API_KEY` present: register the thin tier (evidence tool, rubric resource, eval-report resource, research prompt).
- Writer/judge keys (DeepSeek or NVIDIA) plus Browserbase keys also present: additionally register the full-pipeline tool.
- `MCP_DEMO_MODE=1` forces thin tier only, regardless of keys present, and enables `limits.py`. The hosted deployment always sets this flag, so expensive tools do not exist on the public URL even if keys are misconfigured onto it.

### Transports

`python -m src.mcp_server` defaults to stdio (local client config). `--transport http --port <n>` serves streamable HTTP for the hosted URL. Both come from the same registered FastMCP app.

### Deployment

Dockerfile running the HTTP transport with `MCP_DEMO_MODE=1` and the Exa key as a platform secret. Target platform: Fly.io (Railway is the fallback if Fly friction appears). Users connect via the URL directly (clients with native remote support) or `npx mcp-remote <url>` (stdio-only clients).

### Charter amendment

This milestone adds the `mcp` Python SDK dependency and a new output surface. CLAUDE.md is amended in the same milestone: stack section gains the `mcp` SDK; the out-of-scope list keeps webapp/dashboard/Slack but notes the MCP server is now in scope. Sheets output is unchanged.

## Tool, resource, and prompt surface

### Thin tier (always registered)

**Tool `get_account_evidence(domain: str)`**
- Domain validated through the existing `Account` normalizer.
- Runs retrieval only (`collect_context`, Exa about + last-90-day news, Browserbase fallback when a key exists) then `_number_justifications`.
- Returns a new frozen `EvidencePack` model as JSON: numbered justifications (index, text, url, source, retrieved_at), cleaned about text, news items, and `retrieval_status: "ok" | "thin" | "empty"` so callers know when evidence is too weak to score. This is the MCP analogue of the `unscoreable` honesty rule.

**Resource `icp://rubric`**: serves `configs/icp.yaml` verbatim.

**Resource `icp://eval-report`**: serves `evals/REPORT.md` (calibration narrative).

**Prompt `research_account(domain)`**: instructs the calling agent to load the rubric resource, call `get_account_evidence`, score each axis 1-5 with the stated weights, propose top-3 personas, and draft outreach where every claim carries an `[N]` marker corresponding to a justification index, dropping unciteable claims. Thin tier is grounding by instruction; full tier is grounding by construction. Document that contrast in the README.

### Full tier (BYOK, gated, never in demo mode)

**Tool `research_account_full(domain: str, run_eval: bool = true)`**
- Runs the existing `process_account` unchanged (enrich, score, personas, grounded hooks with validated citations, judge eval, four-state `AccountStatus`).
- `run_eval=false` skips the judge for roughly half the latency.
- Returns `ScoredAccount` via `model_dump()`. Tool description warns of 30-60s runtime.

### Deliberately excluded

Batch/CSV tool (agents can loop; batch invites timeouts), Sheets-writing tool (server stays read-only), rubric-editing tool (config changes stay reviewed).

## Hosted demo safety rails (`MCP_DEMO_MODE=1`)

Cost basis: one evidence call is 2 Exa searches ($7 per 1k requests) plus roughly 10 content pages ($1 per 1k pages), about $0.025 per call, less with the results clamp. The $14.20 credit pool buys roughly 550-600 calls total. No billing account is attached, so exhaustion stops service rather than incurring charges.

1. **Per-IP rate limit:** 5 evidence calls per hour (env `MCP_DEMO_IP_LIMIT`). Client IP from `X-Forwarded-For`. If the header is absent, fail closed into one shared bucket.
2. **Global daily cap:** 25 calls per UTC day (env `MCP_DEMO_DAILY_CAP`), about $0.60 per day maximum burn, so the pool survives 3+ weeks of sustained maximum abuse and months of hobby traffic.
3. **Demo scope clamps:** Exa limited to 5 results per search (env `MCP_DEMO_EXA_RESULTS`), Browserbase always `NullBrowserbase`, one domain per call.

Limit hits return structured MCP tool errors ("rate limit reached, resets at HH:MM UTC", "demo budget spent for today"), not transport failures, so the caller's agent relays a polite message. Exa credit exhaustion (402/429 after retries) degrades to the same rationing error, so the public URL looks rationed, never broken.

State is in-memory (counters plus timestamps). Restart resets counters; acceptable for a demo and keeps the milestone free of external storage. Revisit only if real traffic appears.

Error payloads never include stack traces, env names, or key fragments.

## Config and wiring changes to existing code

All additive; four files touched.

- **`src/config.py`**: new defaulted `Settings` fields `mcp_demo_mode: bool = False`, `mcp_demo_ip_limit: int = 5`, `mcp_demo_daily_cap: int = 25`, `mcp_demo_exa_results: int = 5`, `mcp_http_port: int = 8000`. New method `mcp_tier() -> Literal["thin", "full"]` mirroring `require_for_pipeline()`: thin needs `EXA_API_KEY` only; full also needs writer/judge and Browserbase keys. `require_for_pipeline()` unchanged.
- **`src/pipeline.py`**: extract the client-construction block from `main()` into an async context manager `open_deps(settings)` living next to `build_deps`. Both `main()` and the MCP server use it. Behavior identical; existing tests unaffected.
- **`src/clients/`**: add `NullBrowserbase` satisfying `BrowserbaseLike`; its fetch raises `BrowserbaseError("browserbase disabled")`, which `collect_context` already catches on the log-and-continue path.
- **`src/enrich.py`**: promote `_collect_context` to public `collect_context()` with a docstring; `_number_justifications` is already importable at module level.
- **`src/models.py`**: add frozen `EvidencePack` with `extra="forbid"`, tuple collections, matching existing conventions.
- **`pyproject.toml`**: add `mcp>=1.0` (official Python SDK; FastMCP included). No new dev dependencies.
- **`Makefile`**: `make mcp` (stdio), `make mcp-http` (local HTTP), `make mcp-demo` (HTTP with demo mode; what the Dockerfile runs).

## Error handling

- **Invalid domain:** `Account` `ValidationError` caught at the tool wrapper, returned as an MCP tool error with the validator message.
- **Empty or thin retrieval:** not an error; `EvidencePack.retrieval_status` communicates it in a successful result.
- **Provider failures** (Exa 429/5xx after tenacity retries): typed "retrieval unavailable, try again" tool error. The full-tier tool inherits `process_account` per-stage isolation, so a judge failure still returns a successful result whose `AccountStatus` is `judge_failed`, exactly like the sheet.
- **Limits:** structured rationing errors as above.
- Logging follows existing conventions: WARNING for recoverable failures, truncate untrusted strings, `%` placeholders.

## Testing (maps to the 5-layer strategy)

1. **Unit:** `limits.py` window math with an injected clock (reset, cap boundary, UTC day rollover); `EvidencePack` construction from crafted contexts including empty and thin; `mcp_tier()` across key combinations.
2. **Functional:** FastMCP in-memory client connected directly to the server object (no subprocess, no network) with `FakeExa` and `NullBrowserbase` stubs; assert evidence JSON, that demo mode registers no full-tier tool, and that missing keys fail fast at startup with the listing message.
3. **Integration:** thin tier through tool plus prompt plus rubric resource with stubbed Exa; full tier with stubbed deps asserting `ScoredAccount` survives `model_dump` to JSON round-trip.
4. **Smoke (opt-in, `make smoke-mcp`):** stdio server as a real subprocess, one live Exa call against a fixture domain, assert numbered non-empty justifications. Skipped in CI.
5. **Edge cases:** cap exhausted mid-session, missing `X-Forwarded-For` (fail closed), malformed domain, simulated Exa credit exhaustion.

Strict mypy throughout; the MCP SDK ships types, so no new `ignore_missing_imports` entries.

## Out of scope for this milestone

- Sales-workflow features (review queue, CRM, Slack, persistence) per the earlier v2 review.
- PyPI packaging and `uvx` distribution (possible follow-up once the tool surface stabilizes).
- Auth on the hosted endpoint (rate limits are the only gate; nothing sensitive is reachable).
- Company-name-to-domain resolution (domains only).

## Success criteria

1. A stranger pastes the hosted URL into Claude Desktop (or uses `npx mcp-remote`) and gets cited account evidence with zero setup.
2. A cloned-repo user with full keys runs `make mcp` and gets `research_account_full` in Claude Code with the complete grounded pipeline.
3. Demo caps demonstrably hold: the 26th call of a day is refused politely; the 6th call in an hour from one IP is refused politely.
4. All offline tests pass and strict mypy stays clean.
5. README gains an MCP section including the grounding-by-instruction vs grounding-by-construction contrast.
