from __future__ import annotations

from datetime import UTC, datetime

from src.models import Account
from src.sheets import build_inputs_rows


def test_inputs_rows_list_each_domain() -> None:
    accounts = [Account(domain="a.com"), Account(domain="b.com"), Account(domain="c.io")]
    rows = build_inputs_rows(accounts)
    flat = [cell for row in rows for cell in row]
    assert "a.com" in flat
    assert "b.com" in flat
    assert "c.io" in flat


def test_inputs_rows_include_count_and_loaded_at() -> None:
    accounts = [Account(domain="a.com"), Account(domain="b.com")]
    when = datetime(2026, 5, 9, 14, 30, 0, tzinfo=UTC)
    rows = build_inputs_rows(accounts, loaded_at=when)
    flat = [cell for row in rows for cell in row]
    assert "count" in flat
    assert "2" in flat
    assert "2026-05-09 14:30:00 UTC" in flat


def test_inputs_rows_include_source_when_given() -> None:
    rows = build_inputs_rows(
        [Account(domain="a.com")],
        loaded_at=datetime(2026, 5, 9, 14, 30, 0, tzinfo=UTC),
        source_path="inputs/accounts.csv",
    )
    flat = [cell for row in rows for cell in row]
    assert "source" in flat
    assert "inputs/accounts.csv" in flat


def test_inputs_rows_handle_empty_list() -> None:
    rows = build_inputs_rows([], loaded_at=datetime(2026, 5, 9, 0, 0, 0, tzinfo=UTC))
    flat = [cell for row in rows for cell in row]
    assert "0" in flat
    assert "domain" in flat
