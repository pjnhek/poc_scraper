# Technology Stack

**Analysis Date:** 2026-05-14

## Languages

**Primary:**
- Python `>=3.11` (`pyproject.toml:6`, target = `py311` in black/ruff/mypy) - all production and test code under `src/`, `tests/`, `evals/`

**Secondary:**
- YAML - ICP rubric configuration (`configs/icp.yaml`)
- Makefile - task runner (`Makefile`)

## Runtime

**Environment:**
- CPython 3.11+ asyncio (`src/pipeline.py` uses `asyncio.Semaphore` for the per-account fan-out)
- Pipeline is async end-to-end via `httpx.AsyncClient` and `openai.AsyncOpenAI`

**Package Manager:**
- `uv` (see `Makefile:4` `uv sync --extra dev`, `make run` -> `uv run python -m src.pipeline`)
- Lockfile: `uv.lock` (present, committed)
- Build backend: `hatchling` (`pyproject.toml:34-39`, wheel packages = `["src"]`)

## Frameworks

**Core:**
- `openai>=1.40.0` (`pyproject.toml:8`) - OpenAI-compatible async client. Used against DeepSeek and NVIDIA Build, not OpenAI itself. See `src/clients/nvidia_client.py:8`.
- `pydantic>=2.7.0` (`pyproject.toml:10`) - typed models in `src/models.py`
- `pydantic-settings>=2.3.0` (`pyproject.toml:11`) - env-driven `Settings` in `src/config.py:13`
- `httpx>=0.27.0` (`pyproject.toml:9`) - direct HTTP for Exa and Browserbase clients
- `tenacity>=8.3.0` (`pyproject.toml:13`) - retry policy on all three external clients

**Testing:**
- `pytest>=8.2.0`, `pytest-asyncio>=0.23.0` (`asyncio_mode = "auto"`, `pyproject.toml:69`)
- `pytest-cov>=5.0.0` - coverage, branch mode on `src/` (`pyproject.toml:76-78`)
- `respx>=0.21.0` - httpx mock transport for client tests
- Markers: `smoke` for opt-in live-API E2E (`pyproject.toml:71-73`)

**Build/Dev:**
- `black>=24.4.0` - formatter, line length 100, target py311 (`pyproject.toml:41-43`)
- `ruff>=0.4.0` - linter, rules `E,F,W,I,B,UP,SIM,ARG`, ignores `E501` (`pyproject.toml:45-54`)
- `mypy>=1.10.0` - strict mode, `disallow_untyped_defs`, `no_implicit_optional` (`pyproject.toml:56-66`). Google API modules are explicitly `ignore_missing_imports`.
- `pre-commit>=3.7.0` - hooks installed via `make install`

## Key Dependencies

**Critical:**
- `openai>=1.40.0` - all LLM calls (writer + judge), pointed at provider-specific base URLs (`src/clients/nvidia_client.py:17-18`)
- `httpx>=0.27.0` - Exa and Browserbase HTTP transport
- `tenacity>=8.3.0` - exponential backoff on 429/`APIError`/`HTTPError`
- `pydantic>=2.7.0` + `pydantic-settings>=2.3.0` - typed config and domain models

**Infrastructure:**
- `google-api-python-client>=2.130.0` - Google Sheets v4 API discovery client (`src/sheets.py:297-307`)
- `google-auth>=2.30.0`, `google-auth-oauthlib>=1.2.0` - service-account credentials for Sheets
- `pyyaml>=6.0` - load `configs/icp.yaml` rubric
- `python-dotenv>=1.0.1` - `.env` loading (consumed by `pydantic-settings`)
- Dev type stubs: `types-requests`, `types-PyYAML` (`pyproject.toml:30-31`)

## Configuration

**Environment:**
- `.env` (gitignored, present locally) loaded by `Settings` in `src/config.py:14-18`
- `.env.example` (committed) documents all required and optional vars
- Settings precedence: explicit env var > `.env` > defaults in `Settings` class
- Per-pipeline validation in `Settings.require_for_pipeline()` (`src/config.py:103-121`) - fails fast with a single message listing all missing keys

**Build:**
- `pyproject.toml` - single source for deps, tooling config, pytest config
- `Makefile` - `install`, `run`, `test`, `smoke`, `lint`, `format`, `typecheck`, `clean`, `eval-live`, `eval-fixtures`, `setup-sheet`
- `.pre-commit-config.yaml` - black, ruff (auto-fix), trailing-whitespace, end-of-file-fixer (CLAUDE.md split)

## Platform Requirements

**Development:**
- Python 3.11+
- `uv` installed (`brew install uv` or equivalent)
- Google service-account JSON at `./credentials.json` for Sheets writes
- At least one of `DEEPSEEK_API_KEY` or `NVIDIA_API_KEY`, plus `EXA_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` for `make run`

**Production:**
- Not a hosted service. Distributed as a CLI prototype. Run via `make run` against `inputs/accounts.csv`, output is a Google Sheet URL printed at the end of the run.

## LLM Provider Matrix

| Provider | Base URL | Writer default | Judge default | Reasoning toggle |
|---|---|---|---|---|
| DeepSeek (recommended) | `https://api.deepseek.com` (`src/clients/nvidia_client.py:18`) | `deepseek-v4-flash` (`src/config.py:49`) | `deepseek-v4-flash` with thinking enabled + `reasoning_effort=medium` (`src/config.py:50,53`) | `extra_body={"thinking": {"type": "enabled"}}` + top-level `reasoning_effort` |
| NVIDIA Build (free fallback) | `https://integrate.api.nvidia.com/v1` (`src/clients/nvidia_client.py:17`) | `minimaxai/minimax-m2.7` (`src/config.py:37`) | `bytedance/seed-oss-36b-instruct` (`src/config.py:38`) | `extra_body={"thinking_budget": <int>}`, `0` = disabled |

Auto-selection logic in `Settings.resolved_provider` (`src/config.py:83-89`): explicit `LLM_PROVIDER` wins, else DeepSeek if its key is set, else NVIDIA.

## Version Constraints (locked behaviors)

- mypy is `strict` and must stay strict (CLAUDE.md). Google API modules are the only allowed `ignore_missing_imports` override (`pyproject.toml:64-66`).
- Black line length 100 (`pyproject.toml:42`). Ruff matches (`pyproject.toml:46`).
- pytest `--strict-markers` (`pyproject.toml:74`) - new markers must be registered.
- `pytest-asyncio` runs in `auto` mode (`pyproject.toml:69`); async tests do not need explicit `@pytest.mark.asyncio`.

---

*Stack analysis: 2026-05-14*
