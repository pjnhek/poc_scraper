from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from src.config import get_settings
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(run()))
