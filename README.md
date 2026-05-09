# poc_scraper

> **POC = Point of Contact**, sales-speak for the right person to reach in an account.
> Also: **Proof of Concept**.

A generic account-research prototype. Given a CSV of company domains, it produces a scored Google Sheet with the top 3 buyer personas to reach and a personalized outreach hook per persona, grounded in retrieved company context with inline citations.

The ICP rubric, weights, and definition live in `configs/icp.yaml` so the same code can be retargeted at any vertical without touching prompts.

## What it does

```text
inputs/accounts.csv  ->  enrich (Exa + Browserbase)  ->  score (ICP rubric)
                                                      ->  contacts (top 3 personas)
                                                      ->  outreach (grounded hooks)
                                                      ->  Google Sheet
```

Per account, the sheet shows:

- Firmographics (name, industry, headcount, tech signals).
- Last-90-day context (funding, hiring, product launches) with source URLs.
- ICP fit verdict (strong / borderline / weak) with weighted breakdown so the seller sees *why*.
- Top 3 target roles to reach with rationale.
- One paragraph of grounded outreach copy per role with inline citations.

Rows are color-coded: strong fits get green, borderline get yellow, eval-flagged groundedness gets red (overrides verdict color).

## Stack and design choices

- **NVIDIA Build endpoint** ([https://build.nvidia.com/](https://build.nvidia.com/)) for synthesis. OpenAI-compatible at `https://integrate.api.nvidia.com/v1`, free preview models.
- **Two different model families on purpose**: writer = MiniMax M2.7 (creative, hot temperature). Judge = Seed-OSS 36B (reasoning model, cold temperature, bounded reasoning budget). Splitting them avoids the self-grading bias that shows up when the same model writes and evaluates.
- **Exa** for neural search on about pages and last-90-day company news.
- **Browserbase** for JS-rendered fallback when Exa misses.
- **LLM-as-judge eval** scoring groundedness, ICP relevance, and personalization on a 1-5 categorical scale (per [NeMo guidance](https://docs.nvidia.com/nemo/microservices/latest/evaluator/metrics/llm-as-a-judge.html), 1-10 numeric judges drift).
- **Google Sheets** as the output surface so a non-technical reader can act on it.

## ICP rubric

The rubric is configured in `configs/icp.yaml`. Default weights:

- 40% **Support volume** - consumer-facing or transaction-heavy, public reviews of support load.
- 30% **AI/automation maturity** - AI/ML hiring, AI mentioned in product, public deflection metrics.
- 20% **Stage fit** - mid-stage to public, not pre-seed, not Fortune 10 with full insourced AI.
- 10% **Channel breadth** - chat plus voice plus email plus SMS support exists.

Each axis is scored 1-5 by the writer using anchor descriptions in the YAML, then weighted into a 1-5 total. Verdict bucketing: total >= 4.0 = strong, >= 2.5 = borderline, < 2.5 = weak.

Edit `configs/icp.yaml` to retarget for a different vertical. Both the scoring prompt and the judge prompt read from this file, so they stay in sync.

## What's next

- v2: feedback loop. When a user rejects a recommendation, the rubric weights update.
- v3: CRM trigger. Runs automatically when a new account hits the CRM.

## Run it

```bash
# 1. Install
make install

# 2. Add API keys to .env (copy from .env.example)
cp .env.example .env
# fill in NVIDIA_API_KEY, EXA_API_KEY, BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID
# point GOOGLE_APPLICATION_CREDENTIALS at a Sheets-enabled service-account JSON

# 3. Drop domains into inputs/accounts.csv (one per line, header `domain`)

# 4. Ship
make run
```

`make run` runs the full pipeline against `inputs/accounts.csv` and then runs `make smoke` so a silently-broken pipeline cannot ship to a recording.

### Picking models

The defaults are MiniMax M2.7 (writer) and Seed-OSS 36B (judge). NVIDIA Build's preview model availability rotates, so if you see a 400 / "DEGRADED function" error from one of them, swap via `WRITER_MODEL` or `JUDGE_MODEL` in `.env`. Tested working alternatives at the time of writing:

- Writer: `mistralai/mistral-large-3-675b-instruct-2512`, `qwen/qwen3-coder-480b-a35b-instruct`
- Judge: `qwen/qwen3-coder-480b-a35b-instruct`, `nvidia/nemotron-mini-4b-instruct`, `mistralai/mistral-large-3-675b-instruct-2512`

Keep the writer and judge in different families. Same family means self-grading bias.

### Reasoning budget for the judge

Seed-OSS is a reasoning model. We pass `thinking_budget` via `extra_body` to bound reasoning tokens. `JUDGE_REASONING_BUDGET=1024` leaves room in `JUDGE_MAX_TOKENS=4096` for the final JSON. If you set it to `-1` (unlimited), bump `JUDGE_MAX_TOKENS` to 8192+ or the model will exhaust output budget on reasoning and return an empty paragraph.

For non-reasoning judge models, leave `JUDGE_REASONING_BUDGET=0` to skip the field entirely.

## Eval results

`make eval` runs the LLM-as-judge over `evals/labeled.jsonl` and prints a markdown table with mean absolute error vs. hand labels.

```text
(populated after first run)
```

## Tests

| Layer       | What it covers                                                            | Hits real APIs? |
|-------------|---------------------------------------------------------------------------|-----------------|
| unit        | Our pure functions (rubric math, citation extraction, CSV parsing).       | No              |
| functional  | One module with stubbed external boundaries.                              | No              |
| integration | Multiple modules wired with stubbed external boundaries.                  | No              |
| smoke       | Real LLM + Exa + Browserbase + Sheets, 2-3 fixture domains.               | Yes (opt-in)    |
| edge cases  | Empty enrichment, scrape blocked, sub-threshold eval, rate limits.        | Mixed           |

`make test` runs everything except smoke. `make smoke` runs the live E2E.
