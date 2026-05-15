# Codebase Structure

**Analysis Date:** 2026-05-14

## Directory Layout

```
poc_scraper/
├── Makefile                      # canonical entry points (install, run, eval, test, lint, typecheck)
├── pyproject.toml                # uv project, deps, tool config (black, ruff, mypy strict, pytest)
├── uv.lock                       # pinned dependency lockfile
├── README.md                     # operator-facing overview
├── CLAUDE.md                     # project-specific guidance for Claude
├── credentials.json              # Google service-account key (gitignored, do not read)
├── configs/
│   └── icp.yaml                  # ICP rubric: buyer + seller description, axes, weights, verdicts
├── inputs/
│   └── accounts.csv              # input domain list (single `domain` column)
├── src/                          # pipeline source
│   ├── __init__.py
│   ├── pipeline.py               # asyncio orchestration, main(), Deps, client builders
│   ├── config.py                 # pydantic-settings Settings (env -> typed config)
│   ├── icp_config.py             # ICPConfig pydantic model, loads configs/icp.yaml
│   ├── models.py                 # frozen pydantic models for every cross-stage value
│   ├── csv_io.py                 # read_accounts() parses inputs/accounts.csv
│   ├── enrich.py                 # Enricher: Exa + Browserbase + firmographics LLM call
│   ├── score.py                  # Scorer: ICP rubric writer LLM call
│   ├── contacts.py               # ContactExtractor: top-3 personas writer LLM call
│   ├── outreach.py               # OutreachGenerator: grounded paragraphs with [N] citations
│   ├── sheets.py                 # SheetsWriter: Google Sheets sink (Results + Rubric + Inputs tabs)
│   ├── _json_utils.py            # tolerant JSON parsing for LLM outputs
│   └── clients/
│       ├── __init__.py
│       ├── nvidia_client.py      # OpenAI-compatible LLM client (NVIDIA Build + DeepSeek)
│       ├── exa_client.py         # Exa about + last-90-day news search
│       ├── browserbase_client.py # JS-rendered fallback for thin Exa pages
│       └── protocols.py          # ExaLike / BrowserbaseLike / LLMClient Protocols
├── evals/                        # LLM-as-judge sidecar
│   ├── __init__.py
│   ├── rubric.py                 # EvalRubric: claim-decomposition groundedness + icp + personalization
│   ├── run_eval.py               # offline: judge vs. labeled.jsonl, mean abs error
│   ├── run_live.py               # live: real pipeline over a few domains, judge each hook
│   └── labeled.jsonl             # hand-labeled calibration examples
├── tests/
│   ├── __init__.py
│   ├── unit/                     # pure functions: rubric math, csv, models, sheet rows, json utils
│   ├── functional/               # one module under test, stubs at API boundary
│   ├── integration/              # multi-module wired together, stubs at external boundaries
│   └── smoke/                    # opt-in e2e (real APIs), fixtures.csv, pytest -m smoke
├── scripts/
│   ├── __init__.py
│   └── setup_sheet.py            # one-shot: create sheet, share with operator, write GOOGLE_SHEET_ID to .env
├── .github/
│   └── workflows/
│       └── ci.yml                # black --check, ruff, mypy --strict, pytest (smoke excluded)
└── .planning/
    └── codebase/                 # this directory: architecture and structure docs
```

## Directory Purposes

**`src/`:**
- Purpose: the entire pipeline (orchestration + stages + clients + sink + models + config).
- Contains: one module per stage, plus a `clients/` subpackage for I/O.
- Key files: `pipeline.py` (entry + DI), `models.py` (schema), `enrich.py` / `score.py` / `contacts.py` / `outreach.py` (stages), `sheets.py` (sink).

**`src/clients/`:**
- Purpose: every outbound HTTP/SDK call lives here. Stages depend only on the `Protocol`s in `protocols.py`.
- Contains: one client per external service plus the structural-typing layer.
- Key files: `nvidia_client.py` (OpenAI-compatible, used for both NVIDIA Build and DeepSeek), `exa_client.py`, `browserbase_client.py`, `protocols.py`.

**`configs/`:**
- Purpose: editable, vertical-specific configuration that should not live in code.
- Contains: `icp.yaml` (buyer + seller description, axis weights, anchors, verdict thresholds, eval flag threshold).
- Used by: `src/icp_config.py`, which both the writer prompts and the judge prompt read from.

**`inputs/`:**
- Purpose: runtime input data.
- Contains: `accounts.csv` (header: `domain`).
- Consumed by: `src/csv_io.py::read_accounts`.

**`evals/`:**
- Purpose: LLM-as-judge layer plus the two ways to run it (offline calibration, live over real pipeline output).
- Contains: `rubric.py` (the judge), `run_eval.py` (vs labeled fixtures), `run_live.py` (vs live pipeline), `labeled.jsonl` (calibration set).
- Imports from `src/` but is not imported by `src/` (the pipeline does `from evals.rubric import EvalRubric` in one place, `src/pipeline.py:9`).

**`tests/`:**
- Purpose: five-layer test pyramid per `CLAUDE.md`.
- Contains:
  - `unit/`: pure functions, no I/O.
  - `functional/`: one module, stubs at the API boundary.
  - `integration/`: multiple modules wired, stubs at external boundaries.
  - `smoke/`: opt-in e2e against real APIs, gated by `pytest -m smoke`.

**`scripts/`:**
- Purpose: one-shot operator tools that are not part of the pipeline hot path.
- Contains: `setup_sheet.py` (create + share a workbook, persist its ID).

**`.github/workflows/`:**
- Purpose: CI configuration.
- Key files: `ci.yml`.
- CI runs the slower checks: `black --check`, `ruff`, `mypy --strict`, and `pytest -m "not smoke"`.

**`.planning/codebase/`:**
- Purpose: codebase analysis docs consumed by other tooling.
- Generated: by hand / by GSD codebase mapper.

## Key File Locations

**Entry Points:**
- `src/pipeline.py`: `make run` -> `python -m src.pipeline` -> `main()` at line 198.
- `evals/run_live.py`: `make eval-live` -> live pipeline + judge over a few domains.
- `evals/run_eval.py`: `make eval-fixtures` -> judge vs `evals/labeled.jsonl`.
- `scripts/setup_sheet.py`: `make setup-sheet` -> create + persist Google Sheet ID.

**Configuration:**
- `pyproject.toml`: dependencies, black, ruff, mypy strict, pytest config.
- `configs/icp.yaml`: ICP rubric (buyer description, axes, weights, verdicts, eval flag threshold).
- `.env`: secrets and per-run knobs (`DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, `EXA_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `GOOGLE_SHEET_ID`, `RUN_LIMIT`, `LLM_PROVIDER`). Loaded by `src/config.py::Settings` via pydantic-settings.
- `credentials.json`: Google service-account JSON for Sheets API.
- `Makefile`: canonical entry points for every operator action.

**Core Logic:**
- `src/pipeline.py`: orchestration, DI, async fan-out, exception isolation.
- `src/models.py`: pydantic schema for every cross-stage value (`Account`, `Enrichment`, `Justification`, `ICPScore`, `Contact`, `OutreachHook`, `EvalScore`, `ScoredAccount`).
- `src/enrich.py` / `src/score.py` / `src/contacts.py` / `src/outreach.py`: one stage each.
- `evals/rubric.py`: judge stage (claim-decomposition groundedness).
- `src/sheets.py`: sink — Results + Rubric + Inputs tabs, verdict colors, flag formatting.

**Testing:**
- `tests/unit/`: 9 test files covering pure functions (config, csv, json utils, models, score math, sheet builders, icp config, eval table builder).
- `tests/functional/`: 7 test files (one per stage + each client).
- `tests/integration/`: pipeline happy path, pipeline failure modes, sheets writer.
- `tests/smoke/`: `test_e2e.py` + `fixtures.csv`, opt-in via `make smoke`.

## Naming Conventions

**Files:**
- snake_case Python modules: `csv_io.py`, `nvidia_client.py`, `icp_config.py`.
- Private/internal helpers prefixed with `_`: `src/_json_utils.py`.
- Test files mirror the module they test: `tests/functional/test_enrich.py` tests `src/enrich.py`; `tests/unit/test_score_math.py` tests the pure math in `src/score.py`.

**Directories:**
- lowercase, no separators: `src`, `evals`, `configs`, `inputs`, `scripts`, `tests`.

**Modules:**
- One class per stage, named after the verb (`Enricher`, `Scorer`, `ContactExtractor`, `OutreachGenerator`).
- One class per client, named after the service (`NvidiaClient`, `ExaClient`, `BrowserbaseClient`).
- Builders are module-level functions: `build_deps`, `build_writer_client`, `build_judge_client`, `build_rows`, `build_rubric_rows`, `build_inputs_rows`.

## Where to Add New Code

**New pipeline stage:**
- Implementation: new file under `src/`, one class with an async method, dependencies constructor-injected (LLM client, Exa, Browserbase, ICPConfig).
- Wire-up: add a field to `Deps` (`src/pipeline.py:33`), construct in `build_deps` (`src/pipeline.py:42`), call from `process_account` (`src/pipeline.py:57`).
- Tests: `tests/functional/test_<stage>.py` with stub clients; add a happy-path assertion in `tests/integration/test_pipeline.py`.

**New external service / client:**
- Implementation: `src/clients/<service>_client.py`. Use `httpx.AsyncClient` injected via constructor; wrap calls in tenacity retries; add a frozen dataclass for the response shape.
- Protocol: add a `Protocol` to `src/clients/protocols.py` so stages depend on structural typing, not the concrete class.
- Settings: add fields to `src/config.py::Settings` and to `require_for_pipeline()` if mandatory.
- Tests: `tests/functional/test_<service>_client.py` using `respx` for HTTP fakes.

**New model / schema field:**
- Implementation: edit `src/models.py`. Models are frozen and `extra="forbid"`, so add the field, default it if optional, and update every producer/consumer the type checker flags.
- Tests: `tests/unit/test_models.py`.

**New ICP rubric axis / verdict:**
- Edit `configs/icp.yaml`. If the axis set changes, also update the `expected` set in `ICPConfig._check_axes` (`src/icp_config.py:42`) and the corresponding fields on `RubricBreakdown` (`src/models.py:100`) and `_build_score_system` (`src/score.py:13`).
- Tests: `tests/unit/test_icp_config.py`, `tests/unit/test_score_math.py`.

**New sheet column:**
- Edit `HEADERS` tuple in `src/sheets.py:14` and the row builder in `_build_row` (`src/sheets.py:63`).
- Tests: `tests/unit/test_sheets_rows.py`.

**New eval axis:**
- Edit `EvalScore` in `src/models.py:133`, the judge prompt in `evals/rubric.py::_build_eval_system`, and the parser in `EvalRubric.evaluate_hook`.
- Tests: `tests/functional/test_eval_rubric.py`, `tests/unit/test_eval_table.py`.

**New operator script:**
- Place under `scripts/`. Add a `make` target in `Makefile`. Scripts may import from `src/` but should not be imported by `src/`.

## Special Directories

**`.venv/`:**
- Purpose: uv-managed virtualenv.
- Generated: yes (`uv sync --extra dev` via `make install`).
- Committed: no.

**`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`:**
- Purpose: tool caches.
- Generated: yes.
- Committed: no. `make clean` removes them.

**`runs/`:**
- Purpose: ad-hoc local run artifacts (referenced in `make clean`).
- Generated: yes.
- Committed: no.

**`credentials.json`:**
- Purpose: Google service-account key for the Sheets API.
- Generated: by the operator out-of-band; not by code.
- Committed: no. **Never read or quote.**

**`.env`:**
- Purpose: secrets and per-run knobs.
- Generated: by the operator (and by `scripts/setup_sheet.py` for `GOOGLE_SHEET_ID`).
- Committed: no. **Never read or quote.**

---

*Structure analysis: 2026-05-14*
