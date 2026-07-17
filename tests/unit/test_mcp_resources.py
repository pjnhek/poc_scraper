"""Unit tests for the icp://rubric and icp://eval-report resource functions.

Calls read_icp_rubric()/read_eval_report() directly (not over the MCP wire)
so D-08 sanitization is asserted in isolation from SDK error-wrapping (see
tests/functional/test_mcp_server.py for the round-trip tests).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from evals.report import REPORT_PATH
from src.icp_config import DEFAULT_CONFIG_PATH
from src.mcp_server.server import read_eval_report, read_icp_rubric


def test_read_icp_rubric_returns_verbatim_file_content() -> None:
    assert read_icp_rubric() == DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")


def test_read_eval_report_returns_verbatim_file_content() -> None:
    assert read_eval_report() == REPORT_PATH.read_text(encoding="utf-8")


def _raise_leaky_oserror(self: Path, *args: object, **kwargs: object) -> str:
    raise OSError("/leaky/absolute/path")


def test_read_icp_rubric_sanitizes_read_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(Path, "read_text", _raise_leaky_oserror)

    with caplog.at_level(logging.WARNING):
        result = read_icp_rubric()

    assert result != ""
    assert "resource unavailable" in result
    assert "/leaky/absolute/path" not in result
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_read_eval_report_sanitizes_read_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(Path, "read_text", _raise_leaky_oserror)

    with caplog.at_level(logging.WARNING):
        result = read_eval_report()

    assert result != ""
    assert "resource unavailable" in result
    assert "/leaky/absolute/path" not in result
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_rubric_and_eval_report_sanitized_messages_are_distinguishable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "read_text", _raise_leaky_oserror)

    rubric_message = read_icp_rubric()
    report_message = read_eval_report()

    assert rubric_message != report_message
