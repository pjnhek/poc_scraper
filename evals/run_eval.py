from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from src.clients.nvidia_client import GenerationParams, NvidiaClient
from src.config import get_settings
from src.models import Citation, Contact, OutreachHook

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
    expected_groundedness: float
    expected_relevance: float
    expected_personalization: float


@dataclass(frozen=True)
class EvalRow:
    example: LabeledExample
    actual_groundedness: float
    actual_relevance: float
    actual_personalization: float
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
                expected_groundedness=float(exp.get("groundedness", 0)),
                expected_relevance=float(exp.get("icp_relevance", 0)),
                expected_personalization=float(exp.get("personalization", 0)),
            )
        )
    return examples


def to_hook(example: LabeledExample) -> OutreachHook:
    citations = tuple(Citation.make(url=u, source="exa") for u in example.citation_urls)
    return OutreachHook(
        contact=Contact(role_title=example.contact_role, rationale="(eval fixture)"),
        paragraph=example.paragraph,
        citations=citations,
    )


def markdown_table(rows: list[EvalRow]) -> str:
    lines = [
        "| id | groundedness (act / exp) | icp_relevance (act / exp) | personalization (act / exp) | notes |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.example.id} "
            f"| {r.actual_groundedness:.1f} / {r.example.expected_groundedness:.1f} "
            f"| {r.actual_relevance:.1f} / {r.example.expected_relevance:.1f} "
            f"| {r.actual_personalization:.1f} / {r.example.expected_personalization:.1f} "
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
    return (
        f"mean abs error: groundedness={g:.2f}, icp_relevance={i:.2f}, " f"personalization={p:.2f}"
    )


async def run() -> int:
    settings = get_settings()
    if not settings.nvidia_api_key:
        log.error("NVIDIA_API_KEY is not set; cannot run eval.")
        return 1

    examples = load_labeled()
    client = NvidiaClient(
        api_key=settings.nvidia_api_key,
        model=settings.judge_model,
        params=GenerationParams(
            temperature=settings.judge_temperature,
            top_p=settings.judge_top_p,
            max_tokens=settings.judge_max_tokens,
        ),
    )
    rubric = EvalRubric(client)

    rows: list[EvalRow] = []
    for ex in examples:
        score = await rubric.evaluate_hook(to_hook(ex), ex.domain)
        rows.append(
            EvalRow(
                example=ex,
                actual_groundedness=score.groundedness,
                actual_relevance=score.icp_relevance,
                actual_personalization=score.personalization,
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
