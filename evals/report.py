"""Pure renderer for evals/REPORT.md (Phase 4, NARR-01/02/03).

Reads four committed artifacts (calibration.json, run-log.json, labeled.jsonl,
COVERAGE.md), builds an id -> LabeledExample lookup, computes deterministic
selectors and aggregates, and renders a single Jinja2 template.

Pure transform: zero LLM/judge calls (D-01), byte-stable output (D-05),
metadata sourced from input artifacts not the wall clock. The freshness
precheck (D-06) fails non-zero with a literal refresh command when run-log
is missing or stale.

Six-section structure (D-03) mirrors PITFALLS.md Pitfall 8 question order:
1) example hook with citations, 2) judge rubric, 3) dataset + coverage,
4) headline number, 5) what eval doesn't catch, 6) one worked failure case.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import jinja2
from pydantic import ConfigDict, Field

from evals.agreement import AXES
from evals.run_eval import LabeledExample, load_labeled, to_hook
from src.citations import INDEX_MARKER_RE
from src.models import _Frozen

log = logging.getLogger(__name__)

LABELED_PATH = Path(__file__).parent / "labeled.jsonl"
RUN_LOG_PATH = Path(__file__).parent / "run-log.json"
CALIBRATION_JSON_PATH = Path(__file__).parent / "calibration.json"
COVERAGE_MD_PATH = Path(__file__).parent / "COVERAGE.md"
REPORT_PATH = Path(__file__).parent / "REPORT.md"
TEMPLATE_DIR = Path(__file__).parent / "templates"

REFRESH_COMMAND = "uv run python -m evals.run_eval --split holdout --emit-log"

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------------------
# Run-log schema (consumed; emitted by evals/run_eval.py::_build_run_log_payload)
# ---------------------------------------------------------------------------


class _AxisScores(_Frozen):
    """Five-axis 1-5 score block. Used for run-log row `actual` payload."""

    groundedness: float = Field(ge=1, le=5)
    icp_relevance: float = Field(ge=1, le=5)
    personalization: float = Field(ge=1, le=5)
    specificity: float = Field(ge=1, le=5)
    recency: float = Field(ge=1, le=5)


class _ExpectedScores(_AxisScores):
    """`actual` plus the per-record eval_failed sentinel."""

    eval_failed: bool = False


class RunLogRow(_Frozen):
    id: str
    domain: str
    expected: _ExpectedScores
    actual: _AxisScores
    notes: str | None = None


class RunLog(_Frozen):
    run_date: str
    split: str
    judge_model: str
    judge_provider: str
    n_records: int
    rows: tuple[RunLogRow, ...]


# ---------------------------------------------------------------------------
# Calibration schema (consumed; emitted by evals/run_eval.py::run_calibration)
# ---------------------------------------------------------------------------


class _PerAxisAgreement(_Frozen):
    kappa: float | None
    pct_agree: float | None


class _CalibrationBlock(_Frozen):
    groundedness: _PerAxisAgreement
    icp_relevance: _PerAxisAgreement
    personalization: _PerAxisAgreement
    specificity: _PerAxisAgreement
    recency: _PerAxisAgreement


class Calibration(_Frozen):
    # calibration.json carries Phase-3 fields the renderer does not display
    # (e.g. fail counts); allow them through rather than forcing the emitter
    # to strip them, but lock the three load-bearing sub-blocks via fields.
    model_config = ConfigDict(frozen=True, extra="allow")

    run_date: str
    deepseek_judge: str
    nvidia_judge: str
    n_records: int
    n_valid_for_kappa: int
    inter_judge: _CalibrationBlock
    deepseek_vs_human: _CalibrationBlock
    nvidia_vs_human: _CalibrationBlock


# ---------------------------------------------------------------------------
# Freshness precheck (D-06)
# ---------------------------------------------------------------------------


def _check_freshness(run_log_path: Path, labeled_path: Path) -> None:
    """Fail loud if run-log.json is missing or older than labeled.jsonl.

    The error messages embed the literal refresh command so the operator
    can copy-paste from a CI log without context-switching to docs.
    """
    if not run_log_path.exists():
        raise FileNotFoundError(f"{run_log_path} missing; refresh with: {REFRESH_COMMAND}")
    if run_log_path.stat().st_mtime < labeled_path.stat().st_mtime:
        raise RuntimeError(
            f"{run_log_path} stale (older than {labeled_path});" f" refresh with: {REFRESH_COMMAND}"
        )


# ---------------------------------------------------------------------------
# Selectors (D-04, D-04a, D-07)
# ---------------------------------------------------------------------------


def _select_audit_slice(
    rows: list[RunLogRow],
) -> tuple[RunLogRow, RunLogRow, RunLogRow]:
    """Return (worst, best, median) by (actual.groundedness, id) ascending.

    D-04a: even-count median is the lower-index of the two middles. Using
    `(n - 1) // 2` deterministically picks the lower-of-two on even n.
    """
    if not rows:
        raise ValueError("audit slice requires at least one holdout row")
    sorted_rows = sorted(rows, key=lambda r: (r.actual.groundedness, r.id))
    n = len(sorted_rows)
    worst = sorted_rows[0]
    best = sorted_rows[-1]
    median = sorted_rows[(n - 1) // 2]
    return worst, best, median


def _select_example_hook(examples: list[LabeledExample]) -> LabeledExample:
    """Pick the highest expected_groundedness LabeledExample (id-tiebreak).

    D-07: Section 1's example hook is intentionally a separate selector
    from D-04 so a single record cannot serve both sections.
    """
    if not examples:
        raise ValueError("example hook requires at least one labeled example")
    sorted_examples = sorted(examples, key=lambda ex: (ex.expected_groundedness, ex.id))
    return sorted_examples[-1]


# ---------------------------------------------------------------------------
# Aggregates (D-08)
# ---------------------------------------------------------------------------


def _compute_axis_means(rows: list[RunLogRow]) -> dict[str, float]:
    """Mean of `actual.<axis>` across rows, in canonical AXES order.

    Returning a dict whose keys match AXES makes Section 4's per-axis table
    iteration data-stable for D-05 byte-stability.
    """
    if not rows:
        raise ValueError("axis means require at least one row")
    n = len(rows)
    means: dict[str, float] = {}
    for axis in AXES:
        total = sum(float(getattr(r.actual, axis)) for r in rows)
        means[axis] = total / n
    return means


# ---------------------------------------------------------------------------
# Formatters (D-10)
# ---------------------------------------------------------------------------


def _fmt_kappa(k: float | None) -> str:
    """Format a kappa cell; null renders as `n/a (single-class)` per D-10."""
    if k is None:
        return "n/a (single-class)"
    return f"{k:.3f}"


def _fmt_pct(p: float | None) -> str:
    if p is None:
        return "n/a"
    return f"{p:.1%}"


# ---------------------------------------------------------------------------
# Section 6 claim-vs-evidence pairing
# ---------------------------------------------------------------------------


def _pair_claims_to_evidence(example: LabeledExample) -> list[dict[str, str]]:
    """Walk the paragraph sentence by sentence; pair each [N] to its justification.

    Returns a list of dicts ready for the template to iterate:
        {"claim": str, "indices": str, "evidence_summary": str, "evidence_url": str}

    Sentences without a marker render `indices = "(no citations)"`. Per D-11
    no editorial prose is added; the renderer surfaces only what the labeled
    record already says.
    """
    _, justifications = to_hook(example)
    by_index = {j.index: j for j in justifications}

    paragraph = example.paragraph.strip()
    if not paragraph:
        return []

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
    pairs: list[dict[str, str]] = []
    for sentence in sentences:
        indices: list[int] = []
        for match in INDEX_MARKER_RE.finditer(sentence):
            for piece in match.group(1).split(","):
                try:
                    n = int(piece.strip())
                except ValueError:
                    continue
                if n not in indices:
                    indices.append(n)

        if not indices:
            pairs.append(
                {
                    "claim": sentence,
                    "indices": "(no citations)",
                    "evidence_summary": "",
                    "evidence_url": "",
                }
            )
            continue

        # For the table layout, surface the first index's evidence on the
        # primary row; multi-cite sentences list every index in the marker
        # column. This is byte-stable because indices iteration follows
        # paragraph order.
        primary = indices[0]
        primary_just = by_index.get(primary)
        markers = " ".join(f"[{i}]" for i in indices)
        pairs.append(
            {
                "claim": sentence,
                "indices": markers,
                "evidence_summary": primary_just.summary if primary_just else "",
                "evidence_url": str(primary_just.citation.url) if primary_just else "",
            }
        )
    return pairs


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _build_environment() -> jinja2.Environment:
    """Single locked Jinja2 environment for byte-stable rendering (D-05)."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,
    )


def _split_counts(examples: list[LabeledExample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ex in examples:
        counts[ex.split] = counts.get(ex.split, 0) + 1
    # Stable key order regardless of which splits actually appeared first.
    return {k: counts.get(k, 0) for k in sorted(counts.keys())}


def _calibration_to_table(block: _CalibrationBlock) -> list[dict[str, str]]:
    """Render one calibration sub-block as a per-axis list of formatted rows."""
    return [
        {
            "axis": axis,
            "kappa": _fmt_kappa(getattr(block, axis).kappa),
            "pct_agree": _fmt_pct(getattr(block, axis).pct_agree),
        }
        for axis in AXES
    ]


def _render(
    *,
    run_log: RunLog,
    calibration: Calibration,
    examples: list[LabeledExample],
    coverage_md: str,
) -> str:
    """Build the template context and render the single Jinja2 template.

    Raises KeyError if the audit-slice's worst id is missing from
    labeled.jsonl (B-02 drift gate).
    """
    examples_by_id: dict[str, LabeledExample] = {ex.id: ex for ex in examples}
    rows = list(run_log.rows)
    worst, best, median = _select_audit_slice(rows)

    if worst.id not in examples_by_id:
        raise KeyError(
            f"run-log id {worst.id!r} not found in labeled.jsonl;"
            " the labeled set and the run-log are out of sync"
            f" -- refresh the run-log via: {REFRESH_COMMAND}"
        )

    worst_example = examples_by_id[worst.id]
    example_hook = _select_example_hook(examples)
    example_hook_pairs = _pair_claims_to_evidence(example_hook)
    worst_pairs = _pair_claims_to_evidence(worst_example)

    axis_means = _compute_axis_means(rows)
    headline_groundedness = axis_means["groundedness"]
    axis_mean_rows = [{"axis": axis, "mean": axis_means[axis]} for axis in AXES]

    env = _build_environment()
    template = env.get_template("report.md.j2")

    ctx: dict[str, object] = {
        "run_date": run_log.run_date,
        "split": run_log.split,
        "judge_model": run_log.judge_model,
        "judge_provider": run_log.judge_provider,
        "n_records": run_log.n_records,
        "labeled_count": len(examples),
        "split_counts": _split_counts(examples),
        "coverage_md": coverage_md,
        "headline_groundedness": headline_groundedness,
        "axis_means": axis_mean_rows,
        "example_hook": {
            "id": example_hook.id,
            "domain": example_hook.domain,
            "contact_role": example_hook.contact_role,
            "paragraph": example_hook.paragraph,
            "pairs": example_hook_pairs,
            "expected_groundedness": example_hook.expected_groundedness,
        },
        "worst": {
            "id": worst.id,
            "domain": worst.domain,
            "paragraph": worst_example.paragraph,
            "pairs": worst_pairs,
            "expected": {
                "groundedness": worst.expected.groundedness,
                "icp_relevance": worst.expected.icp_relevance,
                "personalization": worst.expected.personalization,
                "specificity": worst.expected.specificity,
                "recency": worst.expected.recency,
            },
            "actual": {
                "groundedness": worst.actual.groundedness,
                "icp_relevance": worst.actual.icp_relevance,
                "personalization": worst.actual.personalization,
                "specificity": worst.actual.specificity,
                "recency": worst.actual.recency,
            },
        },
        "best": {"id": best.id, "groundedness": best.actual.groundedness},
        "median": {"id": median.id, "groundedness": median.actual.groundedness},
        "calibration": {
            "deepseek_judge": calibration.deepseek_judge,
            "nvidia_judge": calibration.nvidia_judge,
            "n_records": calibration.n_records,
            "n_valid_for_kappa": calibration.n_valid_for_kappa,
            "inter_judge": _calibration_to_table(calibration.inter_judge),
            "deepseek_vs_human": _calibration_to_table(calibration.deepseek_vs_human),
            "nvidia_vs_human": _calibration_to_table(calibration.nvidia_vs_human),
        },
        "axes": list(AXES),
    }

    return template.render(**ctx)


def main() -> int:
    """Render evals/REPORT.md from committed artifacts. Pure, byte-stable, no LLM."""
    _check_freshness(RUN_LOG_PATH, LABELED_PATH)

    run_log = RunLog.model_validate(json.loads(RUN_LOG_PATH.read_text(encoding="utf-8")))
    calibration = Calibration.model_validate(
        json.loads(CALIBRATION_JSON_PATH.read_text(encoding="utf-8"))
    )
    examples = load_labeled(LABELED_PATH)
    coverage_md = COVERAGE_MD_PATH.read_text(encoding="utf-8")

    rendered = _render(
        run_log=run_log,
        calibration=calibration,
        examples=examples,
        coverage_md=coverage_md,
    )
    REPORT_PATH.write_text(rendered, encoding="utf-8")
    log.info("wrote %s", REPORT_PATH)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Render evals/REPORT.md from committed artifacts.")
    parser.parse_args()
    raise SystemExit(main())
