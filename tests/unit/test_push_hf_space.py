"""Unit tests for the HF Space push secret/symlink filter.

push_hf_space copies whole src/evals/configs trees to a PUBLIC Space, so the
copytree ignore callable is the only thing standing between a nested secret
(or a symlink pointing at one) and public exposure. Exercise it directly with
crafted directory contents.
"""

from __future__ import annotations

import os
from pathlib import Path

from scripts.push_hf_space import _reject_secrets_and_symlinks


def test_secret_named_files_are_skipped_at_any_depth(tmp_path: Path) -> None:
    for name in (
        ".env",
        ".env.local",
        "prod.env",
        "credentials.json",
        "service-account-abc.json",
        ".secrets-denylist",
        "run.log",
    ):
        (tmp_path / name).write_text("secret")

    skip = _reject_secrets_and_symlinks(str(tmp_path), os.listdir(tmp_path))

    assert skip >= {
        ".env",
        ".env.local",
        "prod.env",
        "credentials.json",
        "service-account-abc.json",
        ".secrets-denylist",
        "run.log",
    }


def test_symlinks_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "target.py").write_text("x = 1")
    (tmp_path / "link.py").symlink_to(tmp_path / "target.py")

    skip = _reject_secrets_and_symlinks(str(tmp_path), os.listdir(tmp_path))

    assert "link.py" in skip
    assert "target.py" not in skip


def test_bytecode_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "mod.pyc").write_text("compiled")

    skip = _reject_secrets_and_symlinks(str(tmp_path), ["mod.pyc", "__pycache__"])

    assert skip >= {"mod.pyc", "__pycache__"}


def test_regular_source_files_are_kept(tmp_path: Path) -> None:
    for name in ("enrich.py", "icp.yaml", "labeled.jsonl", "rubric.py"):
        (tmp_path / name).write_text("keep me")

    skip = _reject_secrets_and_symlinks(str(tmp_path), os.listdir(tmp_path))

    assert skip == {"__pycache__"}
