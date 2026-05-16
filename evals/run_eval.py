from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from evals.agreement import AXES, cohen_kappa_linear, pct_agreement
from src.clients.nvidia_client import NVIDIA_BASE_URL, GenerationParams, NvidiaClient
from src.config import Settings, get_settings
from src.models import Citation, Contact, Justification, OutreachHook
from src.pipeline import build_judge_client

from .rubric import EvalRubric

log = logging.getLogger(__name__)

LABELED_PATH = Path(__file__).parent / "labeled.jsonl"


@dataclass(frozen=True)
class LabeledExample:
    id: str
    domain: str
    contact_role: str
    paragraph: str
    citation_urls: list[str]
    justifications: list[dict[str, object]]  # [{index, summary, url}]
    cited_indices: list[int]
    split: str  # "train" | "holdout"
    coverage_cells: list[str]  # explicit cell tags per D-04
    expected_groundedness: float
    expected_relevance: float
    expected_personalization: float
    expected_specificity: float
    expected_recency: float
    expected_eval_failed: bool


@dataclass(frozen=True)
class EvalRow:
    example: LabeledExample
    actual_groundedness: float
    actual_relevance: float
    actual_personalization: float
    actual_specificity: float
    actual_recency: float
    notes: str | None


def load_labeled(path: Path = LABELED_PATH) -> list[LabeledExample]:
    examples: list[LabeledExample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        exp = d.get("expected", {})
        examples.append(
            LabeledExample(
                id=d["id"],
                domain=d["domain"],
                contact_role=d["contact_role"],
                paragraph=d["paragraph"],
                citation_urls=list(d.get("citation_urls", [])),
                justifications=list(d.get("justifications", [])),
                cited_indices=[int(i) for i in d.get("cited_indices", [])],
                split=str(d.get("split", "train")),
                coverage_cells=list(d.get("coverage_cells", [])),
                expected_groundedness=float(exp.get("groundedness", 0)),
                expected_relevance=float(exp.get("icp_relevance", 0)),
                expected_personalization=float(exp.get("personalization", 0)),
                expected_specificity=float(exp.get("specificity", 1.0)),
                expected_recency=float(exp.get("recency", 1.0)),
                expected_eval_failed=bool(exp.get("eval_failed", False)),
            )
        )
    return examples


def to_hook(example: LabeledExample) -> tuple[OutreachHook, tuple[Justification, ...]]:
    # Return justifications alongside hook so evaluate_hook receives real evidence.
    # The labeled set embeds justifications so the judge can evaluate claims fairly.
    justs = tuple(
        Justification(
            index=cast(int, j["index"]),
            summary=str(j["summary"]),
            citation=Citation.make(str(j["url"]), source="exa"),
        )
        for j in example.justifications
    )
    cited = (
        tuple(example.cited_indices)
        if example.cited_indices
        else tuple(range(1, len(example.citation_urls) + 1))
    )
    hook = OutreachHook(
        contact=Contact(role_title=example.contact_role, rationale="(eval fixture)"),
        paragraph=example.paragraph,
        cited_indices=cited,
    )
    return hook, justs


def markdown_table(rows: list[EvalRow]) -> str:
    lines = [
        "| id | groundedness (act / exp) | icp_relevance (act / exp)"
        " | personalization (act / exp) | specificity (act / exp)"
        " | recency (act / exp) | notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.example.id} "
            f"| {r.actual_groundedness:.1f} / {r.example.expected_groundedness:.1f} "
            f"| {r.actual_relevance:.1f} / {r.example.expected_relevance:.1f} "
            f"| {r.actual_personalization:.1f} / {r.example.expected_personalization:.1f} "
            f"| {r.actual_specificity:.1f} / {r.example.expected_specificity:.1f} "
            f"| {r.actual_recency:.1f} / {r.example.expected_recency:.1f} "
            f"| {r.notes or ''} |"
        )
    return "\n".join(lines)


def summary_line(rows: list[EvalRow]) -> str:
    if not rows:
        return "(no examples)"
    g = sum(abs(r.actual_groundedness - r.example.expected_groundedness) for r in rows) / len(rows)
    i = sum(abs(r.actual_relevance - r.example.expected_relevance) for r in rows) / len(rows)
    p = sum(abs(r.actual_personalization - r.example.expected_personalization) for r in rows) / len(
        rows
    )
    s = sum(abs(r.actual_specificity - r.example.expected_specificity) for r in rows) / len(rows)
    rc = sum(abs(r.actual_recency - r.example.expected_recency) for r in rows) / len(rows)
    return (
        f"mean abs error: groundedness={g:.2f}, icp_relevance={i:.2f},"
        f" personalization={p:.2f}, specificity={s:.2f}, recency={rc:.2f}"
    )


async def run(split_filter: str | None = None) -> int:
    settings = get_settings()
    if settings.resolved_provider == "deepseek" and not settings.deepseek_api_key:
        log.error("DEEPSEEK_API_KEY is not set; cannot run eval.")
        return 1
    if settings.resolved_provider == "nvidia" and not settings.nvidia_api_key:
        log.error("NVIDIA_API_KEY is not set; cannot run eval.")
        return 1

    examples = load_labeled()
    if split_filter is not None:
        examples = [ex for ex in examples if ex.split == split_filter]
    rubric = EvalRubric(build_judge_client(settings))

    rows: list[EvalRow] = []
    for ex in examples:
        hook, justs = to_hook(ex)
        score = await rubric.evaluate_hook(hook, ex.domain, justs)
        rows.append(
            EvalRow(
                example=ex,
                actual_groundedness=score.groundedness,
                actual_relevance=score.icp_relevance,
                actual_personalization=score.personalization,
                actual_specificity=score.specificity,
                actual_recency=score.recency,
                notes=score.notes,
            )
        )

    print(markdown_table(rows))
    print()
    print(summary_line(rows))
    return 0


def _require_calibration_keys(settings: Settings) -> None:
    """Fail fast before any API call if both judge keys are not set."""
    missing: list[str] = []
    if not settings.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if not settings.nvidia_api_key:
        missing.append("NVIDIA_API_KEY")
    if missing:
        raise RuntimeError(
            f"cross-family calibration requires both judge keys: {', '.join(missing)}. "
            "See .env.example."
        )


def build_nvidia_judge_client(settings: Settings) -> NvidiaClient:
    """Build NVIDIA judge explicitly for cross-family calibration (D-08).

    Called regardless of settings.resolved_provider so the DeepSeek and NVIDIA
    families always both score the full labeled set.
    """
    return NvidiaClient(
        api_key=settings.nvidia_api_key,
        base_url=NVIDIA_BASE_URL,
        model=settings.judge_model_nvidia,
        max_in_flight=settings.llm_max_in_flight,
        params=GenerationParams(
            temperature=settings.judge_temperature,
            top_p=settings.judge_top_p,
            max_tokens=settings.judge_max_tokens,
            reasoning_budget=settings.judge_reasoning_budget,
            json_mode=False,
        ),
    )


# Axis name in AXES -> LabeledExample attribute name for expected label.
_AXIS_TO_EXPECTED: dict[str, str] = {
    "groundedness": "expected_groundedness",
    "icp_relevance": "expected_relevance",
    "personalization": "expected_personalization",
    "specificity": "expected_specificity",
    "recency": "expected_recency",
}

# Axis name in AXES -> EvalScore attribute name for actual score.
_AXIS_TO_ACTUAL: dict[str, str] = {
    "groundedness": "groundedness",
    "icp_relevance": "icp_relevance",
    "personalization": "personalization",
    "specificity": "specificity",
    "recency": "recency",
}


async def run_calibration() -> int:
    """Score the full labeled set with both judges; write CALIBRATION.md and calibration.json.

    Excludes eval_failed=True examples from kappa computation and reports
    judge-failure rate separately (D-08, RESEARCH.md Pitfall E).
    """
    import datetime

    settings = get_settings()
    _require_calibration_keys(settings)

    examples = load_labeled()
    n_total = len(examples)
    log.info("run_calibration: loaded %d labeled examples", n_total)

    deepseek_rubric = EvalRubric(build_judge_client(settings))
    nvidia_rubric = EvalRubric(build_nvidia_judge_client(settings))

    from src.models import EvalScore

    async def _safe_judge(
        rubric: EvalRubric,
        judge_name: str,
        hook: OutreachHook,
        domain: str,
        justs: tuple[Justification, ...],
    ) -> EvalScore:
        """Score one hook, converting any raised provider error into a judge-failure.

        A persistently-timing-out judge (the NVIDIA free-tier endpoint exhausting
        its tenacity retries, or the known DeepSeek empty-content flake reraising)
        must NOT abort the whole 25-record calibration run. The failed record is
        marked eval_failed=True so it is excluded from kappa and counted in the
        per-judge failure rate.
        """
        try:
            return await rubric.evaluate_hook(hook, domain, justs)
        except Exception as exc:  # noqa: BLE001 -- provider errors are heterogeneous
            log.warning("%s judge raised %s: %s", judge_name, type(exc).__name__, exc)
            return EvalScore(
                groundedness=1,
                icp_relevance=1,
                personalization=1,
                specificity=1,
                recency=1,
                eval_failed=True,
                notes=f"(judge call raised {type(exc).__name__})",
            )

    ds_scores: list[EvalScore] = []
    nv_scores: list[EvalScore] = []

    for ex in examples:
        hook, justs = to_hook(ex)
        ds_score = await _safe_judge(deepseek_rubric, "DeepSeek", hook, ex.domain, justs)
        nv_score = await _safe_judge(nvidia_rubric, "NVIDIA", hook, ex.domain, justs)
        ds_scores.append(ds_score)
        nv_scores.append(nv_score)
        log.info(
            "scored %s: ds_failed=%s nv_failed=%s",
            ex.id,
            ds_score.eval_failed,
            nv_score.eval_failed,
        )

    # Track judge-failure counts before filtering for kappa.
    ds_fail_count = sum(1 for s in ds_scores if s.eval_failed)
    nv_fail_count = sum(1 for s in nv_scores if s.eval_failed)

    # Filter to examples where NEITHER judge failed AND the example is not
    # a deliberate judge-failure sentinel (expected_eval_failed=True).
    # Both flags can differ; use the union to keep kappa computation clean.
    valid_indices = [
        i
        for i, ex in enumerate(examples)
        if not ex.expected_eval_failed
        and not ds_scores[i].eval_failed
        and not nv_scores[i].eval_failed
    ]
    n_valid = len(valid_indices)
    log.info(
        "run_calibration: %d of %d examples used for kappa (ds_failed=%d, nv_failed=%d)",
        n_valid,
        n_total,
        ds_fail_count,
        nv_fail_count,
    )

    # Per-axis kappa for all three pairs.
    inter_judge: dict[str, dict[str, float]] = {}
    ds_vs_human: dict[str, dict[str, float]] = {}
    nv_vs_human: dict[str, dict[str, float]] = {}
    single_class_notes: list[str] = []

    for axis in AXES:
        exp_attr = _AXIS_TO_EXPECTED[axis]
        act_attr = _AXIS_TO_ACTUAL[axis]
        human_vals = [float(getattr(examples[i], exp_attr)) for i in valid_indices]
        ds_vals = [float(getattr(ds_scores[i], act_attr)) for i in valid_indices]
        nv_vals = [float(getattr(nv_scores[i], act_attr)) for i in valid_indices]

        if n_valid == 0:
            inter_judge[axis] = {"kappa": 0.0, "pct_agree": 0.0}
            ds_vs_human[axis] = {"kappa": 0.0, "pct_agree": 0.0}
            nv_vs_human[axis] = {"kappa": 0.0, "pct_agree": 0.0}
            continue

        nv_ds_kappa = cohen_kappa_linear(nv_vals, ds_vals)
        nv_ds_pct = pct_agreement(nv_vals, ds_vals)
        ds_h_kappa = cohen_kappa_linear(ds_vals, human_vals)
        ds_h_pct = pct_agreement(ds_vals, human_vals)
        nv_h_kappa = cohen_kappa_linear(nv_vals, human_vals)
        nv_h_pct = pct_agreement(nv_vals, human_vals)

        # Document single-class kappa collapse (agreement.py returns 1.0 with k==1 guard).
        for pair_name, kappa_val, labels_a, labels_b in [
            ("NVIDIA vs DeepSeek", nv_ds_kappa, nv_vals, ds_vals),
            ("DeepSeek vs human", ds_h_kappa, ds_vals, human_vals),
            ("NVIDIA vs human", nv_h_kappa, nv_vals, human_vals),
        ]:
            if kappa_val == 1.0:
                all_same_a = len(set(labels_a)) == 1
                all_same_b = len(set(labels_b)) == 1
                if all_same_a or all_same_b:
                    single_class_notes.append(
                        f"{axis} ({pair_name}): NOTE: single-class, kappa undefined"
                    )

        inter_judge[axis] = {"kappa": round(nv_ds_kappa, 3), "pct_agree": round(nv_ds_pct, 3)}
        ds_vs_human[axis] = {"kappa": round(ds_h_kappa, 3), "pct_agree": round(ds_h_pct, 3)}
        nv_vs_human[axis] = {"kappa": round(nv_h_kappa, 3), "pct_agree": round(nv_h_pct, 3)}

    run_date = datetime.date.today().isoformat()
    ds_judge_name = settings.judge_model_deepseek
    nv_judge_name = settings.judge_model_nvidia

    out_dir = Path(__file__).parent

    # Write calibration.json (machine-readable sidecar for Phase 4).
    calib_json = {
        "run_date": run_date,
        "deepseek_judge": ds_judge_name,
        "nvidia_judge": nv_judge_name,
        "n_records": n_total,
        "n_valid_for_kappa": n_valid,
        "deepseek_fail_count": ds_fail_count,
        "nvidia_fail_count": nv_fail_count,
        "inter_judge": inter_judge,
        "deepseek_vs_human": ds_vs_human,
        "nvidia_vs_human": nv_vs_human,
    }
    json_path = out_dir / "calibration.json"
    json_path.write_text(json.dumps(calib_json, indent=2) + "\n", encoding="utf-8")
    log.info("wrote %s", json_path)

    # Write CALIBRATION.md (human-readable artifact).
    def _kappa_row(axis: str, data: dict[str, dict[str, float]]) -> str:
        k = data[axis]["kappa"]
        p = data[axis]["pct_agree"]
        return f"| {axis} | {k:.3f} | {p:.1%} |"

    def _accuracy_row(axis: str) -> str:
        ds_k = ds_vs_human[axis]["kappa"]
        ds_p = ds_vs_human[axis]["pct_agree"]
        nv_k = nv_vs_human[axis]["kappa"]
        nv_p = nv_vs_human[axis]["pct_agree"]
        return f"| {axis} | {ds_k:.3f} ({ds_p:.1%}) | {nv_k:.3f} ({nv_p:.1%}) |"

    inter_rows = "\n".join(_kappa_row(ax, inter_judge) for ax in AXES)
    accuracy_rows = "\n".join(_accuracy_row(ax) for ax in AXES)

    notes_lines: list[str] = [
        f"- Records scored: {n_total} (train + holdout combined; D-08 full-set requirement).",
        f"- Records excluded from kappa: {n_total - n_valid}"
        f" (expected_eval_failed=True or judge failure).",
        f"- DeepSeek judge failures: {ds_fail_count}.",
        f"- NVIDIA judge failures: {nv_fail_count}.",
    ]
    if single_class_notes:
        notes_lines.append("- Single-class kappa (kappa undefined, reported as 1.0):")
        for note in single_class_notes:
            notes_lines.append(f"  - {note}")

    notes_block = "\n".join(notes_lines)

    md_content = (
        f"# Phase 3: Cross-Family Calibration\n\n"
        f"**Run date:** {run_date}\n"
        f"**DeepSeek judge:** {ds_judge_name}"
        f" (thinking enabled, reasoning_effort={settings.judge_reasoning_effort_deepseek})\n"
        f"**NVIDIA judge:** {nv_judge_name}\n"
        f"**Records scored:** {n_total}"
        f" (all, including train + holdout; eval_failed excluded from kappa)\n\n"
        f"## Inter-Judge Agreement (NVIDIA vs DeepSeek)\n\n"
        f"| Axis | Kappa (linear-weighted) | % Exact Agreement |\n"
        f"|------|------------------------|-------------------|\n"
        f"{inter_rows}\n\n"
        f"## Judge Accuracy vs Human Labels\n\n"
        f"| Axis | DeepSeek kappa vs human (% agree) | NVIDIA kappa vs human (% agree) |\n"
        f"|------|----------------------------------|--------------------------------|\n"
        f"{accuracy_rows}\n\n"
        f"## Notes\n\n"
        f"{notes_block}\n"
    )

    md_path = out_dir / "CALIBRATION.md"
    md_path.write_text(md_content, encoding="utf-8")
    log.info("wrote %s", md_path)

    print(f"Calibration complete. Records: {n_total}, valid for kappa: {n_valid}.")
    print(f"Artifacts: {md_path}, {json_path}")
    return 0


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run eval harness or cross-family calibration.")
    parser.add_argument(
        "--calibration",
        action="store_true",
        help="Run cross-family calibration (both judges) instead of the default eval run.",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Filter labeled examples by split ('train' or 'holdout').",
    )
    args = parser.parse_args()
    if args.calibration:
        raise SystemExit(asyncio.run(run_calibration()))
    else:
        raise SystemExit(asyncio.run(run(split_filter=args.split)))
