from __future__ import annotations

from pathlib import Path

from evals.run_eval import EvalRow, LabeledExample, load_labeled, markdown_table, summary_line


def _ex(id_: str = "x", g: float = 8, i: float = 8, p: float = 8) -> LabeledExample:
    return LabeledExample(
        id=id_,
        domain="x.com",
        contact_role="VP CX",
        paragraph="p",
        citation_urls=["https://x.com/a"],
        expected_groundedness=g,
        expected_relevance=i,
        expected_personalization=p,
    )


def _row(ex: LabeledExample, g: float, i: float, p: float, notes: str = "ok") -> EvalRow:
    return EvalRow(
        example=ex,
        actual_groundedness=g,
        actual_relevance=i,
        actual_personalization=p,
        notes=notes,
    )


def test_loads_seed_labeled_jsonl() -> None:
    seed = Path(__file__).parents[2] / "evals" / "labeled.jsonl"
    examples = load_labeled(seed)
    assert len(examples) == 5
    assert all(ex.id for ex in examples)
    assert all(0 <= ex.expected_groundedness <= 10 for ex in examples)


def test_markdown_table_has_header_and_one_row_per_example() -> None:
    ex = _ex()
    rows = [_row(ex, 9, 8, 8)]
    md = markdown_table(rows)
    assert md.splitlines()[0].startswith("|")
    assert "9.0 / 8.0" in md
    assert md.count("\n") == 2  # header + separator + 1 row -> 2 newlines


def test_summary_reports_mean_abs_error() -> None:
    ex = _ex(g=10, i=10, p=10)
    rows = [
        _row(ex, 8, 9, 7),
        _row(ex, 9, 10, 8),
    ]
    s = summary_line(rows)
    assert "groundedness=1.50" in s
    assert "icp_relevance=0.50" in s
    assert "personalization=2.50" in s


def test_summary_handles_empty() -> None:
    assert summary_line([]) == "(no examples)"
