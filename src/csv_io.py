from __future__ import annotations

import csv
from pathlib import Path

from .models import Account


class CSVFormatError(ValueError):
    pass


def read_accounts(path: str | Path) -> list[Account]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"accounts CSV not found: {p}")

    accounts: list[Account] = []
    seen: set[str] = set()
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "domain" not in reader.fieldnames:
            raise CSVFormatError(f"expected a 'domain' column in {p}, found: {reader.fieldnames}")
        for row in reader:
            raw = (row.get("domain") or "").strip()
            if not raw:
                continue
            account = Account(domain=raw)
            if account.domain in seen:
                continue
            seen.add(account.domain)
            accounts.append(account)
    return accounts
