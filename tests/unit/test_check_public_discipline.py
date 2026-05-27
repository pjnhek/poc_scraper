from __future__ import annotations

from pathlib import Path

import pytest

import scripts.check_public_discipline as mod

# Publishable placeholder per CONTEXT.md D-05 / THR-02. The real denylisted
# term lives only in the operator's local .secrets-denylist and MUST NOT appear
# in this test file under any circumstance.
FAKE_TERM = "fake-denylisted-term-for-test"


@pytest.mark.parametrize(
    "case_id, body, path_suffix, expected",
    [
        ("content-match", f"this file mentions {FAKE_TERM}\n", "ok.txt", 1),
        ("path-match", "harmless body\n", f"{FAKE_TERM}.txt", 1),
    ],
)
def test_main_flags_violations(
    case_id: str,
    body: str,
    path_suffix: str,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Covers both branches of `if pat.search(content) or pat.search(path)` at
    scripts/check_public_discipline.py:53 per CONTEXT.md D-06."""
    fake_denylist = tmp_path / ".secrets-denylist"
    fake_denylist.write_text(FAKE_TERM + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DENYLIST", fake_denylist)

    fixture = tmp_path / path_suffix
    fixture.write_text(body, encoding="utf-8")

    # main() calls _staged_content() which shells `git show :<path>`. The
    # fixture is not git-staged in a unit test, so the real call returns ""
    # and the content-match case would false-pass. Patch the seam directly.
    monkeypatch.setattr(
        mod,
        "_staged_content",
        lambda p: body if p == str(fixture) else "",
    )

    assert mod.main([str(fixture)]) == expected


def test_main_returns_zero_when_no_denylist_terms_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_denylist = tmp_path / ".secrets-denylist"
    fake_denylist.write_text(FAKE_TERM + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DENYLIST", fake_denylist)

    fixture = tmp_path / "clean.txt"
    body = "clean content\n"
    fixture.write_text(body, encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_staged_content",
        lambda p: body if p == str(fixture) else "",
    )

    assert mod.main([str(fixture)]) == 0
