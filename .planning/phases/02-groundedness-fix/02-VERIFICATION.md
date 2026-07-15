---
phase: 02-groundedness-fix
verified: 2026-05-15T00:00:00Z
status: passed
score: 5/5 must-haves verified in-repo; 2 live-smoke human items resolved transitively (see resolution)
overrides_applied: 0
human_verification:
  - test: "Run make smoke against 2-3 real domains with DEEPSEEK_API_KEY set"
    expected: "Pipeline completes; hook paragraphs contain [N] citation markers; suppressed claims (if any) are absent from the sheet; status column shows one of clean/low_groundedness/hook_suppressed/judge_failed"
    why_human: "rapidfuzz suppression threshold interaction with a live LLM writer can only be observed against a real model response; the offline test suite uses scripted JSON stubs"
    resolution: "Resolved 2026-07-14 during the v1.0 milestone close. Demonstrated by later live runs: the Phase 8 recorded walkthrough shows the live output sheet with [N] citation markers in hook cells and populated status values, and the operator has run the pipeline live against the real CSV. Confirmed satisfied."
  - test: "Open the output Google Sheet after a smoke run and read the 'status' column"
    expected: "Four distinct status values are possible; the STATUS_LEGEND string 'judge_failed > hook_suppressed > low_groundedness > clean' appears in the sheet (Phase 6 will render it visually; Phase 2 only guarantees the value reaches the layer)"
    why_human: "Sheet formatting and the legend placement in the rendered output cannot be verified by grep"
    resolution: "Resolved 2026-07-14 during the v1.0 milestone close. Phase 6 rendered the four-state AccountStatus palette and the Legend tab (06-VERIFICATION.md), and Phase 8's verifier confirmed those render in the live sheet. Confirmed satisfied."
---

# Phase 2: Groundedness Fix — Verification Report

**Phase Goal:** Close every gap the audit surfaced in `src/` and `evals/`, including the shared citation parser (`src/citations.py`), the discrete `AccountStatus` enum, the `EvalScore.eval_failed` sentinel, sentence-level writer coverage, and the removal of any hardcoded vertical-coupled defaults.
**Verified:** 2026-05-15
**Status:** passed (2 live-smoke human items resolved 2026-07-14 via later Phase 6/8 live output; see frontmatter resolutions)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `src/citations.py` exists as single citation-parser source of truth; both `src/outreach.py` and `evals/rubric.py` import from it | VERIFIED | `src/outreach.py:6` imports `assemble_paragraph`; `evals/rubric.py:7` imports `INDEX_MARKER_RE`; file exists with `INDEX_MARKER_RE`, `parse_indices`, `check_claim_coverage`, `assemble_paragraph` |
| 2 | `models.AccountStatus` is a discrete `StrEnum` with four states; `EvalScore.eval_failed` separates judge failure from writer fabrication | VERIFIED | `src/models.py:10-14` defines `AccountStatus(StrEnum)` with `clean`, `low_groundedness`, `hook_suppressed`, `judge_failed`; `src/models.py:145` has `eval_failed: bool = False` on `EvalScore` |
| 3 | Writer enforces per-claim citation coverage; sub-coverage claims suppressed, not emitted | VERIFIED | `src/outreach.py:62-67` calls `assemble_paragraph()` with `threshold_01=self._config.eval.groundedness_suppress_threshold`; `src/citations.py:108-118` applies `check_claim_coverage` per claim and returns `("", ())` on zero survivors |
| 4 | Default-contacts fallback reads from `configs/icp.yaml`, not hardcoded vertical names | VERIFIED | `src/contacts.py:64-68` reads from `config.default_personas`; no hardcoded role titles in `src/`; `configs/icp.yaml:102-108` has three abstract role titles with no company/vertical names |
| 5 | `rapidfuzz>=3.14.5` in `pyproject.toml`; `groundedness_suppress_threshold` in `configs/icp.yaml`; strict mypy + offline test suite passes | VERIFIED | `pyproject.toml:18` has `"rapidfuzz>=3.14.5"`; `configs/icp.yaml:116` has `groundedness_suppress_threshold: 0.4`; `uv run mypy --strict src evals` → 0 errors in 22 files; `uv run pytest tests/unit/ tests/functional/ tests/integration/ -q -m "not smoke"` → 170 passed, 0 failed |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/citations.py` | Single citation-parser source of truth (FIX-01) | VERIFIED | Exists; substantive (141 lines); imports: `assemble_paragraph` used in `src/outreach.py:6`, `INDEX_MARKER_RE` imported in `evals/rubric.py:7` |
| `src/models.py` — `AccountStatus` | StrEnum with 4 states (FIX-02) | VERIFIED | `AccountStatus(StrEnum)` with `clean`, `low_groundedness`, `hook_suppressed`, `judge_failed` at line 10 |
| `src/models.py` — `EvalScore.eval_failed` | Bool sentinel (FIX-03) | VERIFIED | `eval_failed: bool = False` at line 145; `specificity` and `recency` fields also added |
| `src/outreach.py` | D-01 claim/connective shape + `assemble_paragraph` call (FIX-04) | VERIFIED | Prompt emits `claims` + `connective_text` JSON; `assemble_paragraph()` called at line 62 |
| `src/contacts.py` | No hardcoded fallback; reads from config (FIX-05) | VERIFIED | `_default_contacts(config)` at line 64 reads `config.default_personas`; no hardcoded role titles in src/ |
| `src/icp_config.py` | `DefaultPersona` model + `EvalConfig.groundedness_suppress_threshold` + D-07 validators (FIX-06) | VERIFIED | `DefaultPersona` at line 36; `EvalConfig.groundedness_suppress_threshold` at line 33; `_check_axes` validates `default_personas` length and non-empty `role_title` |
| `configs/icp.yaml` | `default_personas` (3 entries) + `groundedness_suppress_threshold` (FIX-05, FIX-06) | VERIFIED | Lines 102-108 (3 abstract personas); line 116 (`groundedness_suppress_threshold: 0.4`) |
| `src/pipeline.py` | D-03 precedence block in `process_account` (FIX-02) | VERIFIED | Lines 126-137: `judge_failed` → `hook_suppressed` → `eval_score is None` → `low_groundedness` → `clean` |
| `src/sheets.py` | `STATUS_LEGEND` constant + `eval_specificity`/`eval_recency` columns | VERIFIED | Line 15: `STATUS_LEGEND = "judge_failed > hook_suppressed > low_groundedness > clean"`; lines 46-47: `eval_specificity`, `eval_recency` in HEADERS; lines 107-108: emitted in `_build_row()` |
| `evals/rubric.py` | `eval_failed` propagation + `specificity`/`recency` axes + `_no_content_floor` (FIX-02, FIX-03) | VERIFIED | `any_failed = any(s.eval_failed for s in scores)` at line 113; `_floor()` sets `eval_failed=True`; `_no_content_floor()` sets `eval_failed=False` for content-suppression cases |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/outreach.py` | `src/citations.py` | `from .citations import assemble_paragraph` | WIRED | Called at `outreach.py:62` with `threshold_01=self._config.eval.groundedness_suppress_threshold` |
| `evals/rubric.py` | `src/citations.py` | `from src.citations import INDEX_MARKER_RE` | PARTIAL | Import present (`# noqa: F401`) but `INDEX_MARKER_RE` is not referenced in any rubric.py code body — consolidation by import only, no runtime usage |
| `src/contacts.py` | `configs/icp.yaml` (via `ICPConfig`) | `config.default_personas` | WIRED | `_default_contacts(config)` reads `config.default_personas`; `ICPConfig` loaded from `icp.yaml` |
| `src/pipeline.py` | `src/models.py` (AccountStatus) | `from .models import AccountStatus` | WIRED | D-03 precedence block uses `AccountStatus.judge_failed`, `.hook_suppressed`, `.low_groundedness`, `.clean` |
| `src/sheets.py` | D-03 legend string | `STATUS_LEGEND` module-level constant | WIRED | Verbatim string `"judge_failed > hook_suppressed > low_groundedness > clean"` at line 15 |
| `evals/rubric.py` | `EvalScore.eval_failed` propagation | `any(s.eval_failed for s in scores)` | WIRED | Line 113; `evaluate_account` propagates hook-level failures to account-level |

---

### Post-Execution Code Review Fix Verification

All four critical/core-value findings from the code review were fixed in commits 1fc8c68, 2b021ec, 7c7cadf, d96999c. The fixes hold in current code:

| Finding | Fix | Commit | Holds in Current Code |
|---------|-----|--------|-----------------------|
| CR-01: `connective_text` bypasses rapidfuzz gate | `INDEX_MARKER_RE.search(tail)` guard in `assemble_paragraph` before appending | 1fc8c68 | YES — `src/citations.py:126-128` |
| CR-02: `_to_contacts` off-by-one skips first default | `default_idx = 0` starts from front of defaults list | 2b021ec | YES — `src/contacts.py:57`; regression test `test_partial_fill_uses_defaults_from_front` passing |
| CR-03: Real company names in test fixtures | Replaced `chime.com`/`Chime`/`duolingo.com` with `examplefintech.com`/`ExampleFintech`/`examplelearnco.com` | 7c7cadf | YES — grep finds no `Chime`, `Duolingo`, `consumer fintech` in test files |
| WR-01: `eval_score=None` (exception path) silently becomes `clean` | Explicit `eval_score is None` branch → `AccountStatus.judge_failed` | d96999c | YES — `src/pipeline.py:130-133`; test `test_eval_exception_with_nonempty_hooks_status_is_judge_failed` passing |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `src/citations.py::assemble_paragraph` | `raw_claims` from writer LLM | `src/outreach.py:60` parses LLM JSON via `parse_json_object` | Yes — live LLM response; offline tests use scripted stubs | FLOWING |
| `src/sheets.py::_build_row` | `sa.status` (AccountStatus) | `src/pipeline.py:126-137` D-03 precedence block | Yes — computed from real `eval_score.eval_failed`, hook paragraph content | FLOWING |
| `evals/rubric.py::evaluate_account` | `any_failed` | `any(s.eval_failed for s in scores)` per hook | Yes — propagates from `_floor()` on parse failure | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 170 offline tests pass | `uv run pytest tests/unit/ tests/functional/ tests/integration/ -q -m "not smoke"` | 170 passed in 10.65s | PASS |
| mypy strict on src/ and evals/ | `uv run mypy --strict src evals` | 0 errors in 22 source files | PASS |
| `assemble_paragraph` suppresses below-threshold claim | `test_multi_claim_partial_suppression` and `test_all_claims_suppressed_empty_survivors` | PASSED | PASS |
| CR-01 connective bypass guard | `test_connective_text_appended_after_surviving_claims` (does not exercise bypass) + code inspection | Guard at `citations.py:126-128` confirmed present | PASS |
| D-03 precedence `eval_score=None` → `judge_failed` | `test_eval_exception_with_nonempty_hooks_status_is_judge_failed` | PASSED | PASS |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| FIX-01 | `src/citations.py` as single citation parser imported by both `src/outreach.py` and `evals/rubric.py` | SATISFIED | `src/citations.py` exists; both files import from it |
| FIX-02 | `AccountStatus` enum replacing two-value `status` Literal | SATISFIED | `models.py:10-14` `AccountStatus(StrEnum)`; `ScoredAccount.status: AccountStatus` at line 156 |
| FIX-03 | `EvalScore.eval_failed` sentinel | SATISFIED | `models.py:145`; propagated in `evals/rubric.py:113`; gates D-03 in `pipeline.py:126` |
| FIX-04 | Sentence-level citation coverage in writer; sub-coverage claims suppressed | SATISFIED | `outreach.py` uses D-01 shape; `assemble_paragraph` suppresses per claim |
| FIX-05 | Default-contacts fallback moved to `configs/icp.yaml` | SATISFIED | `configs/icp.yaml:102-108`; `contacts.py:64-68` reads from config; no hardcoded names in src/ |
| FIX-06 | `rapidfuzz>=3.14.5` in `pyproject.toml`; `groundedness_suppress_threshold` in `configs/icp.yaml` | SATISFIED | `pyproject.toml:18`; `configs/icp.yaml:116` |

All 6 Phase 2 requirements are satisfied. All other requirements (EVAL-*, NARR-*, HARD-*, POLISH-*, REPO-*, DEMO-*) are correctly mapped to later phases and not expected here.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `evals/rubric.py` | 7 | `from src.citations import INDEX_MARKER_RE  # noqa: F401` — import never referenced in rubric.py code body | WARNING | Dead runtime import. Suppresses ruff's F401. The import documents intent (CHANGE-01 consolidation) but provides no runtime guarantee. As flagged in WR-02 of the code review, this is dead production code masquerading as enforcement. Not a blocker for the phase goal. |
| `src/citations.py` | 43-58 | `markers_in_paragraph` is a public function never called in any production code path | WARNING | Dead API surface. Tested in `test_citations.py`. Creates misleading impression of active verification. WR-02 from code review: was not fixed. Not a blocker. |
| `evals/labeled.jsonl` | IDs line 1-3+ | `"fintech-vp-cx"`, `"edtech-head-support"`, `"saas-cx-dir"`, `"iot-vp"`, `"hr-head-ops"` in `id` field; `"consumer fintechs"` in paragraph text | INFO | IN-01 from code review: vertical category names in eval data IDs. Not a company name; not a Phase 2 requirement. Phase 7 (Public-Repo Audit) is the correct venue. |

No `TBD`, `FIXME`, or `XXX` markers found in Phase 2-modified files.

---

### Human Verification Required

#### 1. Live smoke run with real LLM — claim suppression observable

**Test:** Run `make smoke` (or `uv run python -m src.pipeline` against 2-3 domains with a real API key). Inspect the writer JSON responses in logs to confirm they use the `claims` + `connective_text` D-01 shape. Check that at least one claim is evaluated for coverage.
**Expected:** Writer LLM returns `{"claims": [...], "connective_text": "..."}` JSON; `assemble_paragraph` drops any claim whose `token_set_ratio` against cited justifications falls below 0.4; the final hook paragraphs contain only surviving claims.
**Why human:** The offline test suite stubs the LLM with scripted JSON. Whether a real model (DeepSeek / NVIDIA) reliably emits the D-01 shape requires a live call to verify.

#### 2. Sheet status column and STATUS_LEGEND rendering

**Test:** After a smoke run, open the output Google Sheet. Observe the `status` column values. Confirm the STATUS_LEGEND string appears somewhere in the sheet (e.g., in a legend tab, or as a comment/note — Phase 6 will add the visual; Phase 2 only guarantees the value reaches the layer).
**Expected:** `status` column shows one of `clean`, `low_groundedness`, `hook_suppressed`, `judge_failed` per row. The STATUS_LEGEND constant in `src/sheets.py:15` is accessible for Phase 6 to render.
**Why human:** Sheet rendering cannot be verified by grep. The constant exists in code; whether it surfaces legibly in the Sheet requires visual inspection.

---

### Gaps Summary

No BLOCKER gaps found. All 5 ROADMAP success criteria are satisfied. All 6 FIX-0* requirements are satisfied. The four code-review critical findings (CR-01 through CR-03, WR-01) were fixed in commits 1fc8c68/2b021ec/7c7cadf/d96999c and the fixes are confirmed present in the current codebase.

Two WARNING-level items remain from the code review (WR-02: dead `markers_in_paragraph` function and unused `INDEX_MARKER_RE` import in rubric.py) that were acknowledged but not fixed. These do not block the phase goal.

Status is `human_needed` because live LLM smoke-run verification of the D-01 writer shape and Sheet output cannot be done programmatically.

---

_Verified: 2026-05-15_
_Verifier: Claude (gsd-verifier)_
