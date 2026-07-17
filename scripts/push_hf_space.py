"""Push the demo Docker build context to a Hugging Face Space.

Assembles an explicit file allowlist, the same discipline `.dockerignore`
already applies to the local Docker build: only what the Dockerfile's COPY
instructions need, plus the Space card at `deploy/hf-space/README.md`. The
allowlist is copied into a scratch directory and uploaded with `hf upload`
(the officially recommended single-commit path), so nothing outside it, no
`.env`, `credentials.json`, `.planning/`, `tests/`, or the project's own
`README.md`, ever leaves the working tree.

Requires `hf auth login` to already be configured in this shell (see
`docs/DEPLOY.md`). Never reads or embeds a token.

Usage:
    uv run python -m scripts.push_hf_space <owner>/<space-name>
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWLIST_FILES = ["Dockerfile", "pyproject.toml", "uv.lock", ".dockerignore"]
ALLOWLIST_DIRS = ["src", "evals", "configs"]
SPACE_README = ROOT / "deploy" / "hf-space" / "README.md"


def assemble(workdir: Path) -> None:
    for name in ALLOWLIST_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, workdir / name)
    for name in ALLOWLIST_DIRS:
        shutil.copytree(
            ROOT / name,
            workdir / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copy2(SPACE_README, workdir / "README.md")


def push(space: str) -> None:
    with tempfile.TemporaryDirectory(prefix="hf-space-") as tmp:
        workdir = Path(tmp)
        assemble(workdir)
        subprocess.run(
            [
                "hf",
                "upload",
                space,
                str(workdir),
                ".",
                "--repo-type",
                "space",
                "--commit-message",
                "deploy: sync poc-scraper-mcp demo container",
            ],
            check=True,
        )
    print(f"Pushed. Space: https://huggingface.co/spaces/{space}")


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: push_hf_space.py <owner>/<space-name>", file=sys.stderr)
        sys.exit(1)
    push(sys.argv[1])


if __name__ == "__main__":
    main()
