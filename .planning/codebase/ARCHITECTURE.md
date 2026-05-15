<!-- refreshed: 2026-05-14 -->
# Architecture

**Analysis Date:** 2026-05-14

## System Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                            Inputs                                       │
│   `inputs/accounts.csv` (domain column)   `configs/icp.yaml` (rubric)   │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Entry: `src/pipeline.py::main`                       │
│   - load Settings (`src/config.py`)                                     │
│   - read accounts (`src/csv_io.py`)                                     │
│   - build httpx + LLM clients + Deps                                    │
│   - asyncio.gather over accounts, Semaphore(concurrency=5)              │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ per account, in `process_account()`
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 1: enrich    `src/enrich.py::Enricher.enrich`                    │
│    Exa about+news -> Browserbase fallback -> firmographics LLM call ->  │
│    numbered `Justification[]`                                            │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ Enrichment (pydantic, frozen)
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 2: score     `src/score.py::Scorer.score`                        │
│    writer LLM scores 4 axes against `configs/icp.yaml`, returns         │
│    `supporting_indices` referencing the numbered justifications         │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ ICPScore
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 3: contacts  `src/contacts.py::ContactExtractor.extract`         │
│    writer LLM proposes top-3 buyer personas grounded in firmographics   │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ tuple[Contact, ...]
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 4: outreach  `src/outreach.py::OutreachGenerator.generate`       │
│    one paragraph per contact, [N] markers cross-checked against         │
│    `Enrichment.justifications`; unsupported hooks dropped to ""         │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ tuple[OutreachHook, ...]
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 5: eval (sidecar)   `evals/rubric.py::EvalRubric.evaluate_account`│
│    judge LLM (DeepSeek thinking / NVIDIA reasoning) decomposes each     │
│    hook into atomic claims; groundedness = cited / max(total, 3) * 5    │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ ScoredAccount (status + score + hooks + eval)
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Sink: `src/sheets.py::SheetsWriter.write`                              │
│    creates/reuses spreadsheet, refreshes `Rubric` + `Inputs` tabs,      │
│    appends a new `run-YYYYMMDD-HHMMSS` results tab, applies verdict     │
│    background colors + red text on flagged eval_groundedness cells     │
└────────────────────────────────────────────────────────────────────────┘
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

**Overall:** Linear async pipeline with dependency injection.

**Key Characteristics:**
- Each stage is a small class with a single async method, constructor-injected dependencies (LLM client, Exa, Browserbase, ICP config). No globals threaded through the pipeline.
- All cross-stage values are frozen pydantic models (`src/models.py`) with `extra="forbid"`, so a schema drift fails loudly.
- Per-stage exception isolation in `process_account` (`src/pipeline.py:57`): a failed enrich marks the account `unscoreable`; a failed score does the same; outreach failures drop a single hook, never the whole row.
- Citation handling is index-based, not URL-based. `Enrichment.justifications` is numbered 1..N once in `enrich._number_justifications` and that same list is shown to writer, judge, and the sheet. Claims are validated by index membership.
- Provider-agnostic LLM client. `NvidiaClient` speaks OpenAI's wire format and is configured per-provider in `_build_writer` / `_build_judge` (`src/pipeline.py:147`, `:166`).

## Layers

**Entry / orchestration layer:**
- Purpose: load config, build deps, fan out work, write sink.
- Location: `src/pipeline.py`
- Depends on: every stage module, clients, csv_io, sheets.
- Used by: `make run`, `evals/run_live.py`.

**Stage layer (pure business logic):**
- Purpose: one async class per pipeline step.
- Location: `src/enrich.py`, `src/score.py`, `src/contacts.py`, `src/outreach.py`, `evals/rubric.py`.
- Depends on: protocol-typed clients only; never on concrete httpx or openai SDK objects.
- Used by: `src/pipeline.py::build_deps` and tests with stub clients.

**Client layer (I/O):**
- Purpose: HTTP / SDK calls to external services, with retry policy and concurrency caps.
- Location: `src/clients/`.
- Depends on: httpx, openai, tenacity.
- Used by: stages, via protocol types in `src/clients/protocols.py`.

**Config layer:**
- Purpose: typed settings (env) and rubric (yaml).
- Location: `src/config.py`, `src/icp_config.py`, `configs/icp.yaml`.
- Used by: pipeline entry, stages that need the rubric (score, contacts, outreach, eval rubric), sheets (rubric tab).

**Sink layer:**
- Purpose: render `ScoredAccount` list into a Google Sheet with formatting.
- Location: `src/sheets.py`.
- Depends on: `google-api-python-client`, `google-auth`.
- Used by: pipeline entry only.

**Models layer:**
- Purpose: shared schema across all layers.
- Location: `src/models.py`.
- Imported by: every other module.

## Data Flow

### Primary Request Path (one account)

1. `main` reads `inputs/accounts.csv` (`src/pipeline.py:202`).
2. `run_pipeline` fans out with `asyncio.Semaphore(concurrency)` (`src/pipeline.py:123`).
3. `process_account` calls `Enricher.enrich` (`src/pipeline.py:59`).
4. `Enricher` queries Exa about (`src/enrich.py:64`), falls back to Browserbase if thin (`src/enrich.py:67`), queries Exa news, extracts firmographics via writer LLM (`src/enrich.py:100`), and numbers justifications (`src/enrich.py:127`).
5. `Scorer.score` builds rubric prompt from `ICPConfig`, calls writer LLM, validates `supporting_indices` against `Enrichment.justifications` (`src/score.py:53`).
6. `ContactExtractor.extract` calls writer LLM for top-3 personas (`src/contacts.py:34`).
7. For each contact, `OutreachGenerator.generate` calls writer LLM, parses `[N]` markers, intersects claimed indices with markers actually present in the paragraph (`src/outreach.py:71`); paragraph blanked if no valid citation.
8. `EvalRubric.evaluate_account` runs the judge over each non-empty hook, averaging groundedness / icp_relevance / personalization (`evals/rubric.py:88`).
9. Result is a frozen `ScoredAccount` returned to `main`.
10. `SheetsWriter.write` refreshes `Rubric` + `Inputs` tabs, adds `run-YYYYMMDD-HHMMSS` tab, writes values, applies verdict colors and eval-flag formatting (`src/sheets.py:309`).

### Eval Sidecar (offline calibration)

1. `evals/run_eval.py` loads `evals/labeled.jsonl`.
2. Builds a synthetic `OutreachHook` per row.
3. Calls `EvalRubric.evaluate_hook` with only the judge client.
4. Prints a markdown table and mean-absolute-error vs. hand labels.

### Live Eval (`make eval-live`)

`evals/run_live.py` reuses `build_deps` + `process_account` over a small slice of `inputs/accounts.csv`, then flattens hooks into a markdown table. No sheets writer.

**State Management:**
- No mutable global state in the hot path. `get_settings()` and `get_config()` are `@lru_cache(maxsize=1)` singletons over immutable pydantic models; safe to call from any stage.

## Key Abstractions

**`Justification` (numbered evidence):**
- Purpose: a single retrieved snippet with a stable 1-based index, threaded through writer, judge, and sheet.
- Defined: `src/models.py:66` (with docstring explaining the contract).
- Built: `src/enrich.py:127` (`_number_justifications`).
- Consumed by: `src/score.py` (`supporting_indices`), `src/outreach.py` (`cited_indices`), `evals/rubric.py` (claim-to-index mapping), `src/sheets.py` (citation rendering).

**`Deps` (DI bundle):**
- Purpose: hand the pipeline a single immutable struct holding every stage's collaborator.
- Defined: `src/pipeline.py:33`.
- Constructed: `build_deps()` (`src/pipeline.py:42`) — also used by `evals/run_live.py`.

**LLM `Protocol`s:**
- Purpose: stages depend on structural types, not concrete client classes.
- Defined: `src/clients/protocols.py`.
- Pattern: tests pass plain Python objects matching `LLMClient` / `ExaLike` / `BrowserbaseLike`.

**`ICPConfig`:**
- Purpose: edit the rubric, retarget the vertical; both writer and judge prompts read from this file.
- Defined: `src/icp_config.py`.
- Source of truth: `configs/icp.yaml`.

## Entry Points

**`make run` / `python -m src.pipeline`:**
- Location: `src/pipeline.py:239`.
- Triggers: operator command.
- Responsibilities: full pipeline -> Google Sheet.

**`make eval-live` / `python -m evals.run_live`:**
- Location: `evals/run_live.py:171`.
- Triggers: operator command.
- Responsibilities: live pipeline + judge over 2-3 domains, markdown table to stdout.

**`make eval-fixtures` / `python -m evals.run_eval`:**
- Location: `evals/run_eval.py:136`.
- Triggers: operator command.
- Responsibilities: judge-vs-hand-labels calibration, markdown table to stdout.

**`make setup-sheet` / `python -m scripts.setup_sheet`:**
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

**What happens:** Writer LLM occasionally tries to paste raw URLs into the outreach paragraph instead of `[N]` markers.
**Why it's wrong:** Citations would no longer be checkable by the judge or by sheet rendering, and the paragraph looks spammy to a reader.
**Do this instead:** `OutreachGenerator` strips URLs (`URL_RE.sub("", paragraph)`, `src/outreach.py:82`) and only accepts indices that appear as `[N]` markers in the paragraph (`_markers_in_paragraph`, `src/outreach.py:100`). If no valid marker survives the cross-check, the paragraph is blanked.

### Failing the run on a single bad domain

**What happens:** A retrieval failure on one account aborts everything.
**Why it's wrong:** A 50-domain run is wasted because one domain's about page is blocked.
**Do this instead:** Wrap each stage in `try/except` inside `process_account` (`src/pipeline.py:58-89`) and either return `ScoredAccount.unscoreable` or drop a single hook. Never re-raise out of `process_account`.

### Fabricated firmographics on empty context

**What happens:** LLM hallucinates a name/industry when Exa returned nothing.
**Why it's wrong:** Silently fakes data the sales team would act on.
**Do this instead:** `Enrichment.is_empty` short-circuits to `unscoreable` in `process_account` (`src/pipeline.py:66`), and the sheet shows the row's `status` column. The writer's firmographics prompt also says "do not invent data; use null".

### Numeric 1-10 judges

**What happens:** Asking the judge for a 1-10 score.
**Why it's wrong:** 1-10 numeric judges drift run-to-run (NeMo guidance, called out in `CLAUDE.md`).
**Do this instead:** All judge axes are 1-5 categorical (`src/models.py::EvalScore`, `evals/rubric.py`), and groundedness is derived deterministically from a claim-decomposition count rather than asked directly.

## Error Handling

**Strategy:** isolate failures at the stage boundary; never let one account or one hook bring down the run.

**Patterns:**
- Per-stage `try/except` in `process_account` (`src/pipeline.py:57`), logging at WARN, continuing with a degraded `ScoredAccount` or empty hook tuple.
- Tenacity retries with exponential backoff inside each client (`src/clients/nvidia_client.py`, `src/clients/exa_client.py`, `src/clients/browserbase_client.py`).
- Tolerant JSON parsing (`src/_json_utils.py`); parse failures return `None` and the stage degrades, not the whole pipeline.
- Empty/invalid enrichment becomes `ScoredAccount.unscoreable` with an explicit `error` field surfaced in the sheet.
- Sub-threshold groundedness flags the cell red but does not drop the row (`SheetsWriter._apply_eval_flag_text`, `src/sheets.py:431`).

## Cross-Cutting Concerns

**Logging:** stdlib `logging`, configured in each entry point's `if __name__ == "__main__"` block with `format="%(asctime)s %(levelname)s %(name)s %(message)s"`. Each module gets `log = logging.getLogger(__name__)`. Stages log at WARN on failure, INFO on milestones.

**Validation:** pydantic models do field-level validation on construction (e.g. `Account._normalize_domain` lowercases and strips schemes, `src/models.py:18`). Index validation for `supporting_indices` and `cited_indices` is done explicitly against `Enrichment.justifications` in `score.py` and `outreach.py`.

**Authentication:** Google Sheets uses a service-account JSON at `GOOGLE_APPLICATION_CREDENTIALS` (default `./credentials.json`). LLM and Exa and Browserbase use API keys from env. `Settings.require_for_pipeline` (`src/config.py:103`) fails fast at startup with a list of missing variables.

**Concurrency / rate limits:** two layers — `pipeline_concurrency` semaphore over accounts, and `llm_max_in_flight` per-client cap on simultaneous LLM requests. Tenacity backs off on 429s inside each client.

---

*Architecture analysis: 2026-05-14*
