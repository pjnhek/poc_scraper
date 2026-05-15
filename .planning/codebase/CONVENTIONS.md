# Coding Conventions

**Analysis Date:** 2026-05-14

## Naming Patterns

**Files:**
- Snake_case module files: `src/enrich.py`, `src/csv_io.py`, `src/icp_config.py`.
- Leading underscore for module-private utilities: `src/_json_utils.py`.
- Test files mirror source name with `test_` prefix: `tests/unit/test_score_math.py` tests `src/score.py`.
- Client implementations grouped under `src/clients/` with `_client` suffix: `exa_client.py`, `browserbase_client.py`, `nvidia_client.py`.

**Functions:**
- Public functions: lowercase snake_case (`compute_total`, `read_accounts`, `process_account`, `run_pipeline`).
- Module-private helpers: leading underscore (`_clip`, `_canonical`, `_clean_summary`, `_build_score_context`, `_parse_indices`).
- Async functions are not name-prefixed; rely on `async def` signature.

**Variables:**
- snake_case throughout (`about_text`, `news_items`, `supporting_indices`).
- Module-level constants in SCREAMING_SNAKE_CASE: `ABOUT_TEXT_MIN_CHARS`, `SUMMARY_MAX_CHARS`, `NVIDIA_BASE_URL`, `DEEPSEEK_BASE_URL`, `INDEX_MARKER_RE`, `URL_RE`, `HTML_TAG`, `WHITESPACE`, `FIRMOGRAPHICS_SYSTEM`.
- Private instance attributes prefixed with underscore: `self._llm`, `self._exa`, `self._config`, `self._sem`.

**Types:**
- Pydantic models: PascalCase (`Account`, `Enrichment`, `ICPScore`, `RubricBreakdown`, `OutreachHook`).
- Module-private dataclasses prefixed with underscore: `_RawContext` in `src/enrich.py`, `_Frozen` base in `src/models.py`.
- Protocols suffixed `Like`: `ExaLike`, `BrowserbaseLike`, plus `LLMClient` in `src/clients/protocols.py`.
- `Literal` aliases for closed enums: `ScoreStatus = Literal["scored", "unscoreable"]`, `LLMProvider = Literal["deepseek", "nvidia"]`.

## Code Style

**Formatting:**
- `black` with `line-length = 100`, `target-version = ["py311"]` (`pyproject.toml:41-43`).
- Pinned via pre-commit at `black` rev `26.3.1` (`.pre-commit-config.yaml:13`).

**Linting:**
- `ruff` with `line-length = 100`, `target-version = "py311"` (`pyproject.toml:45-47`).
- Selected rule families: `E, F, W, I, B, UP, SIM, ARG` (`pyproject.toml:50`).
- `E501` (line too long) ignored (black owns line length).
- Per-file override: `tests/**` exempt from `ARG` (unused-argument) so fake stubs can match real signatures (`pyproject.toml:53-54`).

**Type checking:**
- `mypy` strict (`pyproject.toml:56-62`):
  ```toml
  strict = true
  warn_unused_ignores = true
  warn_redundant_casts = true
  disallow_untyped_defs = true
  no_implicit_optional = true
  ```
- `disallow_untyped_defs` means every function (including helpers) must be fully annotated.
- Third-party stubs missing for `googleapiclient.*`, `google.oauth2.*`, `google_auth_oauthlib.*`; ignored explicitly (`pyproject.toml:64-66`).
- Do not loosen mypy without asking (`CLAUDE.md`).

## Import Organization

Ruff `I` (isort) enforces order. Every module starts with `from __future__ import annotations` for forward-reference-free PEP 604 unions on Python 3.11.

**Order observed across `src/`:**
1. `from __future__ import annotations`
2. Standard library (`asyncio`, `logging`, `re`, `dataclasses`, `pathlib`).
3. Third-party (`httpx`, `pydantic`, `tenacity`, `openai`).
4. First-party absolute (`from evals.rubric import EvalRubric`).
5. First-party relative within the same package (`from .clients.protocols import LLMClient`, `from .models import Account`).

**Path Aliases:**
- None. The package is installed as `src` via hatch (`pyproject.toml:38-39`); imports use `src.foo` from test code and relative imports inside `src/`.

## Pydantic Usage

All domain types are frozen pydantic models inheriting from a shared base (`src/models.py:11-13`):

```python
class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
```

- `frozen=True` makes instances hashable and immutable; attempting `a.domain = "..."` raises `ValidationError` (asserted in `tests/unit/test_models.py:34-37`).
- `extra="forbid"` rejects unknown keys, catching prompt-drift where the writer invents fields.
- Numeric ranges enforced via `Field(ge=1, le=5)` on rubric axes and eval scores (`src/models.py:101-108, 134-138`).
- Custom `field_validator` for normalization: `Account._normalize_domain` strips protocols, `www.`, trailing slash, lowercases, and validates a dot is present (`src/models.py:18-28`).
- Tuples (not lists) for collections so frozen models stay hashable: `tech_signals: tuple[str, ...]`, `citations: tuple[Citation, ...]`, `supporting_indices: tuple[int, ...]`.
- Factory classmethods named `make` when a model needs lenient input coercion: `Citation.make(...)` builds via `model_validate` (`src/models.py:38-56`).
- Pipeline-relevant convenience constructors named after the resulting state: `ScoredAccount.unscoreable(...)` (`src/models.py:155-157`).

**Settings:**
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

**Strategy:**
- Domain-level failures degrade gracefully and surface in the output sheet: marked `unscoreable` with a human-readable `error` string, never silently dropped.
- Programmer errors (bad input, malformed config) raise immediately at process boundaries: `Account` validation, `Settings.require_for_pipeline`, `compute_total` on out-of-range rubric values.

**Patterns:**
- Log at WARNING for per-stage failures, never CRITICAL/ERROR for expected provider hiccups: `log.warning("enrich failed for %s: %s", account.domain, exc)` (`src/pipeline.py:60-64`).
- Catch narrow exception classes when parsing untrusted text: `except (TypeError, ValueError)` around int/float coercion (`src/enrich.py:122`, `src/score.py:82, 116`).
- LLM JSON parsing routed through `src/_json_utils.parse_json_object`, which returns `None` rather than raising; callers branch on `None` and log the truncated text (`src/enrich.py:108-111`, `src/score.py:64-66`).
- Citation guarantee: outreach validates `cited_justifications` against the `Enrichment.justifications` index set, drops indices not present, and returns an empty hook if zero remain (`src/outreach.py:67-83`). Hallucinated citations cannot reach the sheet.

## Logging

**Framework:** stdlib `logging`. Each module gets `log = logging.getLogger(__name__)` at the top.

**Root config:** Only configured in pipeline entrypoint (`src/pipeline.py:240`):
```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
```

**When to log:**
- `INFO` for lifecycle events (`loaded %d accounts`, `RUN_LIMIT=%d set; processing first %d of %d`).
- `WARNING` for recoverable per-account / per-call failures (parse failures, stage exceptions).
- Use `%` placeholders, not f-strings, so logging defers formatting if the level is disabled.
- Truncate untrusted strings before logging: `result.text[:200]` (`src/score.py:65`).

## Comments

**Style:**
- Comments explain WHY, never WHAT. Names are expected to carry the WHAT (`CLAUDE.md`).
- Multi-line docstrings on public protocol-like classes and any function whose contract isn't obvious from the signature. Example: `Justification` (`src/models.py:67-73`) documents the 1-based numbering protocol shared by writer and judge.
- Inline rationale comments are common above non-obvious branches:
  ```python
  # DeepSeek supports response_format guaranteed JSON; NVIDIA Build
  # generally does not, so only enable when on DeepSeek.
  json_mode = settings.resolved_provider == "deepseek"
  ```
  (`src/pipeline.py:149-151`)
- No "what" comments like `# loop over accounts`.

## Function Design

**Size:** Functions stay short; longest is `Enricher.enrich` at ~17 lines (`src/enrich.py:45-61`). Pure helpers (`_clip`, `_canonical`, `_clean_summary`) are typically 1-8 lines.

**Parameters:**
- Constructor injection for collaborators (LLM client, http client, settings). Tests rely on this to pass `FakeExa`, `FakeBrowserbase`, `FakeAnthropic`.
- Keyword-only after `*` for optional fields on factory classmethods: `Citation.make(url, source, *, title=None, snippet=None, retrieved_at=None)` (`src/models.py:38-46`).
- Default config fetched at instantiation if not passed: `config: ICPConfig | None = None` then `self._config = config or get_config()` (`src/score.py:49-51`, `src/outreach.py:40-42`).

**Return values:**
- Return `None` to signal a recoverable parse / validation failure (`Scorer.score`, `Enricher._extract_firmographics`).
- Return immutable models for successful results. No partial-state mutation.
- Tuples (not lists) returned from functions that yield collection fields on frozen models.

## Module Design

**Exports:**
- No `__all__` declarations. Module-private names lead with `_`; everything else is importable.
- Package `__init__.py` files (`src/__init__.py`, `src/clients/__init__.py`) are empty - no re-export barrels. Imports point at the source module: `from src.models import Account`.

**Protocols over inheritance:**
- External-collaborator contracts live in `src/clients/protocols.py` as `typing.Protocol` definitions (`ExaLike`, `BrowserbaseLike`, `LLMClient`). Real clients and fakes both satisfy these structurally without an explicit `class FakeExa(ExaLike):` declaration.

## Project Rules (from CLAUDE.md, observable in code)

- **No emojis in code or commit messages.** Confirmed across `src/`, `tests/`, and `git log` (`fix(score): require >=1 supporting index, ...`).
- **Conventional commits.** Recent history: `feat(...)`, `fix(...)`, `docs(...)`, `refactor(...)`. Scoped: `feat(sheets):`, `fix(judge):`.
- **No em-dashes in published markdown.** README, eval reports use commas / parentheses.
- **Public-repo discipline.** Code, prompts, and configs avoid naming specific verticals or vendors; ICP definition lives in `configs/icp.yaml`, referenced through `src/icp_config.py`.
- **Stack is locked.** Python 3.11+, `uv`, `httpx`, `pydantic` v2, `openai` SDK (OpenAI-compatible call shape used for both DeepSeek and NVIDIA Build), `tenacity`, `google-api-python-client`. Listed in `pyproject.toml:7-18`.
- **Citations must trace to retrieval.** Enforced in `OutreachGenerator.generate` by intersecting writer-claimed indices with markers actually present in the paragraph and with the `Enrichment.justifications` index set (`src/outreach.py:67-83`).
- **Empty enrichment becomes `unscoreable`, never faked.** `src/pipeline.py:66-67`.

---

*Convention analysis: 2026-05-14*
