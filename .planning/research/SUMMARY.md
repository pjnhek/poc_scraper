# Project Research Summary

**Project:** poc_scraper — demo-ready v1
**Domain:** Brownfield Python LLM pipeline (grounded account research + LLM-as-judge eval) being hardened into a public hiring + GTM artifact
**Researched:** 2026-05-14
**Confidence:** HIGH

## Executive Summary

This milestone is a brownfield hardening pass on an existing async pipeline (`enrich -> score -> contacts -> outreach -> eval -> sheets`). The four research streams converged on one diagnosis: the pipeline already has three physical seams where groundedness *could* be enforced (evidence ledger in `enrich.py`, writer-side marker check in `outreach.py`, judge in `evals/rubric.py`), but only one of them (the writer-side "at least one marker") is actually enforcing anything strict. Demo-killer DK1 (an ungrounded claim) is currently reachable through a paragraph with one real `[N]` cite and three fabricated companion claims. Demo-killer DK2 (eval numbers that do not tell a story) is reachable because `evals/labeled.jsonl` is small, has no train/holdout split, and the narrative artifact does not yet exist.

The recommended approach is small and stack-conservative. Add exactly three pure-Python dependencies, `rapidfuzz` (sentence-to-evidence overlap), `jinja2` (judge prompt + report templating), and optional `great-tables` (publication-quality eval tables), and reject every framework alternative (`deepeval`, `ragas`, `promptfoo`, `inspect-ai`, `litellm`) because each would replace code that already works with a wrapper API. The architectural work is mostly *enforcement* of existing seams rather than new structure: extract `src/citations.py` so writer and judge share one citation parser, replace the free-form `status: Literal["scored","unscoreable"]` + `error: str` pair with a discrete `AccountStatus` enum (so "judge failed" and "writer fabricated" stop colliding visually), and keep the eval narrative as an offline sidecar that reads `evals/labeled.jsonl` and emits markdown, never inline in the pipeline run.

The phase ordering all four researchers independently arrived at: **audit first, fix code seams + status enum, expand the labeled set with a coverage matrix and a held-out split, generate the eval narrative, harden failure modes and polish the sheet in parallel, public-repo audit, and finally re-record README + Loom against the locked output**. The README/Loom phase is intentionally last because re-recording mid-milestone wastes effort, and it must follow the public-repo audit because the recording would otherwise capture vendor/vertical leaks. The single highest-risk pattern not yet on anyone's radar: **judge-writer collusion** (same model family writes and judges) inflates groundedness scores without anyone noticing, the eval narrative needs a cross-family agreement number to be honest.

## Key Findings

### Recommended Stack

The locked stack (Python 3.11+, uv, OpenAI-compatible clients pointed at DeepSeek/NVIDIA, Exa + Browserbase, Google Sheets API, strict mypy) does not change. Three thin additions close the groundedness + narrative gap without dragging in a framework that owns model routing, dataset state, or the Sheets surface.

**Core technologies (additions):**

- `rapidfuzz>=3.14.5`, sentence-to-evidence string match at write time (in `src/outreach.py` / `src/citations.py`) and at judge time, pure C++/Python, deterministic, MIT
- `jinja2>=3.1.6`, templated judge prompts and the eval-report renderer (`evals/report.py`), already a transitive dep
- `great-tables>=0.21.0` (optional, behind an `eval` extra), per-axis score tables and calibration matrix rendered to PNG; defer if Markdown tables render adequately

**Timing of additions:**

- `rapidfuzz` lands in fix-grounding phase (seam B writer guard + judge evidence-overlap signal)
- `jinja2` lands in narrative phase (report rendering)
- `great-tables` lands in narrative phase only if Markdown is insufficient; skip-by-default

**Explicit rejects:** `deepeval`, `ragas`, `promptfoo`, `inspect-ai`, `litellm`, `gspread*`. See `STACK.md` for full rationale.

### Expected Features

11 table stakes, 11 differentiators, 11 anti-features. Full matrix in `FEATURES.md`.

**Must have (table stakes, missing any kills the demo):**

- TS1 every outreach claim traceable
- TS3 eval narrative section in README with concrete numbers + methodology + screenshot
- TS4 labeled eval set sized + coverage-rationaled
- TS5/TS6 graceful degradation visible in the Sheet
- TS7 README front-loads the what / why / proof in the first scroll
- TS8 Loom re-recorded against the final output
- TS9 public-repo cleanliness (zero vertical/vendor names anywhere, including history)
- TS10 pipeline survives a real 20-50 row CSV
- TS11 fresh-clone setup works

**Should have (differentiator framing, code mostly exists, just needs README surfacing):**

- D1 claim-decomposition methodology documented, D2 1-5 categorical rationale, D3 judge calibration table, D4 coverage rationale, D5 failure-mode gallery, D8 architecture diagram, D10 honest "got wrong" callout

**Defer / anti-features (do NOT build):** AF1-AF11 in FEATURES.md (1-10 quality scores, personalization beyond retrievals, ICP confidence percentages, chat/Q&A, self-critique, LLM-written summaries, in-sheet feedback loop, vector store, long README, multi-tenant, LLM-written persona narrative)

**Critical feature dependency:** TS9 (public-repo audit) blocks TS7 (README front-load) and TS8 (Loom). TS1 blocks all citation-UX polish.

### Architecture Approach

Linear-async with DI; hardening overlays a *groundedness contract* on three existing seams. The single most important DRY discipline is extracting `src/citations.py` so writer guard and judge share one citation parser. The narrative artifact stays in `evals/` as an offline sidecar. The free-form `status: Literal["scored","unscoreable"]` + `error: str` pair gets replaced with a discrete `AccountStatus` enum so the sheet renderer can branch on distinct visual states.

**Major components (deltas only):**

1. `src/citations.py` (NEW), pure citation parsing + coverage rules, imported by `src/outreach.py` and `evals/rubric.py`
2. `src/models.py::AccountStatus` (EDIT), discrete enum + `EvalScore.eval_failed` sentinel
3. `src/pipeline.py` (EDIT), propagate suppression; narrow `except Exception` to tagged classes
4. `src/sheets.py` (EDIT), render four AccountStatus states distinctly
5. `evals/report.py` (NEW), markdown narrative generator; reads `labeled.jsonl` + run log, writes `evals/REPORT.md`
6. `configs/icp.yaml` (EDIT), `default_personas` + `groundedness_suppress_threshold`

### Critical Pitfalls

Top 5; full 14 in `PITFALLS.md`.

1. **Partial-citation laundering (Pitfall 1)**, current guard drops only paragraphs with zero `[N]` markers. Avoid: sentence-level coverage + sheet suppression stub on sub-threshold.
2. **Judge-writer collusion (Pitfall 2)**, same family, same blind spots, inflated scores. Avoid: cross-family calibration slice with NVIDIA judge; report inter-judge agreement in narrative.
3. **Generic LLM personalization passing groundedness (Pitfall 11)**, technically grounded, useless to humans. Avoid: add specificity + recency axes 1-5.
4. **`groundedness=1` sentinel collision (Pitfall 5)**, judge-failed and writer-hallucinated render identically. Avoid: `EvalScore.eval_failed` separate; grey vs red.
5. **Public-repo leaks in history (Pitfall 7)**, `git log --all -p | grep` still finds them after scrubbing main. Avoid: dedicated phase; deliberate git-filter-repo decision; `detect-secrets` / `gitleaks` pre-commit.

## Implications for Roadmap

All four researchers independently arrived at the same eight-phase ordering.

### Phase 1: Groundedness Audit (no code changes)

**Rationale:** Cannot fix what hasn't been audited.
**Delivers:** `findings.md` enumerating every gap; manual claim-source pairing on a sample.
**Addresses:** TS1 precondition. **Avoids:** Pitfalls 1, 6.
**Success criterion:** Findings with file:line refs and decisions for the 6 open questions below.

### Phase 2: Fix groundedness in `src/`

**Rationale:** Audit output is a list of code changes; Phases 3/5/6 depend on new schema.
**Delivers:** `src/citations.py` extraction; sentence-level writer coverage; `AccountStatus` enum + `EvalScore.eval_failed`; judge-suppression in pipeline; drop/YAML-ify `_default_contacts`.
**Uses:** `rapidfuzz`. **Avoids:** Pitfalls 1, 5, 14.
**Success criterion:** Coverage threshold in `configs/icp.yaml`; four distinct sheet visuals; integration test `FakeExa(about=[], news=[])` end-to-end.

### Phase 3: Expand `evals/labeled.jsonl`

**Rationale:** Labels must match final `EvalScore` schema from Phase 2.
**Delivers:** `evals/COVERAGE.md` (matrix); 30% held-out split; cross-family calibration slice.
**Addresses:** TS4, D4. **Avoids:** Pitfalls 2, 3, 4.
**Success criterion:** Every matrix cell has at least one example; cross-family agreement recorded; holdout never inspected during prompt tuning.

### Phase 4: Eval narrative artifact

**Rationale:** Depends on Phase 3 finality.
**Delivers:** `evals/report.py` + `make eval-report` + `evals/REPORT.md` answering Pitfall 8's 6 questions; verbatim claim-source audit slice.
**Uses:** `jinja2`, optional `great-tables`. **Avoids:** Pitfalls 2, 3, 8, 11.

### Phase 5: Harden failure modes (parallel with 6)

**Delivers:** Narrowed exceptions tagged with class name; `Retry-After` parsing; empty-enrichment + citation-drop test coverage; optional cached demo bundle.
**Avoids:** Pitfalls 9, 13, 14.

### Phase 6: Polish Sheet output (parallel with 5)

**Delivers:** Four AccountStatus visuals; whole-row tinting; hyperlinked citations to Sources tab (D11); column-per-axis score breakdown; freeze panes.
**Avoids:** Pitfalls 5, 12.

### Phase 7: Public-repo audit

**Rationale:** Can parallel 5/6; must precede 8.
**Delivers:** Synthetic `inputs/accounts.csv`; scrubbed prompts/docstrings; `git log --all -p | grep` decision; `detect-secrets`/`gitleaks` pre-commit + deny-list grep.
**Addresses:** TS9. **Avoids:** Pitfall 7.
**Success criterion:** Deny-list grep returns zero; history decision logged.

### Phase 8: README + Loom refresh

**Rationale:** Last by design.
**Delivers:** Front-loaded README; architecture diagram (D8); failure-mode gallery (D5); editable-rubric framing (D7); v2/v3 deferral (D6); Loom against synthetic CSV; commit SHA pinned; static sheet screenshot embedded.
**Avoids:** Pitfall 10.

### Phase Ordering Rationale

- Audit before fix (1 -> 2)
- Fix before label (2 -> 3): `EvalScore` schema must stabilize
- Label before narrate (3 -> 4): moving dataset = stale narrative
- Schema before parallel polish (2 -> 5/6): both read new `AccountStatus`
- Scrub before record (7 before 8): non-negotiable
- Record last (8): PROJECT.md Key Decision

### Research Flags

**Need planning-phase decisions:** Phase 2 (sentence-coverage shape), Phase 4 (report skeleton + `great-tables` yes/no)
**Standard patterns, skip `/gsd-research-phase`:** Phases 3, 5, 6, 7, 8 (mechanical against itemized checklists)

### Cross-Cutting Decisions (researcher consensus)

1. Extract `src/citations.py` as shared parser
2. `AccountStatus` enum replaces `status: str + error: str`
3. Eval narrative is offline sidecar in `evals/`
4. Keep 1-5 categorical judge rubric
5. No new framework, three thin libraries only
6. Thresholds in `configs/icp.yaml`, not env

### Open Questions (Phase 1 audit must resolve)

1. Sentence-level coverage shape: `[N]`-per-sentence vs `(claim, indices)` tuples, sample 10-20 current hooks
2. History rewrite vs accept-and-document, depends on actual hit list
3. Specificity + recency axes: Phase 2 or defer
4. Cached demo-bundle: needed only if `make run` exceeds ~90s
5. `great-tables` dependency: skip if Markdown calibration table reads well
6. Existing labels migratable under new `EvalScore` shape, or re-label?

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PyPI verified; `great-tables` is the one judgment call |
| Features | HIGH on table stakes/anti-features, MEDIUM on differentiator ranking |
| Architecture | HIGH | Grounded in `.planning/codebase/`; three seams already exist |
| Pitfalls | HIGH | CLAUDE.md + CONCERNS.md + LLM-eval literature |

**Overall confidence:** HIGH

### Gaps to Address

- Phase 2 and 7 sizing depend on Phase 1 output
- Specificity/recency axis scope decided by audit
- History-rewrite cost unknown until `git log --all -p | grep` runs

## Sources

### Primary (HIGH)

- PyPI registry for `rapidfuzz`, `jinja2`, `great-tables`, `deepeval`, `ragas`, `inspect-ai`, `litellm`, `promptfoo`
- `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `CONCERNS.md`, `STACK.md`, `INTEGRATIONS.md`
- `.planning/PROJECT.md`, `CLAUDE.md`

### Secondary (MEDIUM)

- deepset, arxiv (2407.12858, 2503.04830), Databricks, Meilisearch eval best-practices articles
- Anthropic engineering blog, NeMo eval guidance, Inspect AI examples

### Tertiary (LOW, measure during execution)

- Cross-family judge disagreement magnitude (Phase 3 measures)
- `make run` wall-clock on fresh synthetic CSV (Phase 5 measures)
- Git-history leak extent (Phase 7 enumerates)

---
*Research completed: 2026-05-14*
*Ready for roadmap: yes*
