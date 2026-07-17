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
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWLIST_FILES = ["Dockerfile", "pyproject.toml", "uv.lock", ".dockerignore"]
ALLOWLIST_DIRS = ["src", "evals", "configs"]
SPACE_README = ROOT / "deploy" / "hf-space" / "README.md"

# Copying a whole tree is only an allowlist at the top level; a secret nested
# inside src/, evals/, or configs/ (or a symlink pointing at one) would still
# be uploaded to the public Space. Reject these filenames at EVERY depth, and
# never follow a symlink into the upload.
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.env",
    "credentials*.json",
    "service-account*.json",
    ".secrets-denylist",
    "*.log",
)


def _reject_secrets_and_symlinks(dir_path: str, names: list[str]) -> set[str]:
    base = Path(dir_path)
    skip: set[str] = {"__pycache__"}
    for name in names:
        # casefold both sides: the deploy host is Linux, where fnmatch is
        # case-sensitive, so a CREDENTIALS.JSON or .ENV would otherwise slip
        # past lower-case patterns onto the public Space.
        folded = name.casefold()
        if (
            folded.endswith(".pyc")
            or (base / name).is_symlink()
            or any(fnmatchcase(folded, pattern) for pattern in SECRET_PATTERNS)
        ):
            skip.add(name)
    return skip


def _refuse_symlink(path: Path) -> None:
    # Fail closed on a symlinked upload input: copytree/copy2 dereference the
    # link, so a symlinked src/evals/configs root or Space README could publish
    # content from outside the tree. _reject_secrets_and_symlinks only guards
    # links found INSIDE a copied tree, not the tree root itself.
    if path.is_symlink():
        raise RuntimeError(f"refusing to publish symlinked upload input: {path}")


def assemble(workdir: Path) -> None:
    for name in ALLOWLIST_FILES:
        src = ROOT / name
        _refuse_symlink(src)
        if src.is_file():
            shutil.copy2(src, workdir / name)
    for name in ALLOWLIST_DIRS:
        src_dir = ROOT / name
        _refuse_symlink(src_dir)
        shutil.copytree(
            src_dir,
            workdir / name,
            ignore=_reject_secrets_and_symlinks,
        )
    _refuse_symlink(SPACE_README)
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
