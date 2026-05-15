# External Integrations

**Analysis Date:** 2026-05-14

## APIs & External Services

**LLM Providers (OpenAI-compatible chat-completions wire format):**

- **DeepSeek** (recommended default) - writer + judge for firmographics summary, ICP scoring, persona inference, outreach hooks, and LLM-as-judge evaluation
  - Base URL: `https://api.deepseek.com` (`src/clients/nvidia_client.py:18`)
  - SDK/Client: `openai.AsyncOpenAI` wrapped by `NvidiaClient` (`src/clients/nvidia_client.py:55`)
  - Auth: `DEEPSEEK_API_KEY` env var
  - Models: `deepseek-v4-flash` (writer + judge default); `deepseek-v4-pro` for offline-analysis judge with `reasoning_effort=high`
  - Reasoning: thinking mode toggled via `extra_body={"thinking": {"type": "enabled"}}`; `reasoning_effort` sent as top-level kwarg (`src/clients/nvidia_client.py:106-114`)
  - Auto-caches input: see CLAUDE.md "Stack" - no client-side caching needed

- **NVIDIA Build** (free-tier fallback) - same writer + judge roles
  - Base URL: `https://integrate.api.nvidia.com/v1` (`src/clients/nvidia_client.py:17`)
  - SDK/Client: same `NvidiaClient`
  - Auth: `NVIDIA_API_KEY` env var
  - Models: `minimaxai/minimax-m2.7` (writer), `bytedance/seed-oss-36b-instruct` (judge)
  - Reasoning: `thinking_budget` extra (`0` = disabled, `-1` = unlimited, positive = bounded). Free tier recommended at `0` (`.env.example:60`).

- **Exa** - neural search for company about-pages and last-90-day news, used as the citation pool
  - Base URL: `https://api.exa.ai` (`src/clients/exa_client.py:15`)
  - SDK/Client: `ExaClient` (`src/clients/exa_client.py:26`) over raw `httpx.AsyncClient`
  - Auth: `x-api-key` header, value from `EXA_API_KEY`
  - Endpoints used: `POST /search` with `type=neural`. Two query shapes: `search_news` (90-day window, 8 results) and `search_about` (domain-restricted, 5 results)
  - Result fields: `url`, `title`, `text|snippet`, `publishedDate` -> `ExaResult`

- **Browserbase** - headless rendering fallback when Exa returns thin results or pages are JS-only
  - Base URL: `https://api.browserbase.com/v1` (`src/clients/browserbase_client.py:15`)
  - SDK/Client: `BrowserbaseClient` (`src/clients/browserbase_client.py:31`) over raw `httpx.AsyncClient`
  - Auth: `x-bb-api-key` header from `BROWSERBASE_API_KEY`; `projectId` body param from `BROWSERBASE_PROJECT_ID`
  - Endpoint used: `POST /scrape` with `{projectId, url, format: "html"}`
  - Failure mode: swallows exceptions and returns `None` (`src/clients/browserbase_client.py:54-59`) so one blocked domain never fails the run

## Data Storage

**Databases:**
- None. Pipeline is stateless. Each `make run` is a fresh execution against `inputs/accounts.csv`.

**File Storage:**
- Local filesystem only
  - Input: `inputs/accounts.csv` (path configurable via `Settings.accounts_csv`, `src/config.py:81`)
  - Output: Google Sheet (see below). No local artifact persistence.
  - Credentials: `./credentials.json` (Google service-account JSON, path from `GOOGLE_APPLICATION_CREDENTIALS`)
  - Eval fixtures: `evals/labeled.jsonl`

**Caching:**
- No application-level cache.
- DeepSeek-side automatic prompt caching (1/10 input price on cache hits) - documented in CLAUDE.md, no code path required.

## Authentication & Identity

**Service auth (machine -> external APIs):**
- LLM providers: bearer API key via `AsyncOpenAI(api_key=...)`
- Exa: `x-api-key` header
- Browserbase: `x-bb-api-key` header
- Google Sheets: service-account JSON loaded via `google.oauth2.service_account.Credentials.from_service_account_file` (`src/sheets.py:297-307`), scope `https://www.googleapis.com/auth/spreadsheets` (`src/sheets.py:46`)

**End-user auth:**
- None. Single-operator CLI prototype.

## Output Surface: Google Sheets

- API: Google Sheets v4 via `googleapiclient.discovery.build("sheets", "v4", ...)` (`src/sheets.py:307`)
- Write behavior in `SheetsWriter.write` (`src/sheets.py:309`):
  - If `GOOGLE_SHEET_ID` is set: append a new `run-YYYYMMDD-HHMMSS` tab to that workbook
  - Otherwise: `spreadsheets().create` a fresh workbook and print the URL
  - Also refreshes named tabs `Rubric` and `Inputs` (`src/sheets.py:145-146`, `327-339`) for human review
  - Applies row background colors by verdict (`src/sheets.py:253-275`) and red bold text on groundedness-flagged rows (`src/sheets.py:431-471`)
- `cache_discovery=False` (`src/sheets.py:307`) - suppresses the googleapiclient file cache warning

## Monitoring & Observability

**Error Tracking:**
- None. Failures log via stdlib `logging` (`src/clients/*.py` use `log = logging.getLogger(__name__)`).

**Logs:**
- Stdlib `logging`. Retries log at WARNING via `tenacity.before_sleep_log(log, logging.WARNING)` (`src/clients/nvidia_client.py:119`).
- Per-account failures in the pipeline never crash the run; they are recorded on the row's `error` column in the Sheet (`src/sheets.py:44`).

## CI/CD & Deployment

**Hosting:**
- Not hosted. Run locally or in a one-off container via `make run`.

**CI Pipeline:**
- Pre-commit (local, fast): black, ruff (auto-fix), trailing-whitespace, end-of-file-fixer
- CI (slower, more thorough): `black --check`, `ruff`, `mypy --strict`, `pytest -m "not smoke"`. Smoke tests skipped to avoid burning API credits. (Split documented in CLAUDE.md.)

## Environment Configuration

**Required env vars for `make run` (`src/config.py:103-121`):**
- One of `DEEPSEEK_API_KEY` or `NVIDIA_API_KEY` (matching the resolved provider)
- `EXA_API_KEY`
- `BROWSERBASE_API_KEY`
- `BROWSERBASE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS` (defaults to `./credentials.json`)

**Optional env vars (`src/config.py`, `.env.example`):**
- `LLM_PROVIDER` (`deepseek` | `nvidia`) - force a provider, else auto-select
- `GOOGLE_SHEET_ID` - target existing workbook; unset = create new sheet per run
- `WRITER_MODEL_DEEPSEEK`, `WRITER_MODEL_NVIDIA`, `JUDGE_MODEL_DEEPSEEK`, `JUDGE_MODEL_NVIDIA` - model overrides
- `WRITER_TEMPERATURE` (default 1.0), `WRITER_TOP_P` (0.95), `WRITER_MAX_TOKENS` (8192)
- `JUDGE_TEMPERATURE` (default 0.3), `JUDGE_TOP_P` (0.95), `JUDGE_MAX_TOKENS` (4096)
- `JUDGE_REASONING_EFFORT_DEEPSEEK` (`low` | `medium` | `high`, default `medium`)
- `JUDGE_REASONING_BUDGET` (NVIDIA only; 0 disabled, -1 unlimited, positive = cap)
- `PIPELINE_CONCURRENCY` (default 5, range 1-50) - per-account asyncio fan-out
- `LLM_MAX_IN_FLIGHT` (default 6, range 1-50) - per-`NvidiaClient` semaphore cap
- `RUN_LIMIT` - cap on domains from `accounts.csv`

**Secrets location:**
- `.env` (gitignored). `credentials.json` (gitignored). Neither is read by tooling other than the runtime config loader.

## Rate Limits & Concurrency

**Per-account concurrency:**
- `asyncio.Semaphore(PIPELINE_CONCURRENCY)` in `src/pipeline.py:121-123`. Default cap 5.

**Per-LLM-client in-flight cap:**
- `NvidiaClient` owns an internal `asyncio.Semaphore(max_in_flight)` (`src/clients/nvidia_client.py:86`).
- Configured from `Settings.llm_max_in_flight` at construction in `src/pipeline.py:156, 185`. Default 6 (DeepSeek-tuned). Drop to 2-3 for NVIDIA free tier on 429s (`.env.example:64-67`).

**Retry policies:**

| Client | Retries | Backoff | Retry-on |
|---|---|---|---|
| `NvidiaClient` (`src/clients/nvidia_client.py:115-124`) | 6 attempts | `wait_random_exponential(multiplier=4, max=60)` | `RateLimitError`, `APIStatusError`, `APIError` |
| `ExaClient` (`src/clients/exa_client.py:71-86`) | 4 attempts | `wait_exponential(multiplier=1, min=1, max=15)` | `httpx.HTTPError` |
| `BrowserbaseClient` (`src/clients/browserbase_client.py:62-77`) | 2 attempts then swallow | `wait_exponential(multiplier=1, min=1, max=8)` | `httpx.HTTPError` |

**Per-request timeouts:**
- LLM: 120s (`DEFAULT_REQUEST_TIMEOUT_S`, `src/clients/nvidia_client.py:23`). OpenAI SDK's own retries disabled (`max_retries=0`) to avoid double-retry.
- Exa: 30s default (`src/clients/exa_client.py:31`)
- Browserbase: 60s default (`src/clients/browserbase_client.py:38`)

## Webhooks & Callbacks

**Incoming:** None.

**Outgoing:** None. Single-direction request/response only.

## Client Module Index

| Module | Purpose | Protocol |
|---|---|---|
| `src/clients/nvidia_client.py` | OpenAI-compatible LLM client for DeepSeek and NVIDIA Build | `LLMClient` (`src/clients/protocols.py:22`) |
| `src/clients/exa_client.py` | Neural web search for citations | `ExaLike` (`src/clients/protocols.py:10`) |
| `src/clients/browserbase_client.py` | Headless render fallback | `BrowserbaseLike` (`src/clients/protocols.py:18`) |
| `src/clients/protocols.py` | Structural typing seams used to inject stubs in tests | - |

All external boundaries are reachable only through these protocols, which makes functional and integration tests injectable without monkey-patching HTTP (CLAUDE.md "Testing strategy" layer 2-3).

---

*Integration audit: 2026-05-14*
