# Codebase Concerns

**Analysis Date:** 2026-05-14

Severity legend: **HIGH** = ship-blocker or public-repo / security risk; **MEDIUM** = correctness or maintenance risk; **LOW** = polish, dead code, minor smell.

## Public-repo Leaks

CLAUDE.md is explicit: "This repo is intended to be public. Do not name specific companies, vendors, or verticals in code, prompts, or commit messages. Keep the ICP definition abstract and edit `configs/icp.yaml` for vertical-specific runs." Several places violate that contract.

**HIGH — Real customer-target domains committed to `inputs/accounts.csv`:**
- Files: `inputs/accounts.csv` (10 named consumer brands: mercury.com, ramp.com, faire.com, strava.com, peloton.com, zocdoc.com, calm.com, warbyparker.com, linear.app, retool.com)
- Why it matters: every one of these is a real, identifiable company. Publishing this file together with the seller description ("AI customer-support automation platform") is a *public list of named prospects*. That's a sales artifact, not a fixture.
- Fix approach: replace with synthetic placeholders (e.g. `examplefin.com`, `examplestream.com`) matching the pattern already used in `evals/labeled.jsonl`. Move the real list to a gitignored `inputs/accounts.local.csv` and document that override in the README.

**HIGH — Vertical-specific persona defaults hardcoded:**
- Files: `src/contacts.py:61-66` (`_default_contacts()` returns `VP Customer Experience`, `Head of Support Operations`, `Director of CX Automation`)
- Why it matters: when the LLM call fails or returns unparseable JSON, the pipeline falls back to CX-vertical personas regardless of what `configs/icp.yaml` describes. A user who retargets the YAML at, say, devtools will still see CX roles in the sheet. Also: hardcoding personas in `src/` defeats the "vertical-agnostic code, vertical lives in YAML" design.
- Fix approach: either (a) drop the defaults and emit empty contacts with a clear error in the sheet, or (b) add a `default_personas` block to `configs/icp.yaml` and read it in `_default_contacts()`.

**MEDIUM — Vendor names leaked in code comments and prompts:**
- `src/enrich.py:22` — prompt example `'e.g. ["zendesk","react"]'` names a specific support vendor (Zendesk). Since the seller per `configs/icp.yaml` competes with chat/voice support tooling, naming Zendesk in the firmographics prompt nudges the model toward a competitor framing.
- `src/enrich.py:147` — comment uses Mercury as the canonical example (`"About Mercury | The art of simplified finances"`). Mercury is also in `inputs/accounts.csv`, so a casual reader connects the two.
- `evals/run_live.py:10` — module docstring example: `EVAL_LIVE_DOMAINS=mercury.com,strava.com make eval-live`.
- Fix approach: scrub to generic placeholders (`"e.g. ['support_vendor','frontend_framework']"`, `"About ExampleCo"`, `EVAL_LIVE_DOMAINS=examplefin.com,examplestream.com`).

**LOW — GCP project ID embedded in committed `credentials.json`:**
- File: `credentials.json` (project_id `poc-scraper-495806`)
- Status: file is correctly gitignored (`.gitignore` line 19, `credentials*.json`) and not in git history (`git ls-files credentials.json` returns nothing). Risk is local-only.
- Fix approach: none required as long as `.gitignore` stays intact. Add a pre-commit hook that hard-fails if `credentials*.json` or `.env` appear in the index, since a `git add -A` accident is the realistic failure mode.

## Secrets Handling

**HIGH — `.env` and `credentials.json` correctly gitignored, but no defense-in-depth:**
- `.gitignore:1` ignores `.env`; `.gitignore:18-20` ignores `credentials*.json` and `service-account*.json`. Verified neither file is tracked.
- Gap: nothing prevents an accidental `git add credentials.json` followed by `--force`, and there is no pre-commit secret scanner (`.pre-commit-config.yaml` only runs black/ruff/whitespace fixers).
- Fix approach: add `detect-secrets` or `gitleaks` hook to `.pre-commit-config.yaml`.

**LOW — API keys passed as plain strings through constructors:**
- Files: `src/clients/exa_client.py:33`, `src/clients/browserbase_client.py:39`, `src/clients/nvidia_client.py:80`
- Risk: low (no logging of the keys observed), but `repr()` of these clients would expose the key if anyone ever logs the object. Pydantic's `SecretStr` exists for this.
- Fix approach: optional — `pydantic.SecretStr` on `Settings` fields, `.get_secret_value()` at the client boundary.

## Documented Failure Modes vs Implementation

CLAUDE.md names five first-class failure modes. Walking each one against the code:

**MEDIUM — "Hallucination on a sales claim: every outreach claim must trace to a retrieval":**
- Implemented at `src/outreach.py:71-80`: the writer's claimed indices are cross-checked against `[N]` markers actually present in the paragraph, and the hook is dropped if no valid markers remain. Good.
- Gap: the *judge* in `evals/rubric.py` decomposes claims and marks them supported/uncited, but the writer-side guard only requires *at least one* valid marker. A 4-claim paragraph with 1 cited and 3 fabricated still ships to the sheet; only the judge's groundedness score flags it later, and that flag is just red text on one cell, not a row-level drop.
- Fix approach: either (a) raise the writer-side bar (require markers covering N% of sentences), or (b) make the judge's groundedness-below-threshold gate actually suppress the hook text in the sheet instead of just coloring the eval cell. README.md:48 explicitly preserves the verdict color, which is by design, but it does mean a hallucinated hook still appears in the cell.

**MEDIUM — "Scraping blocked: Browserbase retries once; if still blocked, log and continue":**
- Implemented at `src/clients/browserbase_client.py:62-67` (`stop_after_attempt(2)` = one retry) and `:54-59` (catch-all returns `None`). Good.
- Gap: `stop_after_attempt(2)` means exactly 2 attempts total = 1 retry, which matches the doc, but the retry only fires on `httpx.HTTPError`. A `BrowserbaseError` ("empty rendered content") raised at line 81 is not retried — first empty render bubbles. Probably intentional, but worth documenting.

**LOW — "Empty enrichment: mark the account `unscoreable`":**
- Implemented at `src/pipeline.py:66-67` and `src/enrich.py:47-48` (returns `Enrichment` with no news, no firmographics) and `src/models.py:95-97` (`is_empty` property). Good. `tests/integration/test_pipeline_failures.py:55-66` covers the score-failure path but not the empty-enrichment path explicitly.
- Fix approach: add a test that wires `FakeExa(about=[], news=[])` and asserts `status == "unscoreable"` with error `"empty enrichment"`.

**MEDIUM — "Rate limits: asyncio + httpx, concurrency cap of 5, exponential backoff on 429s via tenacity":**
- Concurrency cap honored at `src/pipeline.py:123` and `src/clients/nvidia_client.py:86` (`asyncio.Semaphore(max_in_flight)`).
- Backoff at `src/clients/nvidia_client.py:115-120`: retries on `RateLimitError, APIStatusError, APIError`, 6 attempts, `wait_random_exponential(multiplier=4, max=60)`. Good.
- Gap: `src/clients/exa_client.py:71-76` retries only on `httpx.HTTPError`, *not* specifically on 429s with their `Retry-After` header. Exa 429s arrive as `httpx.HTTPStatusError` (a subclass of `httpx.HTTPError`) so they *are* retried, but the backoff is fixed exponential, ignoring server-supplied `Retry-After`. Same for `src/clients/browserbase_client.py:62-67`.
- Fix approach: parse `Retry-After` when present; otherwise current behavior is acceptable.

**LOW — "Sub-threshold eval: groundedness below the configured threshold flags the row red":**
- Implemented at `src/sheets.py:431-471` and `src/models.py:140-142`. Good.
- Note: as flagged above, the hook text still appears; only the `eval_groundedness` cell is recolored. This is documented behavior in README.md:48, so categorizing as low.

## Error Handling Gaps

**MEDIUM — Broad `except Exception` at every pipeline stage:**
- Files: `src/pipeline.py:60, 71, 79, 86, 103`
- Each stage swallows any exception, logs a warning, and continues. Good for resilience, bad for debuggability: a real bug in our code (e.g. a `KeyError` from a refactor) looks identical to a real network failure. No structured error type, no metric for "swallowed exceptions per run."
- Fix approach: narrow to `(httpx.HTTPError, APIError, BrowserbaseError, json.JSONDecodeError, ValidationError)` and let everything else propagate, OR keep the broad catch but log with `exc_info=True` and tag the row's `error` field with the exception class name.

**MEDIUM — `_floor()` returns groundedness=1 on judge failure:**
- File: `evals/rubric.py:106-113`
- An unparseable judge response is indistinguishable from a fully-hallucinated hook (both score 1.0). The sheet flags the row red as if the writer failed, even though the writer might have been fine.
- Fix approach: introduce a sentinel (e.g. `groundedness=None` plus a separate `eval_failed: bool` field on `EvalScore`) so the sheet can distinguish "judge couldn't score this" from "writer fabricated claims."

**LOW — `_create_empty_spreadsheet` returns an arbitrary spreadsheet, no error if creds lack permission:**
- File: `src/sheets.py:350-356`
- If the service account can create sheets but cannot share them, the user gets a URL they can't open. No detection.
- Fix approach: after creation, attempt a read; if 403, surface the permission gap in the log.

**LOW — `compute_total()` blows up if `configs/icp.yaml` axis names change:**
- File: `src/score.py:104-109` — uses hardcoded keys `support_volume`, `ai_maturity`, `stage_fit`, `channel_breadth`.
- Why fragile: the rest of the system (prompts, rubric tab) is generated from `cfg.axes`, but the math hardcodes the four current axis names. Adding a fifth axis or renaming one silently produces wrong scores (the new axis gets weight in the rubric tab but isn't summed).
- Fix approach: rewrite as `sum(getattr(breakdown, name) * axis.weight for name, axis in cfg.axes.items())` plus a startup-time check that `RubricBreakdown.model_fields` matches `cfg.axes.keys()`.

## Tech Debt

**LOW — Dead code:**
- `src/score.py:159-160` — `_format_news()` is defined but called nowhere (grep across repo). Likely leftover from refactor.
- Fix approach: delete.

**LOW — `NvidiaClient` is mis-named:**
- File: `src/clients/nvidia_client.py:55-58`
- Class docstring acknowledges: "Despite the name, works for any provider that speaks the OpenAI chat-completions wire format." It's now the default DeepSeek client too. The filename and class name suggest a single-provider client.
- Fix approach: rename to `OpenAICompatClient` in `src/clients/openai_compat_client.py`. Low priority because the rename touches many imports and the docstring already clarifies.

**LOW — Justifications truncated to first 10 silently:**
- Files: `src/score.py:138`, `src/outreach.py:133` — both slice `enrichment.justifications[:10]`.
- Risk: if Exa returns 8 about-page citations and 8 news items (16 total), justifications 11-16 are never shown to the writer, but a downstream consumer of the model might assume "all retrievals were visible." Also: the `Justification.index` field is 1-based and assigned in retrieval order, so the writer is biased toward citing about-page entries.
- Fix approach: either lift the cap or document it explicitly in the prompt.

**LOW — `_strip_html` is regex-based:**
- File: `src/enrich.py:214-216`
- `HTML_TAG = re.compile(r"<[^>]+>")` will mishandle nested angle brackets, `<script>` content, and HTML entities (`&amp;` stays as-is). For about-page text destined for an LLM, this is mostly fine, but it's the kind of code that produces "why does the firmographic name include &nbsp;?" tickets.
- Fix approach: optional — `selectolax` or `BeautifulSoup(..., "html.parser").get_text()` for the rendered-HTML path only. Exa snippets are already plain text.

**LOW — `Settings.resolved_provider` does silent fallback:**
- File: `src/config.py:84-89`
- If `LLM_PROVIDER` is unset and `DEEPSEEK_API_KEY` is empty but `NVIDIA_API_KEY` is also empty, `resolved_provider` returns `"nvidia"` and the failure surfaces later in `require_for_pipeline()`. Fine, but the error message says "missing NVIDIA_API_KEY" which can confuse a DeepSeek user who just forgot to set their key.
- Fix approach: in `require_for_pipeline`, if both keys are empty, raise a different error: `"set either DEEPSEEK_API_KEY or NVIDIA_API_KEY"`.

## Fragile Areas

**MEDIUM — JSON parsing of LLM output:**
- File: `src/_json_utils.py:25-55`
- Strategy is "find first `{` and last `}`, try to parse." Works in practice because all writer prompts say "Output ONLY one JSON object." Breaks if the writer wraps JSON in narrative containing braces (e.g. "Here's the JSON: { ... } -- note that I used a {placeholder}").
- Mitigation: DeepSeek path uses `response_format={"type":"json_object"}` (`src/pipeline.py:151, 177`), which removes the failure mode there. NVIDIA path has no such guarantee.
- Fix approach: the current code already returns `None` cleanly on parse failure, and every caller (`score.py:64-66`, `outreach.py:63-65`, `contacts.py:42-44`, `rubric.py:70-72`, `enrich.py:108-110`) handles `None`. The fragility is acceptable for an NVIDIA fallback that the README labels "unreliable for live demos."

**MEDIUM — Justification index integrity depends on stable iteration order:**
- Files: `src/enrich.py:138-165` builds the numbered list; `src/score.py:91`, `src/outreach.py:68`, `evals/rubric.py:126` all reference the same indices.
- Risk: if any caller re-orders `enrichment.justifications` between writer and judge, every cited index is wrong. Currently all reads use the same `Enrichment` instance, which is frozen, so this is safe. But the invariant is unwritten.
- Fix approach: add a unit test that asserts `j.index == i + 1` for every justification produced by `_number_justifications`, and a docstring on `Justification` (already has one — extend it).

**LOW — Tenacity retry consumes the response object before re-binding:**
- File: `src/clients/exa_client.py:71-86`, `src/clients/browserbase_client.py:62-78`
- Pattern: `async for attempt in AsyncRetrying: with attempt: resp = await ...` then `resp.json()` is called *outside* the loop. If the final attempt raises (e.g. on `reraise=True`), `resp` is unbound. In practice tenacity re-raises the exception so the `data = resp.json()` line is unreachable, but a code reader can't easily see that.
- Fix approach: move `data = resp.json()` *inside* the `with attempt:` block.

## Test Coverage Gaps

**MEDIUM — No test for the "empty enrichment" status:**
- File missing: `tests/integration/test_pipeline_failures.py`
- Existing tests cover score failure and outreach failure. Missing: a test that asserts `process_account` returns `status="unscoreable"`, `error="empty enrichment"` when Exa returns no results and Browserbase also fails.
- Fix approach: 10-line test, wires `FakeExa()` with empty lists.

**MEDIUM — No test exercising the citation-cross-check drop:**
- File: `tests/functional/test_outreach.py` (exists, but does it cover the drop?)
- The whole "no valid `[N]` markers => drop the paragraph" guard at `src/outreach.py:75-80` is the codebase's primary defense against hallucination. If it regresses silently, the user finds out via judge scores on a real run.
- Fix approach: add a test that feeds in a paragraph with `[99]` (invalid index) and asserts `paragraph == ""` and `cited_indices == ()`.

**LOW — No test for rate-limit retry behavior:**
- File missing: `tests/functional/test_nvidia_client.py` exists; check if it covers the retry path.
- The 6-attempt retry on `RateLimitError` is core to the "rate limits are handled" claim. A test that injects a stub raising `RateLimitError` twice then succeeding would lock in the behavior.

**LOW — No test for `compute_total` against the YAML weights:**
- The math is `0.40 * sv + 0.30 * am + 0.20 * sf + 0.10 * cb`. If someone edits `configs/icp.yaml` weights, nothing catches a sum-of-weights ≠ 1.0.
- Fix approach: a unit test that asserts `sum(axis.weight for axis in config.axes.values()) == 1.0`.

## Out-of-scope Items

CLAUDE.md explicitly defers these to v2/v3. None are partially implemented in `src/`, which is the correct state. Confirmation:

- Feedback loop from sales rejections — not present (verified by grep for "feedback", "reject").
- CRM trigger automation — not present.
- Webapp / dashboard / Slack bot — not present.
- Multi-tenant config — `configs/icp.yaml` is a singleton via `lru_cache` in `src/icp_config.py`, which is correct for a POC.
- Custom prompt-caching layer — not present (relies on DeepSeek auto-cache, as documented).

The README's "What's next" section (`README.md:78-80`) mentions v2/v3 items appropriately; no leakage into code.

## Scaling Limits

**LOW — Default `pipeline_concurrency=5` and `llm_max_in_flight=6`:**
- File: `src/config.py:71-76`
- For a 10-domain run, latency is bounded by serial DeepSeek calls per account (enrich → score → contacts → 3x outreach → 3x judge = ~8 LLM calls/account, ~80 total). At 5-10s/call that's 60-160s wall time per account, mostly hidden by concurrency.
- For a 1000-domain run, this design ships fine but you'll exhaust Exa quota (8 news + 5 about = 13 retrievals per account = 13k retrievals).
- Fix approach: none for POC scope. If scaling becomes a real requirement, add a cached-retrievals layer keyed by domain.

---

*Concerns audit: 2026-05-14*
