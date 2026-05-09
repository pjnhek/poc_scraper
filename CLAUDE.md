# CLAUDE.md - poc_scraper

Project-specific guidance for Claude Code working in this repo. Inherits from `~/.claude/CLAUDE.md`.

## What this project is

An account-mapping prototype targeted at AI customer-support sellers. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP score, top-3 buyer personas, and grounded outreach hooks per persona.

The double pun in the name matters: **POC = Point of Contact** (sales-speak for the decision-maker) AND **Proof of Concept**. Keep that in the README.

## Working norms

- Show a 10-line plan before each major component (enrich, score, contacts, outreach, sheets, eval). Course-correct early, not after the fact.
- Commit after each working component lands. Conventional commits. Small, reviewable diffs - if a commit needs a paragraph to explain, it's probably too many files at once.
- No emojis in code or commit messages.
- No em-dashes in any markdown that will be published (README, eval reports). Use commas, parentheses, or rewrite.
- If you hit a real trade-off, stop and ask. Don't guess.
- Don't add comments that explain WHAT the code does. Only add a comment if the WHY isn't obvious from the names.

## Stack (locked, don't drift)

- Python 3.11+, `uv` for env management.
- Anthropic API, Claude Sonnet 4.6 (`claude-sonnet-4-6`) for synthesis. Use prompt caching aggressively on the company-news context block.
- Exa primary for context retrieval (about pages + last-90-day news).
- Browserbase fallback for JS-rendered pages or when Exa returns thin results.
- Google Sheets API with service-account auth as the output surface.
- LLM-as-judge eval over hand-labeled examples in `evals/labeled.jsonl`.

## Testing strategy (5-layer)

1. **Unit tests** - call our pure functions directly with crafted inputs. No mocks because there's no I/O. Examples: ICP rubric math, citation extraction, CSV parsing.
2. **Functional tests** - one module under test, dependencies injected as stubs at the API boundary. Verifies our orchestration logic, not the network.
3. **Integration tests** - multiple modules wired together with stubs at external boundaries. Verifies the seams.
4. **Smoke E2E** - `make smoke`, opt-in, real Anthropic + Exa + Browserbase + Sheets against 2-3 fixture domains. Skipped in CI to avoid burning credits and avoid flakiness.
5. **Edge cases** - scattered across layers above. Empty enrichment, scrape blocked, sub-threshold eval score, malformed CSV, rate limits.

`make run` runs the full pipeline AND `make smoke` at the end so a silently-broken pipeline cannot ship to a Loom recording.

## Pre-commit vs CI split

- **Pre-commit (fast)**: black, ruff (auto-fix), trailing-whitespace, end-of-file-fixer.
- **CI (slower, more thorough)**: black --check, ruff, mypy --strict, pytest (offline tests only, smoke skipped).

mypy is strict. Don't loosen it without asking.

## Failure modes (first-class, don't let them slide)

- **Hallucination on a sales claim**: every outreach claim must trace to a retrieval. If Claude outputs a claim it can't cite, drop it.
- **Scraping blocked**: Browserbase retries once; if still blocked, log and continue. Never fail the whole run for one domain.
- **Empty enrichment**: mark the account `unscoreable`, surface that in the sheet. Don't fake data.
- **Rate limits**: asyncio + httpx, concurrency cap of 5, exponential backoff on 429s via tenacity.
- **Sub-threshold eval**: groundedness < 6/10 flags the row red in the sheet.

Internal tools deserve the same rigor as customer-facing agents.

## File layout

```
src/
  pipeline.py            # asyncio orchestration
  models.py              # pydantic models
  config.py              # env -> typed settings
  enrich.py              # firmographics + news via Exa/Browserbase
  score.py               # ICP rubric
  contacts.py            # top-3 inferred personas
  outreach.py            # grounded hooks with citations
  sheets.py              # Google Sheets writer
  csv_io.py              # accounts.csv reader
  clients/
    anthropic_client.py  # with prompt caching
    exa_client.py
    browserbase_client.py
evals/
  rubric.py              # LLM-as-judge
  labeled.jsonl          # hand-labeled examples
  run_eval.py
tests/
  unit/
  functional/
  integration/
  smoke/
inputs/accounts.csv
```

## Out of scope (v2/v3, do not build)

- Feedback loop from sales rejections.
- CRM trigger automation.
- Webapp / dashboard / Slack bot.
- Multi-tenant config.
- Caching layer beyond Anthropic prompt caching.

Mention these in the README under "What's next." Don't implement them.
