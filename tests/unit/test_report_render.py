"""Unit tests for evals/report.py — the pure renderer.

The renderer reads four committed artifacts (calibration.json, run-log.json,
labeled.jsonl, COVERAGE.md), builds an id -> LabeledExample lookup, computes
deterministic selectors + aggregates, and renders one Jinja2 template.

These tests cover every renderer helper plus the integration seams that the
plan calls out as gates:
- audit-slice selector (D-04 / D-04a tiebreak)
- example-hook selector (D-07)
- id -> LabeledExample lookup feeding Section 6 (B-02)
- kappa-null formatter (D-10)
- calibration sub-table ingestion (W-04)
- byte-stability (D-05)
- freshness precheck error message (D-06)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.agreement import AXES
from evals.report import (
    Calibration,
    RunLog,
    RunLogRow,
    _AxisScores,
    _check_freshness,
    _compute_axis_means,
    _ExpectedScores,
    _fmt_kappa,
    _fmt_pct,
    _pair_claims_to_evidence,
    _render,
    _select_audit_slice,
    _select_example_hook,
)
from evals.run_eval import LabeledExample


def _ex(
    id_: str,
    *,
    expected_groundedness: float = 4.0,
    paragraph: str = "Sample claim [1]. Another claim [2].",
    justifications: list[dict[str, object]] | None = None,
) -> LabeledExample:
    """Build a synthetic LabeledExample. The renderer only reads a subset of fields."""
    if justifications is None:
        justifications = [
            {"index": 1, "summary": "Evidence one summary.", "url": "https://example.test/a"},
            {"index": 2, "summary": "Evidence two summary.", "url": "https://example.test/b"},
        ]
    return LabeledExample(
        id=id_,
        domain=f"{id_}.com",
        contact_role="VP CX",
        paragraph=paragraph,
        citation_urls=["https://example.test/a", "https://example.test/b"],
        justifications=justifications,
        cited_indices=[1, 2],
        split="holdout",
        coverage_cells=["rich-enrichment"],
        expected_groundedness=expected_groundedness,
        expected_relevance=3.0,
        expected_personalization=3.0,
        expected_specificity=3.0,
        expected_recency=3.0,
        expected_eval_failed=False,
    )


def _row(
    id_: str,
    *,
    groundedness: float,
    expected_groundedness: float = 4.0,
) -> RunLogRow:
    return RunLogRow(
        id=id_,
        domain=f"{id_}.com",
        expected=_ExpectedScores(
            groundedness=expected_groundedness,
            icp_relevance=3.0,
            personalization=3.0,
            specificity=3.0,
            recency=3.0,
            eval_failed=False,
        ),
        actual=_AxisScores(
            groundedness=groundedness,
            icp_relevance=3.0,
            personalization=3.0,
            specificity=3.0,
            recency=3.0,
        ),
        notes=None,
    )


def _calibration_block(value: float | None = 0.3) -> dict[str, dict[str, float | None]]:
    return {
        "groundedness": {"kappa": value, "pct_agree": 0.5},
        "icp_relevance": {"kappa": value, "pct_agree": 0.5},
        "personalization": {"kappa": value, "pct_agree": 0.5},
        "specificity": {"kappa": value, "pct_agree": 0.5},
        "recency": {"kappa": value, "pct_agree": 0.5},
    }


def _synthetic_calibration_payload() -> dict[str, object]:
    return {
        "run_date": "2026-05-21",
        "deepseek_judge": "deepseek-v4-flash",
        "nvidia_judge": "moonshot-v1-32k",
        "n_records": 25,
        "n_valid_for_kappa": 24,
        "deepseek_fail_count": 0,
        "nvidia_fail_count": 0,
        "inter_judge": _calibration_block(0.176),
        "deepseek_vs_human": _calibration_block(0.277),
        "nvidia_vs_human": _calibration_block(0.198),
    }


def _synthetic_run_log_payload(rows: list[RunLogRow]) -> dict[str, object]:
    return {
        "run_date": "2026-05-21",
        "split": "holdout",
        "judge_model": "deepseek-v4-flash",
        "judge_provider": "deepseek",
        "n_records": len(rows),
        "rows": [
            {
                "id": r.id,
                "domain": r.domain,
                "expected": {
                    "groundedness": r.expected.groundedness,
                    "icp_relevance": r.expected.icp_relevance,
                    "personalization": r.expected.personalization,
                    "specificity": r.expected.specificity,
                    "recency": r.expected.recency,
                    "eval_failed": r.expected.eval_failed,
                },
                "actual": {
                    "groundedness": r.actual.groundedness,
                    "icp_relevance": r.actual.icp_relevance,
                    "personalization": r.actual.personalization,
                    "specificity": r.actual.specificity,
                    "recency": r.actual.recency,
                },
                "notes": r.notes,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# _select_audit_slice (D-04, D-04a)
# ---------------------------------------------------------------------------


def test_select_audit_slice_worst_best_median() -> None:
    rows = [
        _row("a", groundedness=4.0),
        _row("b", groundedness=2.0),
        _row("c", groundedness=5.0),
        _row("d", groundedness=3.0),
        _row("e", groundedness=1.0),
    ]
    worst, best, median = _select_audit_slice(rows)
    assert worst.id == "e"
    assert best.id == "c"
    # Sorted ascending by score: e(1), b(2), d(3), a(4), c(5). n=5 -> median idx (5-1)//2 = 2 -> d.
    assert median.id == "d"


def test_select_audit_slice_even_count_median_is_lower_of_two() -> None:
    # D-04a: even-count median is the lower-INDEX of the two middles (sorted asc).
    # With 4 rows sorted ascending, indices 1 and 2 are the two middles.
    # (n-1)//2 = (4-1)//2 = 1 -> the lower-index one.
    rows = [
        _row("a", groundedness=1.0),
        _row("b", groundedness=2.0),
        _row("c", groundedness=3.0),
        _row("d", groundedness=4.0),
    ]
    _, _, median = _select_audit_slice(rows)
    assert median.id == "b"


def test_select_audit_slice_id_tiebreak() -> None:
    # Two rows with identical groundedness: order by id ascending.
    rows = [
        _row("z-second", groundedness=3.0),
        _row("a-first", groundedness=3.0),
    ]
    worst, best, _ = _select_audit_slice(rows)
    assert worst.id == "a-first"
    assert best.id == "z-second"


def test_select_audit_slice_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _select_audit_slice([])


# ---------------------------------------------------------------------------
# _select_example_hook (D-07)
# ---------------------------------------------------------------------------


def test_select_example_hook_highest_expected_groundedness() -> None:
    examples = [
        _ex("a", expected_groundedness=3.0),
        _ex("b", expected_groundedness=5.0),
        _ex("c", expected_groundedness=4.0),
    ]
    chosen = _select_example_hook(examples)
    assert chosen.id == "b"


def test_select_example_hook_id_tiebreak_returns_highest_id() -> None:
    # Two records tied at the maximum expected_groundedness: pick the
    # highest id after sorting by (score, id) ascending and taking the last.
    examples = [
        _ex("a", expected_groundedness=5.0),
        _ex("z", expected_groundedness=5.0),
    ]
    chosen = _select_example_hook(examples)
    assert chosen.id == "z"


def test_select_example_hook_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _select_example_hook([])


# ---------------------------------------------------------------------------
# examples_by_id lookup (B-02)
# ---------------------------------------------------------------------------


def test_examples_by_id_lookup_finds_worst_record() -> None:
    examples = [
        _ex("alpha", paragraph="alpha paragraph [1]."),
        _ex("beta", paragraph="beta paragraph [1]."),
        _ex("gamma", paragraph="gamma paragraph [1]."),
    ]
    rows = [
        _row("alpha", groundedness=4.0),
        _row("beta", groundedness=1.0),
        _row("gamma", groundedness=3.0),
    ]
    examples_by_id = {ex.id: ex for ex in examples}
    worst, _, _ = _select_audit_slice(rows)
    assert worst.id == "beta"
    matched = examples_by_id[worst.id]
    assert matched.paragraph == "beta paragraph [1]."
    assert matched.paragraph != ""


def test_examples_by_id_lookup_missing_id_raises() -> None:
    # When _render is asked to build Section 6 using a run-log id that is
    # NOT present in labeled.jsonl, the lookup MUST raise loud (KeyError)
    # with a message that names the --emit-log refresh command so the
    # operator knows how to resync.
    examples = [_ex("alpha"), _ex("gamma")]
    rows = [_row("beta", groundedness=1.0)]  # 'beta' is NOT in examples
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    with pytest.raises(KeyError, match="--emit-log"):
        _render(
            run_log=run_log,
            calibration=calib,
            examples=examples,
            coverage_md="# coverage\n",
        )


def test_section_6_renders_claim_evidence_pairs_from_labeled_record() -> None:
    # Render the template against a fixture run-log + matching labeled
    # record; assert Section 6 contains the worst record's paragraph
    # verbatim AND at least one [N] claim-evidence pair derived from its
    # justifications. This is the integration seam from B-02.
    paragraph = "Acme launched payroll [1]. Acme grew headcount [2]."
    worst_example = _ex(
        "worst-record",
        paragraph=paragraph,
        expected_groundedness=2.0,
    )
    best_example = _ex("best-record", expected_groundedness=5.0)
    examples = [worst_example, best_example]
    rows = [
        _row("worst-record", groundedness=1.0),
        _row("best-record", groundedness=5.0),
    ]
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    rendered = _render(
        run_log=run_log,
        calibration=calib,
        examples=examples,
        coverage_md="# coverage\n",
    )

    # Locate Section 6 in the rendered output.
    section_6_marker = "## 6."
    assert section_6_marker in rendered
    section_6_start = rendered.index(section_6_marker)
    section_6 = rendered[section_6_start:]

    # Worst paragraph appears verbatim.
    assert paragraph in section_6

    # At least one [N] marker is rendered as a claim-evidence pair.
    import re

    assert re.search(r"\[\d+\]", section_6) is not None


# ---------------------------------------------------------------------------
# run_log.split guard (CR-03): REPORT.md narrative is holdout-only.
# ---------------------------------------------------------------------------


def test_render_rejects_non_holdout_split_with_refresh_command() -> None:
    # COVERAGE.md commits the headline number to the holdout slice. A
    # `make eval-fixtures` run with no --split flag writes split="all",
    # and without this guard the renderer would silently print the
    # all-set mean under "holdout slice" language. The guard must fire
    # for every non-holdout value and embed the refresh command so the
    # operator knows how to fix it.
    rows = [_row("a", groundedness=3.0), _row("b", groundedness=4.0)]
    examples = [_ex("a"), _ex("b")]
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    for bad_split in ("all", "train"):
        payload = _synthetic_run_log_payload(rows)
        payload["split"] = bad_split
        run_log = RunLog.model_validate(payload)
        with pytest.raises(ValueError, match="holdout") as exc_info:
            _render(
                run_log=run_log,
                calibration=calib,
                examples=examples,
                coverage_md="# coverage\n",
            )
        assert _REFRESH_COMMAND_LITERAL in str(exc_info.value)


def test_run_log_schema_rejects_unknown_split_value() -> None:
    # Pydantic's Literal["all","train","holdout"] catches typos at
    # schema-validation time rather than letting them flow into _render.
    # This converts the WR-02-style "--split holdou" typo into an
    # immediate, named failure.
    from pydantic import ValidationError

    rows = [_row("a", groundedness=3.0)]
    payload = _synthetic_run_log_payload(rows)
    payload["split"] = "holdou"
    with pytest.raises(ValidationError):
        RunLog.model_validate(payload)


# ---------------------------------------------------------------------------
# _fmt_kappa / _fmt_pct (D-10)
# ---------------------------------------------------------------------------


def test_fmt_kappa_null_is_single_class() -> None:
    assert _fmt_kappa(None) == "n/a (single-class)"
    assert _fmt_kappa(0.176) == "0.176"
    assert _fmt_kappa(0.0) == "0.000"


def test_fmt_pct_null_is_na() -> None:
    assert _fmt_pct(None) == "n/a"
    assert _fmt_pct(0.5) == "50.0%"
    assert _fmt_pct(0.167) == "16.7%"


# ---------------------------------------------------------------------------
# _compute_axis_means (D-08)
# ---------------------------------------------------------------------------


def test_compute_axis_means_returns_axes_in_order() -> None:
    rows = [
        _row("a", groundedness=4.0),
        _row("b", groundedness=2.0),
    ]
    means = _compute_axis_means(rows)
    # Order matches AXES from evals.agreement.
    assert list(means.keys()) == list(AXES)
    # The two synthetic rows both have non-groundedness axes pinned to 3.0,
    # and groundedness 4.0 + 2.0 -> mean 3.0.
    assert means["groundedness"] == pytest.approx(3.0)
    assert means["icp_relevance"] == pytest.approx(3.0)


def test_compute_axis_means_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _compute_axis_means([])


# ---------------------------------------------------------------------------
# _pair_claims_to_evidence
# ---------------------------------------------------------------------------


def test_pair_claims_to_evidence_returns_indices_and_summaries() -> None:
    example = _ex(
        "x",
        paragraph="Acme launched payroll [1]. Acme grew [2]. No cite here.",
        justifications=[
            {"index": 1, "summary": "Acme expands into payroll.", "url": "https://example.test/p"},
            {"index": 2, "summary": "Acme headcount +20%.", "url": "https://example.test/h"},
        ],
    )
    pairs = _pair_claims_to_evidence(example)
    # Three sentences: two with markers, one without.
    assert len(pairs) == 3
    assert pairs[0]["indices"] == "[1]"
    assert "Acme expands into payroll." in pairs[0]["evidence_summary"]
    assert pairs[0]["evidence_url"] == "https://example.test/p"
    assert pairs[1]["indices"] == "[2]"
    # The uncited sentence renders the (no citations) sentinel.
    assert pairs[2]["indices"] == "(no citations)"


def test_pair_claims_to_evidence_record_level_fallback_when_no_markers() -> None:
    # The writer's older paragraph shape (and most rows in the committed
    # labeled.jsonl) carries citations on the record via `cited_indices`
    # rather than inline `[N]` markers. The renderer must surface those
    # citations per justification row instead of emitting "(no citations)"
    # for every claim and silently contradicting the surrounding narrative.
    example = LabeledExample(
        id="rec-no-markers",
        domain="rec-no-markers.com",
        contact_role="VP CX",
        paragraph="Acme launched payroll. Acme grew headcount.",
        citation_urls=["https://example.test/p", "https://example.test/h"],
        justifications=[
            {"index": 1, "summary": "Acme expands into payroll.", "url": "https://example.test/p"},
            {"index": 2, "summary": "Acme headcount +20%.", "url": "https://example.test/h"},
        ],
        cited_indices=[1, 2],
        split="holdout",
        coverage_cells=["rich-enrichment"],
        expected_groundedness=4.0,
        expected_relevance=3.0,
        expected_personalization=3.0,
        expected_specificity=3.0,
        expected_recency=3.0,
        expected_eval_failed=False,
    )
    pairs = _pair_claims_to_evidence(example)
    # One row per cited_index, in the record's declared order.
    assert len(pairs) == 2
    assert pairs[0]["indices"] == "[1]"
    assert pairs[0]["claim"] == "(paragraph-level cite)"
    assert pairs[0]["evidence_summary"] == "Acme expands into payroll."
    assert pairs[0]["evidence_url"] == "https://example.test/p"
    assert pairs[1]["indices"] == "[2]"
    assert pairs[1]["evidence_summary"] == "Acme headcount +20%."
    # And critically: zero "(no citations)" rows for a record that actually
    # carries citations on the record.
    assert all(p["indices"] != "(no citations)" for p in pairs)


def test_pair_claims_to_evidence_empty_paragraph_returns_empty() -> None:
    # Sentinel records (e.g. the empty-enrichment row in labeled.jsonl)
    # carry an empty paragraph; the table must collapse to zero rows so the
    # template renders no body, not a misleading "(no citations)" line.
    example = _ex("empty", paragraph="")
    assert _pair_claims_to_evidence(example) == []


def test_pair_claims_to_evidence_does_not_split_at_abbreviations() -> None:
    # WR-03 regression: the naive `(?<=[.!?])\s+` splitter would treat the
    # period in "N.A." (or "Inc.", "U.S.", "etc.") as a sentence boundary
    # and fragment one claim into two table rows. The rejoin guard in
    # `_split_sentences` must keep these abbreviations attached to their
    # surrounding sentence so the marker placement and the evidence pairing
    # both stay aligned with the writer's intent.
    paragraph = (
        "Acme Bank, N.A. launched a new product [1]."
        " Acme Inc. grew headcount by 20% [2]."
        " The U.S. expansion went live [1]."
    )
    example = _ex(
        "abbrev",
        paragraph=paragraph,
        justifications=[
            {"index": 1, "summary": "Acme product launch.", "url": "https://example.test/p"},
            {"index": 2, "summary": "Acme headcount growth.", "url": "https://example.test/h"},
        ],
    )
    pairs = _pair_claims_to_evidence(example)
    # Three real sentences, NOT five (which is what the naive splitter would
    # produce by breaking at "N.A. ", "Inc. ", "U.S. ").
    assert len(pairs) == 3
    assert pairs[0]["indices"] == "[1]"
    assert "N.A." in pairs[0]["claim"]
    assert pairs[1]["indices"] == "[2]"
    assert "Inc." in pairs[1]["claim"]
    assert pairs[2]["indices"] == "[1]"
    assert "U.S." in pairs[2]["claim"]


# ---------------------------------------------------------------------------
# Calibration ingest (W-04)
# ---------------------------------------------------------------------------


def test_calibration_three_sub_tables_render() -> None:
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    rows = [
        _row("a", groundedness=3.0),
        _row("b", groundedness=4.0),
    ]
    examples = [_ex("a"), _ex("b")]
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    rendered = _render(
        run_log=run_log,
        calibration=calib,
        examples=examples,
        coverage_md="# coverage\n",
    )

    # All three sub-tables must appear as identifiable sub-headings in Section 5.
    assert "Inter-judge" in rendered or "inter_judge" in rendered.lower()
    assert "DeepSeek vs human" in rendered or "deepseek_vs_human" in rendered.lower()
    assert "NVIDIA vs human" in rendered or "nvidia_vs_human" in rendered.lower()


def test_calibration_null_kappa_renders_single_class_marker() -> None:
    payload = _synthetic_calibration_payload()
    null_block = _calibration_block(None)
    payload["inter_judge"] = null_block
    calib = Calibration.model_validate(payload)
    rows = [
        _row("a", groundedness=3.0),
        _row("b", groundedness=4.0),
    ]
    examples = [_ex("a"), _ex("b")]
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    rendered = _render(
        run_log=run_log,
        calibration=calib,
        examples=examples,
        coverage_md="# coverage\n",
    )

    assert "n/a (single-class)" in rendered


# ---------------------------------------------------------------------------
# Freshness precheck (D-06)
# ---------------------------------------------------------------------------


_REFRESH_COMMAND_LITERAL = "uv run python -m evals.run_eval --split holdout --emit-log"


def test_freshness_precheck_missing_run_log_names_refresh_command(tmp_path: Path) -> None:
    labeled = tmp_path / "labeled.jsonl"
    labeled.write_text('{"id":"x"}\n', encoding="utf-8")
    run_log = tmp_path / "run-log.json"  # does NOT exist
    with pytest.raises(FileNotFoundError) as exc_info:
        _check_freshness(run_log_path=run_log, labeled_path=labeled)
    assert _REFRESH_COMMAND_LITERAL in str(exc_info.value)


def test_freshness_precheck_stale_run_log_names_refresh_command(tmp_path: Path) -> None:
    import os
    import time

    labeled = tmp_path / "labeled.jsonl"
    run_log = tmp_path / "run-log.json"
    # Create run-log first, then labeled (so labeled has the newer mtime).
    run_log.write_text("{}\n", encoding="utf-8")
    time.sleep(0.01)
    labeled.write_text('{"id":"x"}\n', encoding="utf-8")
    # Make sure run_log mtime is strictly older.
    old = time.time() - 60
    os.utime(run_log, (old, old))

    with pytest.raises(RuntimeError) as exc_info:
        _check_freshness(run_log_path=run_log, labeled_path=labeled)
    assert _REFRESH_COMMAND_LITERAL in str(exc_info.value)


def test_freshness_precheck_fresh_run_log_passes(tmp_path: Path) -> None:
    import os
    import time

    labeled = tmp_path / "labeled.jsonl"
    run_log = tmp_path / "run-log.json"
    labeled.write_text('{"id":"x"}\n', encoding="utf-8")
    run_log.write_text("{}\n", encoding="utf-8")
    # Force labeled strictly older than run_log via backdating; future-dating
    # run_log with `time.time() + N` is rejected or clamped by NFS, sandboxed
    # CI runners, and some FAT-family filesystems. Backdating is universally
    # supported and the relative ordering is the only thing the precheck
    # reads.
    older = time.time() - 120
    os.utime(labeled, (older, older))

    # Must not raise.
    _check_freshness(run_log_path=run_log, labeled_path=labeled)


# ---------------------------------------------------------------------------
# Byte-stability (D-05)
# ---------------------------------------------------------------------------


def test_report_render_is_byte_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Construct a complete fixture set under tmp_path. Patch the module-level
    # path constants so main() reads our fixtures, writes REPORT.md to tmp_path,
    # then re-render and assert byte equality.
    import evals.report as mod

    labeled_path = tmp_path / "labeled.jsonl"
    run_log_path = tmp_path / "run-log.json"
    calibration_path = tmp_path / "calibration.json"
    coverage_path = tmp_path / "COVERAGE.md"
    report_path = tmp_path / "REPORT.md"

    # Two records: one labeled.jsonl line per record so load_labeled() works
    # with the patched path.
    ex_a = {
        "id": "a-rec",
        "domain": "a.com",
        "contact_role": "VP CX",
        "paragraph": "A claims [1].",
        "citation_urls": ["https://example.test/a"],
        "justifications": [{"index": 1, "summary": "Evidence a.", "url": "https://example.test/a"}],
        "cited_indices": [1],
        "split": "holdout",
        "coverage_cells": ["rich-enrichment"],
        "expected": {
            "groundedness": 4.0,
            "icp_relevance": 3.0,
            "personalization": 3.0,
            "specificity": 3.0,
            "recency": 3.0,
            "eval_failed": False,
        },
    }
    ex_b = {
        "id": "b-rec",
        "domain": "b.com",
        "contact_role": "VP CX",
        "paragraph": "B claims [1].",
        "citation_urls": ["https://example.test/b"],
        "justifications": [{"index": 1, "summary": "Evidence b.", "url": "https://example.test/b"}],
        "cited_indices": [1],
        "split": "holdout",
        "coverage_cells": ["rich-enrichment"],
        "expected": {
            "groundedness": 5.0,
            "icp_relevance": 3.0,
            "personalization": 3.0,
            "specificity": 3.0,
            "recency": 3.0,
            "eval_failed": False,
        },
    }
    labeled_path.write_text(json.dumps(ex_a) + "\n" + json.dumps(ex_b) + "\n", encoding="utf-8")

    rows = [
        _row("a-rec", groundedness=2.0, expected_groundedness=4.0),
        _row("b-rec", groundedness=5.0, expected_groundedness=5.0),
    ]
    run_log_path.write_text(
        json.dumps(_synthetic_run_log_payload(rows), indent=2) + "\n",
        encoding="utf-8",
    )
    calibration_path.write_text(
        json.dumps(_synthetic_calibration_payload(), indent=2) + "\n",
        encoding="utf-8",
    )
    coverage_path.write_text("# Coverage\nA stable coverage body.\n", encoding="utf-8")

    monkeypatch.setattr(mod, "LABELED_PATH", labeled_path)
    monkeypatch.setattr(mod, "RUN_LOG_PATH", run_log_path)
    monkeypatch.setattr(mod, "CALIBRATION_JSON_PATH", calibration_path)
    monkeypatch.setattr(mod, "COVERAGE_MD_PATH", coverage_path)
    monkeypatch.setattr(mod, "REPORT_PATH", report_path)

    rc1 = mod.main()
    assert rc1 == 0
    first = report_path.read_bytes()

    rc2 = mod.main()
    assert rc2 == 0
    second = report_path.read_bytes()

    assert first == second, "renderer output drifted across two identical-input runs"


# ---------------------------------------------------------------------------
# Section 5 framing note (W-01 / D-09)
# ---------------------------------------------------------------------------


def test_section_5_contains_framing_note() -> None:
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    rows = [
        _row("a", groundedness=3.0),
        _row("b", groundedness=4.0),
    ]
    examples = [_ex("a"), _ex("b")]
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    rendered = _render(
        run_log=run_log,
        calibration=calib,
        examples=examples,
        coverage_md="# coverage\n",
    )

    assert "one signal, not a verdict" in rendered


# ---------------------------------------------------------------------------
# Six numbered H2 sections (D-03)
# ---------------------------------------------------------------------------


def test_six_h2_sections_render_in_order() -> None:
    calib = Calibration.model_validate(_synthetic_calibration_payload())
    rows = [
        _row("a", groundedness=3.0),
        _row("b", groundedness=4.0),
    ]
    examples = [_ex("a"), _ex("b")]
    run_log = RunLog.model_validate(_synthetic_run_log_payload(rows))

    rendered = _render(
        run_log=run_log,
        calibration=calib,
        examples=examples,
        coverage_md="# coverage\n",
    )

    # All six numbered H2 headings appear, in numeric order.
    positions = []
    for n in range(1, 7):
        marker = f"## {n}."
        assert marker in rendered, f"missing section heading {marker}"
        positions.append(rendered.index(marker))
    assert positions == sorted(positions), "section headings appear out of order"
