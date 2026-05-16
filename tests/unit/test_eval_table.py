from __future__ import annotations

from pathlib import Path

from evals.run_eval import EvalRow, LabeledExample, load_labeled, markdown_table, summary_line


def _ex(id_: str = "x", g: float = 4.0, i: float = 4.0, p: float = 4.0) -> LabeledExample:
    return LabeledExample(
        id=id_,
        domain="x.com",
        contact_role="VP CX",
        paragraph="p",
        citation_urls=["https://x.com/a"],
        justifications=[],
        cited_indices=[],
        split="train",
        coverage_cells=["rich-enrichment"],
        expected_groundedness=g,
        expected_relevance=i,
        expected_personalization=p,
        expected_specificity=3.0,
        expected_recency=3.0,
        expected_eval_failed=False,
    )


def _row(ex: LabeledExample, g: float, i: float, p: float, notes: str = "ok") -> EvalRow:
    return EvalRow(
        example=ex,
        actual_groundedness=g,
        actual_relevance=i,
        actual_personalization=p,
        actual_specificity=3.0,
        actual_recency=3.0,
        notes=notes,
    )


def test_loads_seed_labeled_jsonl() -> None:
    seed = Path(__file__).parents[2] / "evals" / "labeled.jsonl"
    examples = load_labeled(seed)
    assert len(examples) >= 1
    assert all(ex.id for ex in examples)
    assert all(1.0 <= ex.expected_groundedness <= 5.0 for ex in examples)


def test_markdown_table_has_header_and_one_row_per_example() -> None:
    ex = _ex()
    rows = [_row(ex, 4.5, 4.0, 4.0)]
    md = markdown_table(rows)
    assert md.splitlines()[0].startswith("|")
    assert "4.5 / 4.0" in md
    assert md.count("\n") == 2  # header + separator + 1 row -> 2 newlines


def test_summary_reports_mean_abs_error() -> None:
    ex = _ex(g=5.0, i=5.0, p=5.0)
    rows = [
        _row(ex, 3.0, 4.0, 2.0),
        _row(ex, 4.0, 5.0, 3.0),
    ]
    s = summary_line(rows)
    assert "groundedness=1.50" in s
    assert "icp_relevance=0.50" in s
    assert "personalization=2.50" in s


def test_summary_handles_empty() -> None:
    assert summary_line([]) == "(no examples)"
