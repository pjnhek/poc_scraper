# Stack Research

**Domain:** Groundedness / citation verification + LLM-as-judge eval tooling for a small-team Python LLM POC (brownfield, demo-ready v1 milestone)
**Researched:** 2026-05-14
**Confidence:** HIGH on rejects (well-verified upstream behavior), MEDIUM-HIGH on picks (versions verified via PyPI; integration patterns verified against official docs)

## Scope and constraint reminder

This research is bounded by the locked stack in `CLAUDE.md` and the existing inventory in `.planning/codebase/STACK.md`:

- Python 3.11+, `uv`, strict mypy, `pyproject.toml` as single source of truth
- `openai>=1.40.0` async client pointed at DeepSeek (default) or NVIDIA Build (fallback) via OpenAI-compatible base URLs
- `pydantic>=2.7`, `httpx>=0.27`, `tenacity>=8.3`
- `pytest>=8.2` + `pytest-asyncio` (auto mode) + `respx`
- `google-api-python-client` for Sheets, service-account auth

The question is **not** "rebuild eval/groundedness" but "which thin, judge-agnostic libraries close the gap that `evals/rubric.py` and `src/outreach.py` already opened, without dragging in a framework that owns model routing, dataset state, or the Sheets surface."

The demo-killer that drives every recommendation: an ungrounded outreach claim that traces to nothing, plus eval numbers that read as ad-hoc rather than rigorous.

## Recommended Stack

### Core additions (the short list)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `rapidfuzz` | `3.14.5` (2026-04-07) | Sentence-to-evidence string match for citation verification at write time and at judge time | Pure C++/Python, no network, no model, deterministic, MIT, 100x faster than `python-Levenshtein`. The right primitive for "does this claim's substring appear in any cited Exa snippet" - the exact failure mode the milestone is hardening. Replaces hand-rolled string comparison in `src/outreach.py` and gives the judge an evidence-overlap signal independent of the LLM. |
| `jinja2` | `3.1.6` (2025-03-05) | Templated judge prompts + eval-report rendering (HTML/Markdown) | The eval narrative artifact (PROJECT.md "Active" item 4) needs to be regenerated from `evals/labeled.jsonl` results without hand-editing. Jinja is already a transitive dep of most Python tooling; treating it as a first-class dep keeps prompt templates and report templates in one engine. Avoids f-string sprawl in `evals/rubric.py`. |
| `great-tables` | `0.21.0` (2026-03-03) | Per-judge-axis score tables rendered to HTML/PNG for the README and Loom | Posit-maintained, Polars/Pandas-aware, produces publication-quality tables without a JS toolchain. The eval narrative needs a "rigor legible to a non-author reader" artifact; this is the lowest-friction way to ship one PNG into the README. Optional - skip if Markdown tables read well enough on GitHub. |

That is the entire prescribed addition list. Three deps, all pure-Python or pure-C extensions, no transitive bloat, no framework lock-in.

### Supporting libraries (already present, just call them out)

| Library | Version (current) | Purpose | When to Use |
|---------|-------------------|---------|-------------|
| `pydantic` | `>=2.7.0` (already in `pyproject.toml`) | Typed eval models: `LabeledExample`, `JudgeVerdict`, `GroundednessReport` | Every new eval data class. Don't add `dataclasses` next to existing pydantic models. |
| `pytest` + `pytest-asyncio` | `>=8.2.0` / `>=0.23.0` | Run eval suite as a normal test target (`pytest -m eval`), gated by a `eval` marker | Register `eval` in `pyproject.toml` `markers`; mirrors the existing `smoke` pattern. Keep evals out of the default `make test` to avoid burning judge tokens in CI. |
| `tenacity` | `>=8.3.0` | Backoff on judge calls (already configured in `NvidiaClient`) | Reuse the existing retry policy. Judge calls are LLM calls, same 429 surface. |
| `respx` | `>=0.21.0` | Mocked judge HTTP for unit/functional tests of rubric scoring | Layer 2 of the 5-layer testing strategy. Mock the judge response, assert rubric math, no live tokens. |
| `pyyaml` | `>=6.0` | If the rubric's judge prompts move from inline strings into `evals/rubric.yaml`, parse them with the same loader `configs/icp.yaml` uses | Only if rubric prompt versioning becomes a concern. Not required for v1. |

### Development tools (no change)

| Tool | Purpose | Notes |
|------|---------|-------|
| `black`, `ruff`, `mypy --strict` | Lint/format/type new eval code | New modules under `evals/` must satisfy strict mypy. No exceptions. |
| `pre-commit` | Same hooks | Don't add eval-specific hooks; the eval target runs in CI as a separate job, not pre-commit. |

## Installation

```bash
# Add to pyproject.toml dependencies
uv add rapidfuzz jinja2

# Add to pyproject.toml [project.optional-dependencies].dev (or a new `eval` extra)
uv add --optional eval great-tables
```

Pin floors only (`rapidfuzz>=3.14`, `jinja2>=3.1`, `great-tables>=0.21`). The repo's existing convention is floor-pinning; the lockfile `uv.lock` carries exact versions.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `rapidfuzz` + hand-rolled judge in `evals/rubric.py` | `deepeval==4.0.2` | If this project grew into a multi-tenant eval platform with web-UI test management and CI dashboards. For a single-operator POC it imports a metric framework, an `assert_test` pytest harness, and a base-class hierarchy (`DeepEvalBaseLLM`) we'd have to subclass to wrap `NvidiaClient`. Net: more surface area than the existing `evals/rubric.py` already gives us. |
| `rapidfuzz` + hand-rolled judge | `ragas==0.4.3` | If we were evaluating a full RAG pipeline with `question/context/answer` triplets and wanted out-of-the-box `faithfulness`, `context_precision`, `answer_relevancy` metrics. Two blockers for this POC: (1) Ragas routes through LiteLLM/LangChain to talk to non-OpenAI providers, which is a second model-routing layer next to our `NvidiaClient`; (2) the metric names map to RAG semantics, not "sales-claim is supported by retrieved evidence." We'd be bending Ragas's vocabulary. |
| `rapidfuzz` + hand-rolled judge | `inspect-ai` (UK AISI, Python >=3.10, active 2026) | If this work expanded to safety/capability evals across many models and tasks. Inspect is excellent for batch evals of frontier models with structured task definitions. Overkill for "score 50-200 hand-labeled outreach examples on a 1-5 axis." |
| Markdown tables in README + Jinja-rendered HTML report | `streamlit` / `gradio` dashboard | Never, for this milestone. PROJECT.md explicitly lists webapp/dashboard as v3 out-of-scope. The artifact is README+Loom, not an app. |
| Jinja2 templates for the eval narrative | `mkdocs` / `quarto` | If the eval narrative grew into a multi-page doc site. For one section in README.md plus an `evals/REPORT.md` artifact, Jinja into static Markdown is correct. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `promptfoo` (pypi `0.1.4`, JS under the hood, requires Node 20+) | Adds a Node toolchain to a Python-only repo. The PyPI package is a wrapper that shells out to `npx promptfoo@latest`. Violates the locked stack (`uv` + Python) and complicates CI without buying anything we can't do in `evals/rubric.py`. | Keep the existing `evals/rubric.py` judge harness; add `rapidfuzz`-backed groundedness scoring beside it. |
| `deepeval` for this milestone | Capable framework, but it wraps the LLM in its own `DeepEvalBaseLLM` adapter and ships its own `assert_test` decorator. We already have `NvidiaClient`, `pytest-asyncio` `auto` mode, and a `1-5` categorical rubric matching NeMo guidance. Adopting DeepEval means rewriting `evals/rubric.py` to satisfy its API. Two-week milestone, not the right time. | Keep the existing rubric and judge. If we later need a hosted eval dashboard, revisit. |
| `ragas` for this milestone | RAG-centric metric vocabulary (`faithfulness`, `context_recall`) doesn't cleanly map to "outreach claim cites a real Exa snippet." Routes through LiteLLM, adding a second LLM router next to our `NvidiaClient`. Custom OpenAI-compatible providers require `litellm.completion` plumbing per their docs. | If we need a faithfulness number specifically, compute it as: `rapidfuzz` overlap between each claim and its cited evidence, then judge-verify the borderline cases. Same signal, no new framework. |
| `inspect-ai` for this milestone | Designed for frontier-eval scale (200+ benchmarks, multi-model sweeps). Importing it for a 50-200 example labeled set is using a kiln to bake a cookie. | Existing `evals/rubric.py` + `pytest -m eval`. |
| `langchain` / `llama-index` evaluators | Heavy framework with its own model abstractions; the project explicitly uses raw `openai.AsyncOpenAI` against custom base URLs to avoid this. | Direct `NvidiaClient` calls, as already implemented. |
| `litellm` as a router | We already have `NvidiaClient` which is a 200-line `AsyncOpenAI` wrapper that does exactly what LiteLLM does for our two providers, plus thinking-mode toggles tuned for each. Adding LiteLLM means two routers fighting over the same base URLs. | Keep `NvidiaClient`. Add providers there if needed. |
| `gspread` / `gspread-formatting` | The repo writes Sheets via `google-api-python-client` directly, with conditional formatting and row coloring already implemented in `src/sheets.py`. `gspread` is a different SDK; mixing them would split the Sheets writer in two. | Extend `src/sheets.py` directly for any new formatting (conditional groundedness flags, per-axis score columns). The Sheets API surface is small enough that the existing batchUpdate-style code is fine. |
| Custom prompt-caching layer | Explicitly out of scope per `CLAUDE.md`. DeepSeek auto-caches at 1/10 input price on hits; NVIDIA doesn't expose cache control. | Trust provider-side caching. |
| Numeric 1-10 LLM-as-judge scales | `CLAUDE.md` already documents that NeMo guidance says numeric 1-10 judges drift; the rubric is 1-5 categorical. Sticking it here because it's the most common eval mistake. | 1-5 categorical with explicit anchor descriptions per level (already in `evals/rubric.py`). |

## Stack Patterns by Variant

**If groundedness audit (Phase 1) finds the writer occasionally cites the wrong snippet:**
- Use `rapidfuzz.fuzz.partial_ratio` at write time in `src/outreach.py` to verify each emitted claim has >= N% token overlap with at least one cited Exa snippet
- Drop claims that fail the threshold (`CLAUDE.md` "Failure modes: every outreach claim must trace to a retrieval")
- Threshold lives in `configs/icp.yaml` or a new `configs/eval.yaml`, not hardcoded

**If audit finds the judge rubric anchors are weak:**
- Use Jinja templates in `evals/prompts/` for the judge prompt so each axis (groundedness, relevance, specificity) has explicit per-level anchor examples
- Version the templates with the dataset; bump a `rubric_version` field on each `LabeledExample` so old judgments don't silently mix with new

**If the eval narrative needs a Loom-quality visual:**
- Use `great-tables` to render the per-axis score distribution and a 5x5 confusion matrix (judge verdict vs human label) to PNG
- Embed the PNG in `README.md` and `evals/REPORT.md`
- Skip if a Markdown table renders adequately on GitHub; don't add the dep speculatively

**If `evals/labeled.jsonl` grows past ~200 examples:**
- Add a `make eval-sample` target that runs a stratified subset for fast iteration
- Keep the full set for the headline number in `evals/REPORT.md`
- Do NOT introduce a dataset framework (`datasets`, `dvc`). JSONL plus git is sufficient at this scale.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `rapidfuzz>=3.14.5` | Python 3.9-3.14 | No issues with `py311`. Pure C++ extension, wheels published for macOS/Linux/Windows. |
| `jinja2>=3.1.6` | Python 3.7+ | Already a transitive dep of `pytest` plugins and `googleapiclient`; pinning it directly is safe. |
| `great-tables>=0.21.0` | Python 3.9+, Polars or Pandas | Pulls in Polars by default. If we don't want Polars in the runtime dep set, scope `great-tables` under an `eval` extra so production installs skip it. |
| `pydantic>=2.7` + new eval models | - | Eval data classes should use `pydantic.BaseModel`, not `pydantic.dataclasses`, to match `src/models.py`. |
| `mypy --strict` + new modules | - | `great-tables` ships type stubs but they are loose; if mypy complains, add it to the same `[[tool.mypy.overrides]]` block that already silences Google API modules (`pyproject.toml:64-66`). Do not relax strict mode globally. |

## Sources

- PyPI `rapidfuzz` 3.14.5, 2026-04-07 — version, license, scope verified
- PyPI `jinja2` 3.1.6, 2025-03-05 — version, Pallets maintenance verified
- PyPI `great-tables` 0.21.0, 2026-03-03 — version, Posit maintenance, Pandas/Polars support verified
- PyPI `promptfoo` 0.1.4, 2026-04-06 — Node-wrapper architecture confirmed (reject)
- PyPI `deepeval` 4.0.2, 2026-05-13 — Apache-2.0, `DeepEvalBaseLLM` adapter pattern confirmed
- deepeval.com docs — confirmed offline operation possible with custom LLM, but requires base-class subclass to wrap our client (reject for milestone scope)
- PyPI `ragas` 0.4.3, 2026-01-13 — RAG metric vocabulary and LiteLLM dependency for non-OpenAI providers confirmed (reject)
- `UKGovernmentBEIS/inspect_ai` GitHub `pyproject.toml` — Python >=3.10, setuptools_scm versioning, frontier-eval scope confirmed (reject for milestone scope)
- PyPI `litellm` 1.84.0, 2026-05-14 — DeepSeek native support confirmed, redundant with existing `NvidiaClient` for our two providers (reject)
- `.planning/codebase/STACK.md` and `.planning/codebase/INTEGRATIONS.md` — existing dep inventory, confirmed no overlap with proposed additions
- `CLAUDE.md` — locked stack constraints, 1-5 categorical rubric guidance, caching policy
- `.planning/PROJECT.md` — milestone scope, demo-killers, out-of-scope list

## Confidence per pick

| Pick | Confidence | Why |
|------|------------|-----|
| `rapidfuzz` | HIGH | PyPI verified, well-known library, the right primitive for the stated problem, no framework risk |
| `jinja2` | HIGH | Stable, already transitively present, low-risk addition |
| `great-tables` | MEDIUM-HIGH | Verified current and actively maintained by Posit; the one judgment call is whether the README needs a rendered table at all. Easy to defer. |
| Reject `promptfoo` | HIGH | Confirmed JS-under-the-hood from official PyPI page |
| Reject `deepeval` | MEDIUM-HIGH | Capable framework; the rejection is about milestone scope (2-week harden) not library quality. Revisit for v2. |
| Reject `ragas` | HIGH | RAG-vocab mismatch and LiteLLM routing redundancy are structural, not version-dependent |
| Reject `inspect-ai` | HIGH | Frontier-eval framing is mismatch with single-vertical, single-rubric POC |
| Reject `litellm` | HIGH | Redundant with existing `NvidiaClient` for the two providers we support |
| Reject `gspread*` | HIGH | Would split the Sheets writer; `google-api-python-client` already handles formatting in `src/sheets.py` |

---
*Stack research for: groundedness + LLM-as-judge tooling, demo-ready v1 milestone*
*Researched: 2026-05-14*
