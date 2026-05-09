from __future__ import annotations

from pathlib import Path

import pytest

from src.csv_io import CSVFormatError, read_accounts


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "accounts.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_reads_simple_csv(tmp_path: Path) -> None:
    p = _write(tmp_path, "domain\nnotion.so\nlinear.app\n")
    accs = read_accounts(p)
    assert [a.domain for a in accs] == ["notion.so", "linear.app"]


def test_normalizes_and_dedupes(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "domain\nhttps://www.Notion.so/\nNOTION.SO\nlinear.app\n",
    )
    accs = read_accounts(p)
    assert [a.domain for a in accs] == ["notion.so", "linear.app"]


def test_skips_blank_rows(tmp_path: Path) -> None:
    p = _write(tmp_path, "domain\nnotion.so\n\n   \nlinear.app\n")
    accs = read_accounts(p)
    assert [a.domain for a in accs] == ["notion.so", "linear.app"]


def test_missing_header_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "url\nnotion.so\n")
    with pytest.raises(CSVFormatError):
        read_accounts(p)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_accounts(tmp_path / "nope.csv")


def test_invalid_domain_in_row_raises(tmp_path: Path) -> None:
    from pydantic import ValidationError

    p = _write(tmp_path, "domain\nnotion.so\nnot a domain\n")
    with pytest.raises(ValidationError):
        read_accounts(p)


def test_seed_csv_loads(tmp_path: Path) -> None:
    seed = Path(__file__).parents[2] / "inputs" / "accounts.csv"
    accs = read_accounts(seed)
    assert len(accs) == 20
    assert all("." in a.domain for a in accs)
