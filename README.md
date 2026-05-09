# poc_scraper

> **POC = Point of Contact**, sales-speak for the right person to reach in an account.
> Also: **Proof of Concept**.

A generic account-research prototype. Given a CSV of company domains, it produces a scored Google Sheet with the top 3 buyer personas to reach and a personalized outreach hook per persona, grounded in retrieved company context with inline citations.

The ICP rubric, weights, and definition live in `configs/icp.yaml` so the same code can be retargeted at any vertical without touching prompts.

## What it does

```
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

## Stack and design choices

- **NVIDIA Build endpoint** (OpenAI-compatible) for synthesis. Pluggable model IDs so writer and judge can be different model families.
- **Exa** for neural search on about pages + last-90-day company news.
- **Browserbase** for JS-rendered fallback when Exa misses.
- **LLM-as-judge eval** scoring groundedness, ICP relevance, and personalization on a 1-5 categorical scale (per [NeMo guidance](https://docs.nvidia.com/nemo/microservices/latest/evaluator/metrics/llm-as-a-judge.html), 1-10 numeric judges drift).
- **Google Sheets** as the output surface so a non-technical seller can read it and act on it.

## ICP rubric

The rubric is configured in `configs/icp.yaml`. Default weights:

- 40% **Support volume** - consumer-facing or transaction-heavy, public reviews of support load.
- 30% **AI/automation maturity** - posting AI/ML jobs, AI mentioned in product, on a competing platform.
- 20% **Stage fit** - mid-stage to public, not pre-seed, not Fortune 10 with full insourced AI.
- 10% **Channel breadth** - chat plus voice plus email plus SMS support exists.

Edit `configs/icp.yaml` to retarget. The scoring prompt and judge prompt both read from this file, so they stay in sync.

## What's next

- v2: feedback loop. When a seller rejects a recommendation, the rubric weights update.
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

## Eval results

`make eval` runs the LLM-as-judge over `evals/labeled.jsonl` and prints a markdown table with mean absolute error vs. hand labels.

```
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
