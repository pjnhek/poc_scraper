"""Integration coverage for the D-06 freshness precheck in evals/report.py.

These tests exercise `main()` end-to-end against `tmp_path` copies of the four
committed artifacts the renderer consumes (labeled.jsonl, run-log.json,
calibration.json, COVERAGE.md). The committed artifacts on disk are never
touched; `shutil.copy2` clones them into `tmp_path` and `os.utime` adjusts the
copies' mtimes to simulate fresh / stale / missing run-log scenarios.

Why integration, not unit: the unit tests in tests/unit/test_report_render.py
already cover `_check_freshness` in isolation with synthetic two-byte files.
This file wires the full `main()` path (freshness precheck -> load four real
artifacts -> render template -> write REPORT.md) against the actual committed
artifact contents, so a future drift in the freshness contract OR in the
artifact loading path is caught by the same gate the operator's `make
eval-report` invocation hits.

The literal refresh command `uv run python -m evals.run_eval --split holdout
--emit-log` is asserted in both error-path tests (stale and missing) so a
silent rename of the literal in `evals/report.py::REFRESH_COMMAND` trips this
gate alongside the unit-test mirror.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

import evals.report as report

_REFRESH_COMMAND_LITERAL = "uv run python -m evals.run_eval --split holdout --emit-log"

_REPO_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"


def _stage_artifacts(tmp_path: Path) -> dict[str, Path]:
    """Copy the four committed input artifacts into tmp_path via shutil.copy2.

    Returns the four staged paths plus an unwritten REPORT.md target. The
    REPORT.md output target lives under tmp_path so the committed
    evals/REPORT.md is never overwritten by these tests.
    """
    labeled = tmp_path / "labeled.jsonl"
    run_log = tmp_path / "run-log.json"
    calibration = tmp_path / "calibration.json"
    coverage = tmp_path / "COVERAGE.md"
    report_out = tmp_path / "REPORT.md"

    shutil.copy2(_REPO_EVALS_DIR / "labeled.jsonl", labeled)
    shutil.copy2(_REPO_EVALS_DIR / "run-log.json", run_log)
    shutil.copy2(_REPO_EVALS_DIR / "calibration.json", calibration)
    shutil.copy2(_REPO_EVALS_DIR / "COVERAGE.md", coverage)

    return {
        "labeled": labeled,
        "run_log": run_log,
        "calibration": calibration,
        "coverage": coverage,
        "report": report_out,
    }


def _repoint_report_module(monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
    monkeypatch.setattr(report, "LABELED_PATH", paths["labeled"])
    monkeypatch.setattr(report, "RUN_LOG_PATH", paths["run_log"])
    monkeypatch.setattr(report, "CALIBRATION_JSON_PATH", paths["calibration"])
    monkeypatch.setattr(report, "COVERAGE_MD_PATH", paths["coverage"])
    monkeypatch.setattr(report, "REPORT_PATH", paths["report"])


def test_main_succeeds_with_fresh_run_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh run-log (mtime strictly newer than labeled) -> main() returns 0.

    The freshness precheck must pass and main() must render a non-empty
    REPORT.md under tmp_path. The committed evals/REPORT.md is never touched.
    """
    paths = _stage_artifacts(tmp_path)
    # Force run_log mtime strictly newer than labeled mtime; copy2 preserves
    # source mtimes which on the committed artifacts are arbitrarily ordered.
    new = time.time() + 60
    os.utime(paths["run_log"], (new, new))
    older = time.time() - 60
    os.utime(paths["labeled"], (older, older))

    _repoint_report_module(monkeypatch, paths)

    rc = report.main()

    assert rc == 0
    assert paths["report"].exists(), "main() did not write REPORT.md"
    rendered = paths["report"].read_text(encoding="utf-8")
    # Sanity: the rendered output is the expected six-section document and
    # not an empty stub or an error message accidentally written to disk.
    assert "# Phase 4: Eval Narrative" in rendered
    assert "## 1." in rendered and "## 6." in rendered


def test_main_fails_when_run_log_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run-log mtime older than labeled.jsonl mtime -> RuntimeError with the literal refresh command.

    Simulates an operator who edited labeled.jsonl without re-running the
    judge. main() must refuse to render and name the exact command the
    operator should run to refresh the snapshot.
    """
    paths = _stage_artifacts(tmp_path)
    # Force run_log strictly older than labeled.
    older = time.time() - 120
    os.utime(paths["run_log"], (older, older))
    newer = time.time()
    os.utime(paths["labeled"], (newer, newer))

    _repoint_report_module(monkeypatch, paths)

    with pytest.raises(RuntimeError) as exc_info:
        report.main()
    assert _REFRESH_COMMAND_LITERAL in str(exc_info.value)
    # main() must NOT have written REPORT.md when the precheck fails.
    assert not paths["report"].exists()


def test_main_fails_when_run_log_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing run-log -> FileNotFoundError with the literal refresh command.

    Simulates a fresh clone or a clean checkout where the operator has not
    yet emitted the holdout snapshot. main() must refuse to render and name
    the exact command the operator should run to produce it.
    """
    paths = _stage_artifacts(tmp_path)
    # Remove the staged run-log to simulate the missing-artifact case. The
    # other three artifacts remain intact so the failure is provably the
    # freshness precheck, not an unrelated load error.
    paths["run_log"].unlink()
    assert not paths["run_log"].exists()

    _repoint_report_module(monkeypatch, paths)

    with pytest.raises(FileNotFoundError) as exc_info:
        report.main()
    assert _REFRESH_COMMAND_LITERAL in str(exc_info.value)
    assert not paths["report"].exists()
