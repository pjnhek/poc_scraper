# Architecture Research

**Domain:** Hardening a brownfield Python LLM pipeline (account-research POC) into a demo-ready v1 with groundedness as the central value
**Researched:** 2026-05-14
**Confidence:** HIGH (architecture is grounded in the existing codebase map at `.planning/codebase/` plus standard patterns for small-team RAG/agent POCs)

## Standard Architecture

### System Overview

The pipeline is already linear-async with DI; the hardening work overlays a *groundedness contract* on top of three architectural seams the code already has but does not fully enforce. The diagram below shows the existing call graph with the seams highlighted (`***`).

```
┌─────────────────────────────────────────────────────────────────┐
│                Entry: src/pipeline.py::main                      │
│  Settings -> Deps -> asyncio fan-out (Semaphore 5)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: src/enrich.py::Enricher                                │
│   Exa + Browserbase -> numbered Justification[]                  │
│   *** SEAM A: evidence ledger — the single source of truth       │
│       for what is citeable. Index integrity is the foundation.   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Enrichment (frozen, indices 1..N)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: src/score.py::Scorer                                   │
│   writer LLM -> supporting_indices cross-checked vs Enrichment   │
└────────────────────────┬────────────────────────────────────────┘
                         │ ICPScore
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3: src/contacts.py::ContactExtractor                      │
│   writer LLM -> top-3 personas (currently NOT citation-bound)    │
└────────────────────────┬────────────────────────────────────────┘
                         │ tuple[Contact, ...]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: src/outreach.py::OutreachGenerator                     │
│   writer LLM -> paragraph with [N] markers                       │
│   *** SEAM B: writer-side enforcement — currently "at least one  │
│       valid marker" gate. This is where coverage rules live.     │
└────────────────────────┬────────────────────────────────────────┘
                         │ tuple[OutreachHook, ...]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5: evals/rubric.py::EvalRubric (sidecar, inline)          │
│   judge LLM -> claim decomposition -> groundedness 1..5          │
│   *** SEAM C: post-write validator — judge can suppress, not     │
│       just annotate. Currently only annotates.                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ ScoredAccount
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Sink: src/sheets.py::SheetsWriter                               │
│   results tab + Rubric + Inputs, verdict colors, eval-flag red   │
│   *** Surface for the propagated groundedness signal             │
└─────────────────────────────────────────────────────────────────┘

   Eval narrative artifact (NEW, sidecar, offline):
   evals/run_eval.py + evals/run_live.py -> markdown report
   reads labeled.jsonl + recent pipeline output; writes
   evals/report.md (or README section). Never blocks main run.
```

### Component Responsibilities (hardening additions on top of existing)

| Component | Responsibility | Module |
|-----------|----------------|--------|
| Evidence ledger | Single numbered `Justification[]` per account; immutable contract | `src/enrich.py`, `src/models.py::Justification` |
| Writer-side claim guard | Reject paragraphs whose `[N]` coverage falls below threshold (not just "any marker") | `src/outreach.py` |
| Citation extraction utility | Pure function that parses `[N]` markers and intersects with allowed indices; shared by writer guard and judge | New: `src/citations.py` (extracted from `_markers_in_paragraph` in `src/outreach.py`) |
| Post-write validator | Judge groundedness can suppress hook text below configurable threshold | `evals/rubric.py` + `src/pipeline.py::process_account` |
| Failure status propagation | `ScoredAccount.status` extended with discrete reasons (`unscoreable`, `low_groundedness`, `judge_failed`); `error` field carries diagnostic | `src/models.py::ScoredAccount`, `src/pipeline.py` |
| Sheet signal renderer | Distinguish four states: clean, judge-flagged, writer-suppressed, judge-failed | `src/sheets.py` |
| Eval narrative generator | Offline command that reads labeled.jsonl + a recent run, emits a markdown report with MAE table, coverage rationale, example rows | New: `evals/report.py` invoked by `evals/run_eval.py` |
| Public-repo guard | Pre-commit hook + scrub list for vendor/vertical leaks | `.pre-commit-config.yaml`, `inputs/accounts.csv`, `src/contacts.py::_default_contacts` |

## Recommended Project Structure (deltas only)

The existing structure is sound. Hardening adds two files and edits a handful:

```
src/
├── citations.py        # NEW: pure citation parsing + coverage rules
│                       #      extracted from outreach.py so the judge
│                       #      and writer guard share one implementation
├── outreach.py         # EDIT: use src/citations.py; raise coverage bar
├── contacts.py         # EDIT: drop hardcoded vertical personas
├── models.py           # EDIT: extend ScoredAccount.status enum,
│                       #       add EvalScore.eval_failed sentinel
├── pipeline.py         # EDIT: propagate suppression decisions
└── sheets.py           # EDIT: render the four states distinctly
evals/
├── report.py           # NEW: markdown narrative generator
├── run_eval.py         # EDIT: invoke report.py at end
└── labeled.jsonl       # EDIT: expand with documented coverage rationale
configs/
└── icp.yaml            # EDIT: add `default_personas` and
                        #       `groundedness_suppress_threshold` keys
```

### Structure Rationale

- **`src/citations.py` as a shared seam.** The single most important DRY violation in this milestone would be having "what counts as a valid citation" implemented twice — once in the writer guard and once in the judge. Extract it into one module that both consume. The judge in `evals/` can import from `src/` (the existing dependency direction).
- **`evals/report.py` stays in `evals/`.** The eval narrative is a sidecar artifact, not part of the production pipeline. Keeping it in `evals/` preserves the existing rule that `src/` does not import from `evals/`.
- **Configurable thresholds in `configs/icp.yaml`, not env.** Both `groundedness_suppress_threshold` (writer-side) and the existing `eval_flag_threshold` (judge-side) are *policy*, not runtime knobs. They belong with the rubric so a vertical retarget can tune them.

## Architectural Patterns

### Pattern 1: Defense in depth for groundedness (three seams, not one)

**What:** Enforce the citation contract at three locations rather than picking one. The seams compose: each catches what the previous one misses.

| Seam | Where | What it catches | What it misses |
|------|-------|-----------------|----------------|
| A. Evidence ledger | `src/enrich.py` numbers `Justification[]`; `Enrichment` is frozen | Indices that don't exist | Writer claiming index 3 supports a claim it doesn't |
| B. Writer-side guard | `src/outreach.py` / `src/citations.py` cross-checks `[N]` markers in paragraph | Indices the writer claimed but never wrote into the paragraph | Writer citing index 3 for a claim index 3 doesn't actually support (the *semantic* hallucination) |
| C. Post-write validator | `evals/rubric.py` decomposes claims, judges each against justification text | Semantic mismatch between claim and cited evidence | Judge LLM error / drift |

**When to use:** Always, for a product whose entire value prop is groundedness. Single-seam enforcement is the dominant POC failure mode in this class of system; the cost of all three is low because the seams already exist physically in the code.

**Trade-offs:**
- Adds two LLM calls per hook (judge already does this); writer guard is free.
- Suppression at Seam C means a hook the writer produced may not appear in the sheet. The `error` / `status` field must surface *why* so the operator does not think a domain silently failed.
- DRY discipline matters: extract the citation parser into `src/citations.py` so the writer guard and judge use the same definition of "valid marker."

**Example:**
```python
# src/citations.py — single source of truth
def parse_markers(paragraph: str) -> frozenset[int]:
    """Indices that appear as [N] markers in the paragraph text."""
    ...

def claim_coverage(paragraph: str, allowed: frozenset[int]) -> float:
    """Fraction of sentences that contain at least one valid [N] marker.
       Used by outreach writer guard and reported by the judge."""
    ...
```

### Pattern 2: Eval as offline sidecar that reads pipeline artifacts

**What:** The narrative report generator does not run inside the pipeline. It reads `evals/labeled.jsonl` and (optionally) the most recent live run output, emits markdown, and stops.

**When to use:** Small-team AI POCs where evaluation needs to be visible to a reader but should not slow down or destabilize the main run. Pattern matches what Anthropic, OpenAI, and the Inspect AI / NeMo Eval communities recommend for "eval as documentation."

**Trade-offs:**
- The narrative is a *snapshot*. Stale reports are misleading; mitigation is a Makefile target (`make eval-report`) and a CI job that regenerates on changes to `evals/labeled.jsonl` or the judge prompt.
- Cannot block bad releases (no CI gate on groundedness). That's the right trade for a POC; production-grade gating belongs in v2.

**Example structure for `evals/report.md`:**
```
1. What the rubric measures (link to configs/icp.yaml)
2. Labeled dataset: size, coverage rationale, how examples were chosen
3. Judge calibration: MAE table vs hand labels, by axis
4. Live run snapshot: groundedness distribution across last N domains
5. Failure modes observed and how the pipeline surfaced them
6. Known judge limitations
```

### Pattern 3: Discrete failure-mode status enum, not a free-form string

**What:** Replace `ScoredAccount.status: Literal["scored", "unscoreable"]` plus free-form `error: str` with a discrete enum that downstream code (and the sheet renderer) can branch on:

```python
# src/models.py
class AccountStatus(str, Enum):
    SCORED = "scored"
    UNSCOREABLE_EMPTY_ENRICHMENT = "unscoreable_empty_enrichment"
    UNSCOREABLE_SCORE_FAILED = "unscoreable_score_failed"
    LOW_GROUNDEDNESS = "low_groundedness"        # judge flagged
    HOOK_SUPPRESSED = "hook_suppressed"          # writer guard dropped all hooks
    JUDGE_FAILED = "judge_failed"                # eval inconclusive, NOT the writer's fault
```

**When to use:** Whenever a UI needs to render different visual states per failure class. The sheet renderer needs to distinguish "writer fabricated" (red, suppress hook) from "judge couldn't evaluate" (yellow, show hook + warning). Today both look the same — the `CONCERNS.md` MEDIUM at `evals/rubric.py:106-113` is exactly this.

**Trade-offs:**
- Schema change: `extra="forbid"` plus frozen models means every consumer must be updated together. The strict mypy + the frozen-models discipline make this a feature, not a bug — the type checker enumerates the work for you.
- More surface area in `src/sheets.py`. Worth it: the demo audience reads the sheet first.

## Data Flow

### Primary Request Path (with groundedness signals)

```
csv_io.read_accounts
    ↓
pipeline.process_account (per domain)
    ↓
enrich.Enricher.enrich  ───►  Enrichment(justifications=numbered 1..N)
    ↓                          [SEAM A: evidence ledger established]
score.Scorer.score
    ↓
contacts.ContactExtractor.extract
    ↓
outreach.OutreachGenerator.generate
    │  citations.parse_markers + claim_coverage  ◄── shared with judge
    │  [SEAM B: writer guard — coverage threshold or drop]
    ↓
EvalRubric.evaluate_account
    │  per hook: decompose -> per claim: cite vs justification
    │  [SEAM C: post-write validator]
    │  groundedness < suppress_threshold  ──►  status = LOW_GROUNDEDNESS,
    │                                          hook.paragraph blanked
    │  judge raised  ──►  status = JUDGE_FAILED, paragraph preserved
    ↓
ScoredAccount(status, hooks, eval_score)
    ↓
sheets.SheetsWriter.write
    │  branch on status -> color/format/cell content
    └─►  Google Sheet (Results tab + Rubric + Inputs)

Sidecar (decoupled, runs on demand):
evals/run_eval.py  reads  evals/labeled.jsonl + recent runs.jsonl
                  └────►  evals/report.md (linked from README)
```

### Key Data Flows

1. **Citation contract flow.** `Enrichment.justifications` is numbered once in `enrich._number_justifications` and read identically by `score.py`, `outreach.py`, `evals/rubric.py`, and `sheets.py`. The frozen-pydantic + index-based design already guarantees this. Hardening adds: extract `src/citations.py` so the *parser* is also shared, not just the data.
2. **Groundedness signal flow.** Writer-side claim-coverage is computed inline (cheap); judge-side groundedness is computed in the eval sidecar that runs inline-by-default. Both write to `EvalScore`. The sheet renderer reads `(status, EvalScore.groundedness, EvalScore.eval_failed)` to pick a visual state.
3. **Failure-mode propagation.** Each stage's `try/except` in `process_account` writes a discrete `AccountStatus` plus a structured `error_class` (the exception classname, per `CONCERNS.md` MEDIUM at `src/pipeline.py:60`). The sheet renders both. The CSV/JSON runs-log dumps both so the eval narrative can summarize.
4. **Eval narrative flow.** Read-only over `evals/labeled.jsonl` (calibration set) and an optional run log; emits markdown. Never modifies pipeline state, never blocks a run.

## Suggested Phase Build Order

The audit-first ordering in `PROJECT.md` is correct. The dependency graph beneath it:

```
Phase 1: Audit (NO CODE CHANGES)
  └─► outputs: findings.md driving every subsequent phase
       │
       ├──────────────► Phase 2: Close groundedness gaps in src/
       │                  - extract src/citations.py (shared parser)
       │                  - raise writer-side coverage bar in outreach.py
       │                  - judge-suppression wiring in pipeline.py
       │                  - extend AccountStatus enum + EvalScore.eval_failed
       │
       ├──────────────► Phase 3: Expand evals/labeled.jsonl
       │                  - depends on Phase 2's stable EvalScore shape
       │                  - documented coverage rationale per example
       │
       ├──────────────► Phase 4: Eval narrative artifact
       │                  - depends on Phase 3's dataset being final
       │                  - new evals/report.py + make eval-report
       │
       ├──────────────► Phase 5: Harden failure modes
       │                  - narrow except clauses (CONCERNS MEDIUM)
       │                  - Retry-After parsing in exa/browserbase
       │                  - test coverage for empty-enrichment +
       │                    citation-cross-check drop
       │                  - PARALLELIZABLE with Phase 6
       │
       ├──────────────► Phase 6: Polish Sheet output
       │                  - render four AccountStatus states distinctly
       │                  - score breakdown legibility
       │                  - PARALLELIZABLE with Phase 5
       │
       ├──────────────► Phase 7: Public-repo audit
       │                  - scrub inputs/accounts.csv,
       │                    src/contacts.py defaults, prompt examples
       │                  - add detect-secrets / gitleaks pre-commit hook
       │                  - PARALLELIZABLE with Phase 5/6 but MUST
       │                    precede Phase 8 (README/Loom shows the repo)
       │
       └──────────────► Phase 8: README + Loom refresh
                          - last; reflects the final pipeline output
                          - depends on every preceding phase
```

### Dependency Rationale

- **Phase 1 → 2:** Cannot fix what hasn't been audited. The audit *defines* the Phase 2 scope; preordaining the fixes would defeat its purpose.
- **Phase 2 → 3:** The labeled set needs to match the final `EvalScore` schema. Expanding the dataset against a schema that's about to change wastes labels.
- **Phase 3 → 4:** The narrative's MAE table reads the labeled set. Generating a report against a still-growing dataset produces a stale artifact.
- **Phase 2 → 5, 6:** The new `AccountStatus` enum and the writer-side suppression behavior are inputs to both the failure-mode tests (Phase 5) and the sheet renderer (Phase 6). Both can run in parallel once Phase 2 lands.
- **Phase 7 anywhere before Phase 8:** Scrubbing in parallel with code work is fine, but the README/Loom records the scrubbed state, so 7 must precede 8.
- **Phase 8 last:** Per `PROJECT.md` Key Decision. Re-recording mid-milestone wastes effort.

### Parallelization Map

| Can run in parallel | Cannot |
|---------------------|--------|
| Phase 5 (failure-mode hardening) and Phase 6 (sheet polish) | Phase 1 audit blocks everything |
| Phase 7 (repo scrub) with Phase 5 or 6 | Phase 2 blocks 3, 5, 6 (shared schema) |
| Within Phase 2: `src/citations.py` extraction is independent of the `AccountStatus` enum change — two engineers could split | Phase 3 blocks 4 (dataset → narrative) |
| Within Phase 5: rate-limit Retry-After parsing is independent of test-coverage additions | Phase 8 blocks nothing because it is last |

For a one-engineer milestone, the parallelization mostly manifests as "small commits that don't have to be sequenced strictly." For a two-engineer week, 5+6+7 can genuinely fan out.

## Scaling Considerations

The POC scope (10s of domains) does not stress the architecture. Scale comments for honesty:

| Scale | Adjustments |
|-------|-------------|
| 1-50 domains/run | Current architecture. No changes. |
| 50-500 domains/run | Exa quota becomes the limit (`CONCERNS.md` LOW notes 13 retrievals/account). Add a per-domain retrieval cache keyed on `(domain, ISO-date)` in a local SQLite. Out of scope for this milestone. |
| 500+ domains/run | The Google Sheets writer's per-row formatting calls are O(rows); batch into one `batchUpdate`. Out of scope for this milestone. |

### Bottleneck Order (if forced to scale)

1. **Exa API quota** — cache retrievals by domain.
2. **DeepSeek token spend** — already mitigated by auto-cache; nothing to do.
3. **Sheets API formatting calls** — batch them.

None of these are demo-killers at POC scale. Do not optimize.

## Anti-Patterns

### Anti-Pattern 1: Single-seam groundedness enforcement

**What people do:** Trust the judge alone ("we have eval, we're grounded") or the writer alone ("we cross-check `[N]` markers").
**Why it's wrong:** The judge is an LLM and drifts; the writer guard only verifies *presence* of a marker, not whether the marker semantically supports the claim. Either alone is a marketing claim, not an engineering guarantee.
**Do this instead:** Defense in depth at Seams A, B, C (above). The seams compose because they catch disjoint failure classes.

### Anti-Pattern 2: Eval narrative generated inline during the pipeline run

**What people do:** Add a "write the report" step to `src/pipeline.py::main`.
**Why it's wrong:** Couples the demo artifact to a real run, slows runs, and breaks the "eval as offline calibration" abstraction. Also pollutes the sheet writer's responsibilities.
**Do this instead:** Keep `evals/` as a sidecar. Add `evals/report.py` invoked by `make eval-report`. The README links to the latest committed report.

### Anti-Pattern 3: Free-form `error: str` for failure-mode propagation

**What people do:** Stuff every failure into a string field and grep it in the sheet renderer.
**Why it's wrong:** The renderer can't reliably distinguish "judge failed" from "writer fabricated" — both currently surface as red cells (`CONCERNS.md` MEDIUM, `evals/rubric.py:106`). The demo audience misreads "judge couldn't score this" as "your pipeline lied."
**Do this instead:** Discrete `AccountStatus` enum (Pattern 3). Branch on the enum in `sheets.py`.

### Anti-Pattern 4: Hardcoded vertical defaults in `src/`

**What people do:** Ship fallback personas like `VP Customer Experience` in `src/contacts.py::_default_contacts()` (`CONCERNS.md` HIGH).
**Why it's wrong:** Defeats the "vertical lives in YAML" contract. A public repo with CX personas hardcoded is also a vendor leak.
**Do this instead:** Either drop defaults (preferred: emit empty contacts + status), or move them to `configs/icp.yaml::default_personas`.

## Integration Points

### External Services (unchanged)

| Service | Integration | Notes |
|---------|-------------|-------|
| Exa | `src/clients/exa_client.py`, retries on `httpx.HTTPError` | Add `Retry-After` parsing (CONCERNS MEDIUM) |
| Browserbase | `src/clients/browserbase_client.py`, single retry | Don't retry `BrowserbaseError` (intentional, document it) |
| DeepSeek / NVIDIA | `src/clients/nvidia_client.py`, OpenAI-compatible | DeepSeek prefers `response_format=json_object` (already wired) |
| Google Sheets | `src/sheets.py`, service-account JSON | Detect 403 on share (CONCERNS LOW) |

### Internal Boundaries (hardening)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `src/outreach.py` ↔ `src/citations.py` | direct import | Shared citation parsing; pure function module |
| `evals/rubric.py` ↔ `src/citations.py` | direct import (evals reads from src) | Same parser, same semantics |
| `src/pipeline.py` ↔ `src/models.py::AccountStatus` | direct | Discrete enum; mypy enforces exhaustive handling |
| `src/sheets.py` ↔ `AccountStatus` | direct, switch on enum | Four visual states |
| `evals/report.py` ↔ `evals/labeled.jsonl` + run log | filesystem | Read-only; never touches pipeline state |
| Pre-commit ↔ everything | `gitleaks` or `detect-secrets` hook | Defense-in-depth for the public-repo discipline |

## Sources

- `.planning/codebase/ARCHITECTURE.md` — existing pipeline architecture (HIGH confidence)
- `.planning/codebase/STRUCTURE.md` — module layout and where to add new code (HIGH)
- `.planning/codebase/CONCERNS.md` — known weak spots; informed every hardening recommendation (HIGH)
- `.planning/PROJECT.md` — milestone goals, demo-killers, key decisions (HIGH)
- `CLAUDE.md` — stack locks, failure modes, 5-layer test strategy (HIGH)
- General pattern: defense-in-depth groundedness enforcement is the consensus design among small-team RAG/agent POC writeups (Anthropic engineering blog, NeMo eval guidance, Inspect AI examples) (MEDIUM, not verified against current docs because the patterns above are derived from this codebase's existing seams)

---
*Architecture research for: brownfield Python LLM pipeline hardening*
*Researched: 2026-05-14*
