"""Pre-commit guard: block staged content that violates public-repo discipline.

Patterns live in a local-only file (.secrets-denylist, gitignored) so the
sensitive terms themselves never enter the public repository. If that file is
absent (e.g. a fresh clone by another contributor) the check passes silently
rather than breaking unrelated commits.

Usage: invoked by pre-commit with the list of staged files as argv.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DENYLIST = Path(__file__).resolve().parent.parent / ".secrets-denylist"


def _load_patterns() -> list[re.Pattern[str]]:
    if not DENYLIST.exists():
        return []
    patterns: list[re.Pattern[str]] = []
    for raw in DENYLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line, re.IGNORECASE))
    return patterns


def _staged_content(path: str) -> str:
    # Read the staged blob, not the worktree file: only what is actually
    # about to be committed should gate the commit.
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def main(argv: list[str]) -> int:
    patterns = _load_patterns()
    if not patterns:
        return 0

    violations: list[str] = []
    for path in argv:
        content = _staged_content(path)
        for pat in patterns:
            if pat.search(content) or pat.search(path):
                violations.append(f"  {path}: matches /{pat.pattern}/i")

    if violations:
        sys.stderr.write(
            "public-repo-discipline check failed; staged changes contain "
            "denylisted terms:\n" + "\n".join(violations) + "\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
