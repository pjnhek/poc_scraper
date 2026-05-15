# Testing Patterns

**Analysis Date:** 2026-05-14

## Test Framework

**Runner:**
- `pytest >=8.2.0` with `pytest-asyncio >=0.23.0` and `pytest-cov >=5.0.0` (`pyproject.toml:22-25`).
- Config in `pyproject.toml:68-74`:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  markers = [
      "smoke: end-to-end tests that hit live external APIs (opt-in via `make smoke`)",
  ]
  addopts = "-ra --strict-markers"
  ```
- `asyncio_mode = "auto"` means every `async def test_*` is auto-collected without an explicit `@pytest.mark.asyncio` decorator (though many tests use the decorator anyway for explicitness).
- `--strict-markers` rejects undeclared markers, so `smoke` is the only opt-in tag.

**Assertion Library:**
- Plain `assert`. `pytest.approx` for floats (`tests/unit/test_score_math.py:25`). `pytest.raises(ValidationError)` for pydantic rejection paths.

**HTTP Mocking:**
- `respx >=0.21.0` for `httpx` request interception (`pyproject.toml:25`). Used across `tests/functional/test_exa_client.py`, `tests/functional/test_browserbase_client.py`.

**Coverage:**
- `pytest-cov` configured against `src` with `branch = true` (`pyproject.toml:76-78`). No CI-enforced threshold.

**Run Commands (Makefile):**
```bash
make test            # uv run pytest -m "not smoke" - all offline tests
make smoke           # uv run pytest -m smoke -v   - opt-in live E2E
make typecheck       # uv run mypy src evals       - strict
make lint            # ruff check + black --check
make format          # black + ruff --fix
```

`make run` runs the pipeline; `make smoke` is now a separate target (not auto-chained) because both burn the same rate-limited LLM quota (`CLAUDE.md`).

## Test File Organization

**Location:**
- Separate `tests/` tree, mirroring `src/` module names. Co-location is not used.

**Layout:**
```
tests/
  __init__.py
  unit/
    __init__.py
    test_config.py            # Settings env resolution, provider fallback
    test_csv_io.py            # CSV parsing edge cases
    test_eval_table.py        # Eval rubric rendering
    test_icp_config.py        # ICP YAML loader
    test_json_utils.py        # parse_json_object code-fence + prose handling
    test_models.py            # Pydantic validation, frozen behavior, ranges
    test_score_math.py        # Pure rubric arithmetic
    test_sheets_inputs.py     # Inputs-tab projection
    test_sheets_rows.py       # Row builder
    test_sheets_rubric.py     # Rubric-tab projection
  functional/
    __init__.py
    test_browserbase_client.py # respx + http boundary
    test_contacts.py
    test_enrich.py            # Enricher with FakeExa/FakeBrowserbase/FakeAnthropic
    test_eval_rubric.py
    test_exa_client.py        # respx + retry behavior
    test_nvidia_client.py     # Fake OpenAI client, GenerationParams plumbing
    test_outreach.py          # Citation enforcement
    test_score.py
  integration/
    __init__.py
    test_pipeline.py          # process_account + run_pipeline with scripted LLM
    test_pipeline_failures.py # Per-stage failure isolation
    test_sheets_writer.py     # SheetsWriter with FakeService/FakeSpreadsheets
  smoke/
    __init__.py
    fixtures.csv              # 2 real domains
    test_e2e.py               # Live LLM + Exa + Browserbase + Sheets
```

**Naming:**
- `test_<module>.py` mirrors `src/<module>.py`.
- Test functions: `test_<behavior_under_test>` snake_case. Examples: `test_browserbase_fallback_when_about_text_thin`, `test_one_account_failure_does_not_kill_pipeline`, `test_rejects_blank_or_malformed_domain`.
- Optional grouping via plain test classes (no inheritance) when a model has several behaviors: `TestAccount`, `TestCitation`, `TestEvalScoreFlag` in `tests/unit/test_models.py`.

**Volume:** ~2,500 lines of tests across 17 test files (excluding `__init__.py`).

## Test Layers (5-layer strategy from CLAUDE.md)

| Layer | Directory | Network | Stubs | Examples |
|-------|-----------|---------|-------|----------|
| 1. Unit | `tests/unit/` | None | None - pure functions only | `test_score_math.py`, `test_models.py`, `test_json_utils.py` |
| 2. Functional | `tests/functional/` | None | Stubs at the API boundary of one module | `test_enrich.py` (Enricher + FakeExa/FakeBrowserbase/FakeAnthropic); `test_exa_client.py` (real ExaClient + respx HTTP mock) |
| 3. Integration | `tests/integration/` | None | Stubs at external boundaries; multiple internal modules wired together | `test_pipeline.py` (enrich + score + contacts + outreach + eval orchestrated); `test_sheets_writer.py` (full SheetsWriter against FakeService) |
| 4. Smoke E2E | `tests/smoke/` | Real | None | `test_e2e.py` - real DeepSeek/NVIDIA + Exa + Browserbase + optionally Sheets |
| 5. Edge cases | scattered across 1-3 | None | Same as parent layer | Empty enrichment, malformed CSV, blocked scrape, rate-limit retries, sub-threshold eval |

### Layer 1: Unit (pure functions, no mocks)

`tests/unit/test_score_math.py:23-67` calls `compute_total` and `config.verdict_for` directly:
```python
def test_weights_sum_to_one() -> None:
    config = get_config()
    assert sum(a.weight for a in config.axes.values()) == pytest.approx(1.0)

def test_weighted_average_matches_manual() -> None:
    config = get_config()
    rb = _rb(4, 3, 5, 2)
    weights = {n: a.weight for n, a in config.axes.items()}
    expected = round(4 * weights["support_volume"] + ..., 1)
    assert compute_total(rb) == expected
```

`tests/unit/test_models.py:20-37` exercises pydantic validators end-to-end on `Account`, `Citation`, `RubricBreakdown`, `Justification`. No I/O, no mocks - the models themselves are the unit.

### Layer 2: Functional (one module + boundary stubs)

`tests/functional/test_enrich.py:14-58` defines hand-rolled stub classes that match the Protocol shapes from `src/clients/protocols.py`:
```python
class FakeExa:
    def __init__(self, about=None, news=None) -> None:
        self.about = about or []
        self.news = news or []
        self.calls: list[str] = []
    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        self.calls.append(f"about:{domain}")
        return self.about
    async def search_news(self, domain: str, days: int = 90, num_results: int = 8) -> list[ExaResult]:
        ...

class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []
    async def synthesize(self, system, context, user_prompt, max_tokens=None) -> LLMResponse:
        self.calls.append({"system": system, "context": context, "user": user_prompt})
        return LLMResponse(text=self.text)
```

The `.calls` lists let assertions verify call patterns: `assert bb.calls == []  # didn't need fallback`.

For HTTP clients themselves, the boundary is `httpx`, so functional tests use `respx`:
```python
async with respx.mock(base_url=EXA_BASE_URL) as router:
    route = router.post("/search").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"results": []})]
    )
    ...
assert route.call_count == 2
```
(`tests/functional/test_exa_client.py:56-68`)

### Layer 3: Integration (multiple modules, stubs at edge)

`tests/integration/test_pipeline.py` wires `build_deps` with a `ScriptedAnthropic` whose `synthesize` dispatches on a substring of the `system` prompt:
```python
def _scripted_full_run() -> ScriptedAnthropic:
    return ScriptedAnthropic({
        "extract structured firmographics": '{"name":"Chime", ...}',
        "score companies against an ICP rubric": '{"support_volume":5, ...}',
        "propose the top 3 buyer personas": '[{"role_title":"VP CX", ...}]',
        "write one short outreach paragraph": '{"paragraph":"Saw your AI push [2] ...", "cited_justifications":[2]}',
        "LLM judge evaluating an outreach paragraph": '{"claims":[...], ...}',
    })
```
This is the canonical way to fake multi-call LLM flows. Substring keys are tied to actual system-prompt phrases used in `src/enrich.py`, `src/score.py`, `src/contacts.py`, `src/outreach.py`, `evals/rubric.py` - if a system prompt is reworded, the script lookup misses and `ScriptedAnthropic` raises `AssertionError(f"unscripted call: {system[:80]}")`.

`tests/integration/test_sheets_writer.py:21-92` builds a `FakeService -> FakeSpreadsheets -> FakeValues` shape that matches the googleapiclient builder pattern, capturing `update_calls`, `clear_calls`, `create_calls`, `batch_calls` for assertion.

### Layer 4: Smoke (`make smoke`, opt-in)

`tests/smoke/test_e2e.py` is gated by a module-scoped autouse fixture that skips when API keys are absent (`tests/smoke/test_e2e.py:34-40`):
```python
@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_keys() -> None:
    if not _all_required_keys_set():
        pytest.skip("smoke tests require NVIDIA_API_KEY, EXA_API_KEY, ...")
```
Marked `pytestmark = pytest.mark.smoke` at module level, so `pytest -m "not smoke"` (the default in CI and `make test`) skips the file entirely. Uses `tests/smoke/fixtures.csv` (2 domains) and asserts at least one scored result.

### Layer 5: Edge cases

Distributed across the layers above, not a directory of their own:
- Empty enrichment: `test_empty_enrichment_when_no_data` (`tests/functional/test_enrich.py:204-213`).
- Browserbase blocked: `test_browserbase_blocked_falls_back_to_exa_text` (`tests/functional/test_enrich.py:189-200`).
- Malformed LLM JSON: `test_malformed_llm_json_returns_none_firmographics`, `test_handles_json_wrapped_in_code_fences` (`tests/functional/test_enrich.py:217-238`).
- Per-stage pipeline failure isolation: `tests/integration/test_pipeline_failures.py` (`FailingAnthropic` raises on a specific system prompt substring).
- Sub-threshold eval coloring: `test_flagged_row_keeps_verdict_color_with_red_text_on_eval_cell` (`tests/integration/test_sheets_writer.py:161-184`).
- Rate-limit retries: `test_search_retries_then_succeeds`, `test_search_gives_up_after_max_attempts` (`tests/functional/test_exa_client.py:56-78`).
- Domain normalization / rejection: `tests/unit/test_models.py:20-37`.

## Mocking

**Framework:**
- No `unittest.mock`. Hand-rolled stub classes implementing the `Protocol` interfaces from `src/clients/protocols.py`. This keeps mypy strict happy and avoids the typical "mock returns Mock returns Mock" debugging trap.
- `respx` for `httpx` request interception when the unit under test is the HTTP client itself.

**Patterns:**
- Same fake class is redefined per test file (FakeExa/FakeBrowserbase/FakeAnthropic appear in `test_enrich.py`, `test_pipeline.py`, `test_pipeline_failures.py`). They are intentionally minimal duplicates rather than a shared `conftest.py` fixture - each file scopes its fake to the exact method set it needs.
- Stubs capture call history on a public `self.calls: list[...]` attribute for behavioral assertions.
- `ScriptedAnthropic` pattern for multi-call orchestration: dispatch on a substring of the system prompt (`tests/integration/test_pipeline.py:36-48`).
- `FailingAnthropic` pattern for failure injection: raise when a specific system prompt substring is seen (`tests/integration/test_pipeline_failures.py:34-43`).
- googleapiclient builder shape replicated with `FakeService -> FakeSpreadsheets -> FakeValues -> FakeRequest`, each exposing the methods the production code calls (`tests/integration/test_sheets_writer.py:21-91`).

**What to Mock:**
- External network boundaries: Exa, Browserbase, the OpenAI-compatible LLM endpoint, Google Sheets.
- Stable third-party SDK shapes (the OpenAI Python client) via `_FakeOpenAI/_FakeChat/_FakeCompletions` (`tests/functional/test_nvidia_client.py:10-42`).

**What NOT to Mock:**
- Pydantic models. Construct real instances.
- Pure helpers (`compute_total`, `_clean_summary`, `_canonical`, `parse_json_object`). Call them directly with crafted inputs.
- `src/icp_config.get_config()`. Reads `configs/icp.yaml` at import-time; tests use the real config.

## Fixtures and Factories

**Style:** Inline factory helpers per test file, no shared `conftest.py`.

Examples:
- `_rb(sv, ai, stage, ch)` builds a `RubricBreakdown` with placeholder reason strings (`tests/unit/test_score_math.py:10-20`).
- `_exa_about(text=...)` and `_exa_news(url=...)` build `ExaResult` instances with sane defaults (`tests/functional/test_enrich.py:61-76`).
- `_scored(domain, flag)` builds a complete `ScoredAccount` graph (`tests/integration/test_sheets_writer.py:94-127`).

**Smoke fixtures:** `tests/smoke/fixtures.csv` holds 2 real domains used for the live run.

## Common Patterns

**Async testing:** `asyncio_mode = "auto"` plus explicit `@pytest.mark.asyncio` decorators on async tests. Coroutine fakes (`async def render`, `async def synthesize`) match production signatures so `mypy --strict` doesn't choke.

**Error testing:**
```python
with pytest.raises(ValidationError):
    Account(domain="")
```
(`tests/unit/test_models.py:27-32`)

**Behavioral assertion via stub `.calls`:**
```python
assert bb.calls == ["https://notion.so/about"]
assert llm.calls == []  # we don't call LLM with no context
```
(`tests/functional/test_enrich.py:118, 213`)

**Substring assertion on emitted prompts** (verifies prompt assembly without coupling to wording):
```python
assert "<news>...</news>" in call["messages"][1]["content"]
assert "score the account" in call["messages"][1]["content"]
```
(`tests/functional/test_nvidia_client.py:59-60`)

## CI vs Pre-commit Split

**Pre-commit** (`.pre-commit-config.yaml`) - fast, runs on every commit:
- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict` (pre-commit-hooks v4.6.0).
- `black` (rev 26.3.1).
- `ruff-check --fix` (rev v0.15.12).

**Not in pre-commit:** mypy, pytest. Comment at the top says: "mypy + pytest run in CI (see .github/workflows/ci.yml)."

**CI** (`.github/workflows/ci.yml`) - thorough, runs on push and PR to `main`:
1. `astral-sh/setup-uv@v3` with cache, then `uv python install 3.11`.
2. `uv sync --extra dev`.
3. `uv run black --check src tests evals`.
4. `uv run ruff check src tests evals`.
5. `uv run mypy src evals` (strict).
6. `uv run pytest -m "not smoke"` - offline tests only. Smoke is deliberately skipped to avoid burning credits and flakiness from rate limits.

## Coverage

**Coverage source:** `src` with branch coverage enabled (`pyproject.toml:76-78`).
**Enforced threshold:** None in CI. `pytest-cov` is installed but not auto-invoked by `make test`.

**Coverage hot spots** (high test density):
- `src/models.py` - `tests/unit/test_models.py` (145 lines).
- `src/enrich.py` - `tests/functional/test_enrich.py` (251 lines).
- `src/pipeline.py` orchestration - `tests/integration/test_pipeline.py` + `test_pipeline_failures.py` (~300 lines combined).
- `src/sheets.py` - `tests/integration/test_sheets_writer.py` (244 lines) + 3 unit files (`test_sheets_inputs.py`, `test_sheets_rows.py`, `test_sheets_rubric.py`).

**Gaps:**
- `src/contacts.py` covered by `tests/functional/test_contacts.py` (83 lines) but not by an integration test that exercises score-to-contact handoff with a malformed persona list.
- `evals/run_eval.py` and `evals/run_live.py` (eval entry points) have no test file; `evals/rubric.py` is exercised through `tests/functional/test_eval_rubric.py` and the integration scripted run.
- No coverage of the actual `setup_sheet` script (`scripts/setup_sheet.py`).
- Smoke E2E does not verify outreach paragraph quality; it only asserts `1 <= score.total <= 5` and that `eval_score is not None`.

---

*Testing analysis: 2026-05-14*
