from __future__ import annotations

from pathlib import Path

from evals.run_eval import (
    EvalRow,
    LabeledExample,
    _build_run_log_payload,
    load_labeled,
    markdown_table,
    summary_line,
)
from src.config import Settings


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


def _row(ex: LabeledExample, g: float, i: float, p: float, notes: str | None = "ok") -> EvalRow:
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


def test_run_log_payload_schema() -> None:
    # Unit test for the --emit-log payload builder. Asserts every row has
    # exactly the documented five expected and five actual axes (1-5
    # floats), eval_failed is bool, notes is str | None, and the top-level
    # metadata fields are present. Guards the contract Plan 02's pydantic
    # loader will consume with extra="forbid".
    ex_a = _ex(id_="a1", g=4.0, i=5.0, p=3.0)
    ex_b = _ex(id_="b2", g=2.0, i=3.0, p=4.0)
    rows = [
        _row(ex_a, 4.5, 5.0, 3.0),
        _row(ex_b, 2.5, 3.0, 4.0, notes=None),
    ]
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        deepseek_api_key="ds-key",
        llm_provider="deepseek",
    )

    payload = _build_run_log_payload(rows, "holdout", settings)

    assert set(payload.keys()) == {
        "run_date",
        "split",
        "judge_model",
        "judge_provider",
        "n_records",
        "rows",
    }
    assert payload["split"] == "holdout"
    assert payload["judge_provider"] == "deepseek"
    assert payload["n_records"] == 2

    row_list = payload["rows"]
    assert isinstance(row_list, list)
    assert len(row_list) == 2

    expected_axes = {"groundedness", "icp_relevance", "personalization", "specificity", "recency"}
    for row in row_list:
        assert set(row.keys()) == {"id", "domain", "expected", "actual", "notes"}
        assert set(row["expected"].keys()) == expected_axes | {"eval_failed"}
        assert set(row["actual"].keys()) == expected_axes
        for axis in expected_axes:
            v_exp = row["expected"][axis]
            v_act = row["actual"][axis]
            assert isinstance(v_exp, float)
            assert isinstance(v_act, float)
            assert 1.0 <= v_exp <= 5.0
            assert 1.0 <= v_act <= 5.0
        assert isinstance(row["expected"]["eval_failed"], bool)
        assert row["notes"] is None or isinstance(row["notes"], str)


def test_run_log_payload_split_none_renders_as_all() -> None:
    # Edge case: when no --split filter is supplied, the payload records
    # "all" so Plan 02's loader can distinguish a full-set run from a
    # holdout-only run without re-deriving from rows.
    ex = _ex()
    rows = [_row(ex, 4.0, 4.0, 4.0)]
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        deepseek_api_key="ds-key",
        llm_provider="deepseek",
    )

    payload = _build_run_log_payload(rows, None, settings)

    assert payload["split"] == "all"
