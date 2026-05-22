# CLAUDE.md - poc_scraper

Project-specific guidance for Claude Code working in this repo. Inherits from `~/.claude/CLAUDE.md`.

## What this project is

A generic account-research prototype. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP fit score against an editable rubric, top-3 buyer personas, and grounded outreach hooks per persona.

POC = Point of Contact (the right person to reach in an account) AND Proof of Concept. Keep that in the README.

The ICP rubric, weights, and definition live in `configs/icp.yaml` so the same code can be retargeted at any vertical without touching prompts.

## Working norms

- Show a 10-line plan before each major component (enrich, score, contacts, outreach, sheets, eval). Course-correct early, not after the fact.
- Commit after each working component lands. Conventional commits. Small, reviewable diffs - if a commit needs a paragraph to explain, it's probably too many files at once.
- No emojis in code or commit messages.
- No em-dashes in any markdown that will be published (README, eval reports). Use commas, parentheses, or rewrite.
- If you hit a real trade-off, stop and ask. Don't guess.
- Don't add comments that explain WHAT the code does. Only add a comment if the WHY isn't obvious from the names.
- This repo is intended to be public. The project is framed as a hypothetical GTM research planner: a fictional company has a product to sell, and the pipeline researches real prospect companies (Mercury, Notion, Linear, Faire, Retool, etc.) to decide which ones to prioritize. Real prospect names are required because the artifact only demonstrates value if it researches real accounts. Keep the seller side (the hypothetical company, its ICP, its product) abstract in `configs/icp.yaml` so any vendor in any vertical can retarget the pipeline by editing that one file. Vendor-specific names belong in `configs/icp.yaml` only, never in code, prompts, or commit messages. A pre-commit guard (`scripts/check_public_discipline.py` + local `.secrets-denylist`) blocks any names that would compromise this framing.

## Stack (locked, don't drift)

- Python 3.11+, `uv` for env management.
- LLM provider is configurable via `LLM_PROVIDER` env (`deepseek` | `nvidia`). DeepSeek is the recommended default; NVIDIA Build is a free fallback. Both are OpenAI-compatible. DeepSeek defaults: writer = `deepseek-v4-flash` (non-thinking), judge = `deepseek-v4-pro` with thinking + `reasoning_effort=high`. NVIDIA defaults: writer = `minimaxai/minimax-m2.7`, judge = `bytedance/seed-oss-36b-instruct`. Auto-select picks DeepSeek if its key is set.
- Exa primary for context retrieval (about pages + last-90-day news).
- Browserbase fallback for JS-rendered pages or when Exa returns thin results.
- Google Sheets API with service-account auth as the output surface.
- LLM-as-judge eval over hand-labeled examples in `evals/labeled.jsonl`. 1-5 categorical rubric per NeMo guidance (1-10 numeric judges drift).

## Testing strategy (5-layer)

1. **Unit tests** - call our pure functions directly with crafted inputs. No mocks because there's no I/O. Examples: ICP rubric math, citation extraction, CSV parsing.
2. **Functional tests** - one module under test, dependencies injected as stubs at the API boundary. Verifies our orchestration logic, not the network.
3. **Integration tests** - multiple modules wired together with stubs at external boundaries. Verifies the seams.
4. **Smoke E2E** - `make smoke`, opt-in, real LLM + Exa + Browserbase + Sheets against 2-3 fixture domains. Skipped in CI to avoid burning credits and avoid flakiness.
5. **Edge cases** - scattered across layers above. Empty enrichment, scrape blocked, sub-threshold eval score, malformed CSV, rate limits.

`make run` runs the full pipeline. `make smoke` is a separate opt-in target; it is no longer auto-chained because both hit the same rate-limited endpoint.

## Pre-commit vs CI split

- **Pre-commit (fast)**: black, ruff (auto-fix), trailing-whitespace, end-of-file-fixer.
- **CI (slower, more thorough)**: black --check, ruff, mypy --strict, pytest (offline tests only, smoke skipped).

mypy is strict. Don't loosen it without asking.

## Failure modes (first-class, don't let them slide)

- **Hallucination on a sales claim**: every outreach claim must trace to a retrieval. If the writer outputs a claim it can't cite, drop it.
- **Scraping blocked**: Browserbase retries once; if still blocked, log and continue. Never fail the whole run for one domain.
- **Empty enrichment**: mark the account `unscoreable`, surface that in the sheet. Don't fake data.
- **Rate limits**: asyncio + httpx, concurrency cap of 5, exponential backoff on 429s via tenacity.
- **Sub-threshold eval**: groundedness below the configured threshold flags the row red in the sheet.

Internal tools deserve the same rigor as customer-facing agents.

## File layout

```
src/
  pipeline.py            # asyncio orchestration
  models.py              # pydantic models
  config.py              # env -> typed settings
  enrich.py              # firmographics + news via Exa/Browserbase
  score.py               # ICP rubric (loads from configs/icp.yaml)
  contacts.py            # top-3 inferred personas
  outreach.py            # grounded hooks with citations
  sheets.py              # Google Sheets writer
  csv_io.py              # accounts.csv reader
  clients/
    nvidia_client.py     # OpenAI-compatible client for NVIDIA Build
    exa_client.py
    browserbase_client.py
configs/
  icp.yaml               # rubric weights, axis definitions, verdict thresholds
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
- Custom prompt-caching layer. DeepSeek auto-caches (1/10 input price on cache hits, no code changes needed); NVIDIA Build doesn't expose explicit cache control. If we move to a provider where caching needs explicit control (e.g. Anthropic), revisit.

Mention these in the README under "What's next." Don't implement them.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**poc_scraper**

A generic account-research prototype. Given a CSV of company domains, it produces a Google Sheet with firmographic enrichment, recent context, an ICP fit score against an editable rubric, top-3 buyer personas, and grounded outreach hooks per persona. "POC" means both Point of Contact (the right person to reach in an account) and Proof of Concept. The ICP rubric lives in `configs/icp.yaml` so the pipeline can be retargeted at any vertical without code changes.

**Core Value:** Every outreach claim is grounded in retrieved evidence and surfaced with a citation, and the eval system makes that rigor visible to a reader. If everything else slips, this must hold — it is the whole story.

### Constraints

- **Public repo discipline**: The project is framed as a hypothetical GTM research planner. Real prospect company names (Mercury, Notion, Linear, Faire, Retool, etc.) are required throughout the eval set and outreach drafts because the pipeline researches real accounts and the artifact must demonstrate that value. The seller side (the hypothetical vendor and its ICP) stays vendor-neutral and lives in `configs/icp.yaml`; vendor-specific names never appear in code, prompts, or commit messages. A pre-commit guard (`scripts/check_public_discipline.py` + local `.secrets-denylist`) enforces this — Why: the repo is public, and keeping the seller abstract makes the pipeline retargetable to any vendor in any vertical without code changes.
- **CLAUDE.md scope is the boundary**: No feedback loop, CRM automation, webapp/dashboard, multi-tenant config, or custom caching layer — These are v2/v3 per the locked project scope. Restating here so the roadmapper does not drift toward them when audit findings surface adjacent ideas.
- **Stack is locked**: Python 3.11+, uv, DeepSeek/NVIDIA OpenAI-compatible clients, Exa primary + Browserbase fallback, Google Sheets API, strict mypy, conventional commits, no emojis in code or commit messages, no em-dashes in published markdown — Per CLAUDE.md; changes require explicit discussion.
- **Grounded claims only**: Every outreach claim must trace to a retrieval; unciteable claims get dropped — This is the project's core value; it is a constraint on every code path that produces user-visible text, not a feature to be toggled.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python `>=3.11` (`pyproject.toml:6`, target = `py311` in black/ruff/mypy) - all production and test code under `src/`, `tests/`, `evals/`
- YAML - ICP rubric configuration (`configs/icp.yaml`)
- Makefile - task runner (`Makefile`)
## Runtime
- CPython 3.11+ asyncio (`src/pipeline.py` uses `asyncio.Semaphore` for the per-account fan-out)
- Pipeline is async end-to-end via `httpx.AsyncClient` and `openai.AsyncOpenAI`
- `uv` (see `Makefile:4` `uv sync --extra dev`, `make run` -> `uv run python -m src.pipeline`)
- Lockfile: `uv.lock` (present, committed)
- Build backend: `hatchling` (`pyproject.toml:34-39`, wheel packages = `["src"]`)
## Frameworks
- `openai>=1.40.0` (`pyproject.toml:8`) - OpenAI-compatible async client. Used against DeepSeek and NVIDIA Build, not OpenAI itself. See `src/clients/nvidia_client.py:8`.
- `pydantic>=2.7.0` (`pyproject.toml:10`) - typed models in `src/models.py`
- `pydantic-settings>=2.3.0` (`pyproject.toml:11`) - env-driven `Settings` in `src/config.py:13`
- `httpx>=0.27.0` (`pyproject.toml:9`) - direct HTTP for Exa and Browserbase clients
- `tenacity>=8.3.0` (`pyproject.toml:13`) - retry policy on all three external clients
- `pytest>=8.2.0`, `pytest-asyncio>=0.23.0` (`asyncio_mode = "auto"`, `pyproject.toml:69`)
- `pytest-cov>=5.0.0` - coverage, branch mode on `src/` (`pyproject.toml:76-78`)
- `respx>=0.21.0` - httpx mock transport for client tests
- Markers: `smoke` for opt-in live-API E2E (`pyproject.toml:71-73`)
- `black>=24.4.0` - formatter, line length 100, target py311 (`pyproject.toml:41-43`)
- `ruff>=0.4.0` - linter, rules `E,F,W,I,B,UP,SIM,ARG`, ignores `E501` (`pyproject.toml:45-54`)
- `mypy>=1.10.0` - strict mode, `disallow_untyped_defs`, `no_implicit_optional` (`pyproject.toml:56-66`). Google API modules are explicitly `ignore_missing_imports`.
- `pre-commit>=3.7.0` - hooks installed via `make install`
## Key Dependencies
- `openai>=1.40.0` - all LLM calls (writer + judge), pointed at provider-specific base URLs (`src/clients/nvidia_client.py:17-18`)
- `httpx>=0.27.0` - Exa and Browserbase HTTP transport
- `tenacity>=8.3.0` - exponential backoff on 429/`APIError`/`HTTPError`
- `pydantic>=2.7.0` + `pydantic-settings>=2.3.0` - typed config and domain models
- `google-api-python-client>=2.130.0` - Google Sheets v4 API discovery client (`src/sheets.py:297-307`)
- `google-auth>=2.30.0`, `google-auth-oauthlib>=1.2.0` - service-account credentials for Sheets
- `pyyaml>=6.0` - load `configs/icp.yaml` rubric
- `python-dotenv>=1.0.1` - `.env` loading (consumed by `pydantic-settings`)
- Dev type stubs: `types-requests`, `types-PyYAML` (`pyproject.toml:30-31`)
## Configuration
- `.env` (gitignored, present locally) loaded by `Settings` in `src/config.py:14-18`
- `.env.example` (committed) documents all required and optional vars
- Settings precedence: explicit env var > `.env` > defaults in `Settings` class
- Per-pipeline validation in `Settings.require_for_pipeline()` (`src/config.py:103-121`) - fails fast with a single message listing all missing keys
- `pyproject.toml` - single source for deps, tooling config, pytest config
- `Makefile` - `install`, `run`, `test`, `smoke`, `lint`, `format`, `typecheck`, `clean`, `eval-live`, `eval-fixtures`, `setup-sheet`
- `.pre-commit-config.yaml` - black, ruff (auto-fix), trailing-whitespace, end-of-file-fixer (CLAUDE.md split)
## Platform Requirements
- Python 3.11+
- `uv` installed (`brew install uv` or equivalent)
- Google service-account JSON at `./credentials.json` for Sheets writes
- At least one of `DEEPSEEK_API_KEY` or `NVIDIA_API_KEY`, plus `EXA_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` for `make run`
- Not a hosted service. Distributed as a CLI prototype. Run via `make run` against `inputs/accounts.csv`, output is a Google Sheet URL printed at the end of the run.
## LLM Provider Matrix
| Provider | Base URL | Writer default | Judge default | Reasoning toggle |
|---|---|---|---|---|
| DeepSeek (recommended) | `https://api.deepseek.com` (`src/clients/nvidia_client.py:18`) | `deepseek-v4-flash` (`src/config.py:49`) | `deepseek-v4-flash` with thinking enabled + `reasoning_effort=medium` (`src/config.py:50,53`) | `extra_body={"thinking": {"type": "enabled"}}` + top-level `reasoning_effort` |
| NVIDIA Build (free fallback) | `https://integrate.api.nvidia.com/v1` (`src/clients/nvidia_client.py:17`) | `minimaxai/minimax-m2.7` (`src/config.py:37`) | `bytedance/seed-oss-36b-instruct` (`src/config.py:38`) | `extra_body={"thinking_budget": <int>}`, `0` = disabled |
## Version Constraints (locked behaviors)
- mypy is `strict` and must stay strict (CLAUDE.md). Google API modules are the only allowed `ignore_missing_imports` override (`pyproject.toml:64-66`).
- Black line length 100 (`pyproject.toml:42`). Ruff matches (`pyproject.toml:46`).
- pytest `--strict-markers` (`pyproject.toml:74`) - new markers must be registered.
- `pytest-asyncio` runs in `auto` mode (`pyproject.toml:69`); async tests do not need explicit `@pytest.mark.asyncio`.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Snake_case module files: `src/enrich.py`, `src/csv_io.py`, `src/icp_config.py`.
- Leading underscore for module-private utilities: `src/_json_utils.py`.
- Test files mirror source name with `test_` prefix: `tests/unit/test_score_math.py` tests `src/score.py`.
- Client implementations grouped under `src/clients/` with `_client` suffix: `exa_client.py`, `browserbase_client.py`, `nvidia_client.py`.
- Public functions: lowercase snake_case (`compute_total`, `read_accounts`, `process_account`, `run_pipeline`).
- Module-private helpers: leading underscore (`_clip`, `_canonical`, `_clean_summary`, `_build_score_context`, `_parse_indices`).
- Async functions are not name-prefixed; rely on `async def` signature.
- snake_case throughout (`about_text`, `news_items`, `supporting_indices`).
- Module-level constants in SCREAMING_SNAKE_CASE: `ABOUT_TEXT_MIN_CHARS`, `SUMMARY_MAX_CHARS`, `NVIDIA_BASE_URL`, `DEEPSEEK_BASE_URL`, `INDEX_MARKER_RE`, `URL_RE`, `HTML_TAG`, `WHITESPACE`, `FIRMOGRAPHICS_SYSTEM`.
- Private instance attributes prefixed with underscore: `self._llm`, `self._exa`, `self._config`, `self._sem`.
- Pydantic models: PascalCase (`Account`, `Enrichment`, `ICPScore`, `RubricBreakdown`, `OutreachHook`).
- Module-private dataclasses prefixed with underscore: `_RawContext` in `src/enrich.py`, `_Frozen` base in `src/models.py`.
- Protocols suffixed `Like`: `ExaLike`, `BrowserbaseLike`, plus `LLMClient` in `src/clients/protocols.py`.
- `Literal` aliases for closed enums: `ScoreStatus = Literal["scored", "unscoreable"]`, `LLMProvider = Literal["deepseek", "nvidia"]`.
## Code Style
- `black` with `line-length = 100`, `target-version = ["py311"]` (`pyproject.toml:41-43`).
- Pinned via pre-commit at `black` rev `26.3.1` (`.pre-commit-config.yaml:13`).
- `ruff` with `line-length = 100`, `target-version = "py311"` (`pyproject.toml:45-47`).
- Selected rule families: `E, F, W, I, B, UP, SIM, ARG` (`pyproject.toml:50`).
- `E501` (line too long) ignored (black owns line length).
- Per-file override: `tests/**` exempt from `ARG` (unused-argument) so fake stubs can match real signatures (`pyproject.toml:53-54`).
- `mypy` strict (`pyproject.toml:56-62`):
- `disallow_untyped_defs` means every function (including helpers) must be fully annotated.
- Third-party stubs missing for `googleapiclient.*`, `google.oauth2.*`, `google_auth_oauthlib.*`; ignored explicitly (`pyproject.toml:64-66`).
- Do not loosen mypy without asking (`CLAUDE.md`).
## Import Organization
- None. The package is installed as `src` via hatch (`pyproject.toml:38-39`); imports use `src.foo` from test code and relative imports inside `src/`.
## Pydantic Usage
- `frozen=True` makes instances hashable and immutable; attempting `a.domain = "..."` raises `ValidationError` (asserted in `tests/unit/test_models.py:34-37`).
- `extra="forbid"` rejects unknown keys, catching prompt-drift where the writer invents fields.
- Numeric ranges enforced via `Field(ge=1, le=5)` on rubric axes and eval scores (`src/models.py:101-108, 134-138`).
- Custom `field_validator` for normalization: `Account._normalize_domain` strips protocols, `www.`, trailing slash, lowercases, and validates a dot is present (`src/models.py:18-28`).
- Tuples (not lists) for collections so frozen models stay hashable: `tech_signals: tuple[str, ...]`, `citations: tuple[Citation, ...]`, `supporting_indices: tuple[int, ...]`.
- Factory classmethods named `make` when a model needs lenient input coercion: `Citation.make(...)` builds via `model_validate` (`src/models.py:38-56`).
- Pipeline-relevant convenience constructors named after the resulting state: `ScoredAccount.unscoreable(...)` (`src/models.py:155-157`).
- `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_file=".env", extra="ignore")` in `src/config.py:13-18`.
- Computed properties for resolved provider state: `resolved_provider`, `writer_model`, `judge_model` (`src/config.py:83-101`).
- A `require_for_pipeline()` method raises `RuntimeError` listing missing env vars before any network call (`src/config.py:103-121`); cheaper than failing mid-run.
## Async Patterns
- Pipeline is async end-to-end. Entry point `src.pipeline.main` runs under `asyncio.run` (`src/pipeline.py:241`).
- Concurrency is bounded by `asyncio.Semaphore(concurrency)` in `run_pipeline`, default 5 (`src/pipeline.py:121-129`). Per-client semaphores additionally cap simultaneous LLM calls (`NvidiaClient._sem`, `src/clients/nvidia_client.py:86`).
- A single shared `httpx.AsyncClient` with `timeout=60.0` is passed to every HTTP-backed client (`src/pipeline.py:216-222`). Clients accept the http client via constructor injection rather than creating their own.
- Retries via `tenacity.AsyncRetrying` with `wait_random_exponential(multiplier=4, max=60)`, `stop_after_attempt(6)`, retrying on `RateLimitError | APIStatusError | APIError`. OpenAI SDK retries are disabled (`max_retries=0`) so backoff lives in one place (`src/clients/nvidia_client.py:62-63, 115-124`).
- Per-account failures are isolated: `process_account` wraps each stage (enrich, score, contacts, outreach, eval) in `try/except` and returns an `unscoreable` result rather than propagating (`src/pipeline.py:57-115`). One bad account never aborts the run.
## Error Handling
- Domain-level failures degrade gracefully and surface in the output sheet: marked `unscoreable` with a human-readable `error` string, never silently dropped.
- Programmer errors (bad input, malformed config) raise immediately at process boundaries: `Account` validation, `Settings.require_for_pipeline`, `compute_total` on out-of-range rubric values.
- Log at WARNING for per-stage failures, never CRITICAL/ERROR for expected provider hiccups: `log.warning("enrich failed for %s: %s", account.domain, exc)` (`src/pipeline.py:60-64`).
- Catch narrow exception classes when parsing untrusted text: `except (TypeError, ValueError)` around int/float coercion (`src/enrich.py:122`, `src/score.py:82, 116`).
- LLM JSON parsing routed through `src/_json_utils.parse_json_object`, which returns `None` rather than raising; callers branch on `None` and log the truncated text (`src/enrich.py:108-111`, `src/score.py:64-66`).
- Citation guarantee: outreach validates `cited_justifications` against the `Enrichment.justifications` index set, drops indices not present, and returns an empty hook if zero remain (`src/outreach.py:67-83`). Hallucinated citations cannot reach the sheet.
## Logging
- `INFO` for lifecycle events (`loaded %d accounts`, `RUN_LIMIT=%d set; processing first %d of %d`).
- `WARNING` for recoverable per-account / per-call failures (parse failures, stage exceptions).
- Use `%` placeholders, not f-strings, so logging defers formatting if the level is disabled.
- Truncate untrusted strings before logging: `result.text[:200]` (`src/score.py:65`).
## Comments
- Comments explain WHY, never WHAT. Names are expected to carry the WHAT (`CLAUDE.md`).
- Multi-line docstrings on public protocol-like classes and any function whose contract isn't obvious from the signature. Example: `Justification` (`src/models.py:67-73`) documents the 1-based numbering protocol shared by writer and judge.
- Inline rationale comments are common above non-obvious branches:
- No "what" comments like `# loop over accounts`.
## Function Design
- Constructor injection for collaborators (LLM client, http client, settings). Tests rely on this to pass `FakeExa`, `FakeBrowserbase`, `FakeAnthropic`.
- Keyword-only after `*` for optional fields on factory classmethods: `Citation.make(url, source, *, title=None, snippet=None, retrieved_at=None)` (`src/models.py:38-46`).
- Default config fetched at instantiation if not passed: `config: ICPConfig | None = None` then `self._config = config or get_config()` (`src/score.py:49-51`, `src/outreach.py:40-42`).
- Return `None` to signal a recoverable parse / validation failure (`Scorer.score`, `Enricher._extract_firmographics`).
- Return immutable models for successful results. No partial-state mutation.
- Tuples (not lists) returned from functions that yield collection fields on frozen models.
## Module Design
- No `__all__` declarations. Module-private names lead with `_`; everything else is importable.
- Package `__init__.py` files (`src/__init__.py`, `src/clients/__init__.py`) are empty - no re-export barrels. Imports point at the source module: `from src.models import Account`.
- External-collaborator contracts live in `src/clients/protocols.py` as `typing.Protocol` definitions (`ExaLike`, `BrowserbaseLike`, `LLMClient`). Real clients and fakes both satisfy these structurally without an explicit `class FakeExa(ExaLike):` declaration.
## Project Rules (from CLAUDE.md, observable in code)
- **No emojis in code or commit messages.** Confirmed across `src/`, `tests/`, and `git log` (`fix(score): require >=1 supporting index, ...`).
- **Conventional commits.** Recent history: `feat(...)`, `fix(...)`, `docs(...)`, `refactor(...)`. Scoped: `feat(sheets):`, `fix(judge):`.
- **No em-dashes in published markdown.** README, eval reports use commas / parentheses.
- **Public-repo discipline.** Code, prompts, and configs avoid naming specific verticals or vendors; ICP definition lives in `configs/icp.yaml`, referenced through `src/icp_config.py`.
- **Stack is locked.** Python 3.11+, `uv`, `httpx`, `pydantic` v2, `openai` SDK (OpenAI-compatible call shape used for both DeepSeek and NVIDIA Build), `tenacity`, `google-api-python-client`. Listed in `pyproject.toml:7-18`.
- **Citations must trace to retrieval.** Enforced in `OutreachGenerator.generate` by intersecting writer-claimed indices with markers actually present in the paragraph and with the `Enrichment.justifications` index set (`src/outreach.py:67-83`).
- **Empty enrichment becomes `unscoreable`, never faked.** `src/pipeline.py:66-67`.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| `main` | Wire settings, clients, deps; run pipeline; write sheet | `src/pipeline.py` |
| `run_pipeline` / `process_account` | Bounded async fan-out over accounts; per-stage exception isolation | `src/pipeline.py` |
| `Deps` / `build_deps` | Frozen dataclass bundling Enricher, Scorer, ContactExtractor, OutreachGenerator, EvalRubric for injection | `src/pipeline.py` |
| `Settings` | Typed env loader via pydantic-settings; resolves LLM provider, models, concurrency, paths | `src/config.py` |
| `read_accounts` | Parse `inputs/accounts.csv`, validate domain format, dedupe | `src/csv_io.py` |
| `Enricher` | Exa about + news, Browserbase fallback for thin pages, firmographics extraction, builds numbered `Justification` list | `src/enrich.py` |
| `Scorer` | Writer-LLM call against the ICP rubric loaded from `configs/icp.yaml`; weighted total + verdict | `src/score.py` |
| `ContactExtractor` | Writer-LLM call to propose 3 personas; falls back to defaults on parse failure | `src/contacts.py` |
| `OutreachGenerator` | Writer-LLM call producing a 3-5 sentence paragraph with `[N]` citations; validates markers against `Enrichment.justifications` | `src/outreach.py` |
| `EvalRubric` | Judge-LLM call per hook; claim-decomposition groundedness, plus icp_relevance + personalization | `evals/rubric.py` |
| `SheetsWriter` | Google Sheets writer: results tab per run, plus refreshed `Rubric` and `Inputs` tabs, plus row/cell formatting | `src/sheets.py` |
| `ICPConfig` / `get_config` | Load and validate `configs/icp.yaml`; axis weights must sum to 1.0 | `src/icp_config.py` |
| `NvidiaClient` | OpenAI-compatible client (NVIDIA Build or DeepSeek), tenacity retries, in-flight cap, optional JSON mode and thinking-mode toggles | `src/clients/nvidia_client.py` |
| `ExaClient` | `search_about` + `search_news` over Exa | `src/clients/exa_client.py` |
| `BrowserbaseClient` | JS-rendered fallback for thin Exa pages | `src/clients/browserbase_client.py` |
| Protocols | Structural typing for LLM / Exa / Browserbase boundaries — enables stub injection in tests | `src/clients/protocols.py` |
| Pydantic models | Frozen, extra-forbid models for every cross-stage value | `src/models.py` |
| `parse_json_object` / `parse_json_array` | Tolerant JSON extraction from LLM output | `src/_json_utils.py` |
## Pattern Overview
- Each stage is a small class with a single async method, constructor-injected dependencies (LLM client, Exa, Browserbase, ICP config). No globals threaded through the pipeline.
- All cross-stage values are frozen pydantic models (`src/models.py`) with `extra="forbid"`, so a schema drift fails loudly.
- Per-stage exception isolation in `process_account` (`src/pipeline.py:57`): a failed enrich marks the account `unscoreable`; a failed score does the same; outreach failures drop a single hook, never the whole row.
- Citation handling is index-based, not URL-based. `Enrichment.justifications` is numbered 1..N once in `enrich._number_justifications` and that same list is shown to writer, judge, and the sheet. Claims are validated by index membership.
- Provider-agnostic LLM client. `NvidiaClient` speaks OpenAI's wire format and is configured per-provider in `_build_writer` / `_build_judge` (`src/pipeline.py:147`, `:166`).
## Layers
- Purpose: load config, build deps, fan out work, write sink.
- Location: `src/pipeline.py`
- Depends on: every stage module, clients, csv_io, sheets.
- Used by: `make run`, `evals/run_live.py`.
- Purpose: one async class per pipeline step.
- Location: `src/enrich.py`, `src/score.py`, `src/contacts.py`, `src/outreach.py`, `evals/rubric.py`.
- Depends on: protocol-typed clients only; never on concrete httpx or openai SDK objects.
- Used by: `src/pipeline.py::build_deps` and tests with stub clients.
- Purpose: HTTP / SDK calls to external services, with retry policy and concurrency caps.
- Location: `src/clients/`.
- Depends on: httpx, openai, tenacity.
- Used by: stages, via protocol types in `src/clients/protocols.py`.
- Purpose: typed settings (env) and rubric (yaml).
- Location: `src/config.py`, `src/icp_config.py`, `configs/icp.yaml`.
- Used by: pipeline entry, stages that need the rubric (score, contacts, outreach, eval rubric), sheets (rubric tab).
- Purpose: render `ScoredAccount` list into a Google Sheet with formatting.
- Location: `src/sheets.py`.
- Depends on: `google-api-python-client`, `google-auth`.
- Used by: pipeline entry only.
- Purpose: shared schema across all layers.
- Location: `src/models.py`.
- Imported by: every other module.
## Data Flow
### Primary Request Path (one account)
### Eval Sidecar (offline calibration)
### Live Eval (`make eval-live`)
- No mutable global state in the hot path. `get_settings()` and `get_config()` are `@lru_cache(maxsize=1)` singletons over immutable pydantic models; safe to call from any stage.
## Key Abstractions
- Purpose: a single retrieved snippet with a stable 1-based index, threaded through writer, judge, and sheet.
- Defined: `src/models.py:66` (with docstring explaining the contract).
- Built: `src/enrich.py:127` (`_number_justifications`).
- Consumed by: `src/score.py` (`supporting_indices`), `src/outreach.py` (`cited_indices`), `evals/rubric.py` (claim-to-index mapping), `src/sheets.py` (citation rendering).
- Purpose: hand the pipeline a single immutable struct holding every stage's collaborator.
- Defined: `src/pipeline.py:33`.
- Constructed: `build_deps()` (`src/pipeline.py:42`) — also used by `evals/run_live.py`.
- Purpose: stages depend on structural types, not concrete client classes.
- Defined: `src/clients/protocols.py`.
- Pattern: tests pass plain Python objects matching `LLMClient` / `ExaLike` / `BrowserbaseLike`.
- Purpose: edit the rubric, retarget the vertical; both writer and judge prompts read from this file.
- Defined: `src/icp_config.py`.
- Source of truth: `configs/icp.yaml`.
## Entry Points
- Location: `src/pipeline.py:239`.
- Triggers: operator command.
- Responsibilities: full pipeline -> Google Sheet.
- Location: `evals/run_live.py:171`.
- Triggers: operator command.
- Responsibilities: live pipeline + judge over 2-3 domains, markdown table to stdout.
- Location: `evals/run_eval.py:136`.
- Triggers: operator command.
- Responsibilities: judge-vs-hand-labels calibration, markdown table to stdout.
- Location: `scripts/setup_sheet.py`.
- Triggers: one-shot bootstrap.
- Responsibilities: create a new workbook, share with operator, persist `GOOGLE_SHEET_ID` to `.env`.
## Architectural Constraints
- **Threading:** single asyncio event loop. Concurrency comes from `asyncio.Semaphore(pipeline_concurrency=5)` over accounts (`src/pipeline.py:123`) and a per-LLM-client `llm_max_in_flight=6` cap (`src/clients/nvidia_client.py`). No threads, no multiprocessing.
- **HTTP client lifetime:** one `httpx.AsyncClient` is created in `main` and shared with both Exa and Browserbase clients (`src/pipeline.py:216`). Closed by the async context manager.
- **Frozen models:** every pydantic model in `src/models.py` is frozen with `extra="forbid"`. Adding a field to one stage's output requires updating the model and any downstream consumers; the type checker will catch mismatches.
- **ICP weights:** must sum to 1.0; validated in `ICPConfig._check_axes` (`src/icp_config.py:42`). Axes must be exactly `support_volume`, `ai_maturity`, `stage_fit`, `channel_breadth` — changing this set requires touching `models.RubricBreakdown` too.
- **Global state:** none mutable. `get_settings()` and `get_config()` are cached read-only singletons.
- **Provider selection:** `Settings.resolved_provider` picks DeepSeek if its key is set, NVIDIA otherwise; `LLM_PROVIDER` env overrides. Writer/judge prompts and JSON-mode wiring branch on this in `_build_writer` and `_build_judge` (`src/pipeline.py:147`).
- **Mypy strict:** `[tool.mypy] strict = true`. New code must be fully annotated.
## Anti-Patterns
### Inline URL citations from the writer
### Failing the run on a single bad domain
### Fabricated firmographics on empty context
### Numeric 1-10 judges
## Error Handling
- Per-stage `try/except` in `process_account` (`src/pipeline.py:57`), logging at WARN, continuing with a degraded `ScoredAccount` or empty hook tuple.
- Tenacity retries with exponential backoff inside each client (`src/clients/nvidia_client.py`, `src/clients/exa_client.py`, `src/clients/browserbase_client.py`).
- Tolerant JSON parsing (`src/_json_utils.py`); parse failures return `None` and the stage degrades, not the whole pipeline.
- Empty/invalid enrichment becomes `ScoredAccount.unscoreable` with an explicit `error` field surfaced in the sheet.
- Sub-threshold groundedness flags the cell red but does not drop the row (`SheetsWriter._apply_eval_flag_text`, `src/sheets.py:431`).
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
