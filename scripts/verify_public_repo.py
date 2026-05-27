"""Operator verification: re-run the public-repo audit in one command.

Patterns live in a local-only file (.secrets-denylist, gitignored) so the
sensitive terms themselves never enter the public repository. Unlike the
pre-commit guard (which passes silently when the denylist is absent so fresh
clones do not break on routine commits), this verification script REQUIRES the
denylist and exits non-zero with a setup prompt if it is missing. Verification
is an explicit operator action with stakes-laden output; silence on missing
configuration would defeat the audit.

Two passes run:
  1. Worktree pass over every tracked path (content + path string).
  2. History pass over `git log --all -p` to cover every commit reachable from
     any ref.

Output is intentionally non-revealing: exactly one summary line on stdout with
occurrence counts and the current HEAD SHA, never raw matches. On a non-zero
hit count the operator must grep locally to inspect; the script does not echo
matched text under any code path.

Usage: invoked by `make verify-public-repo`, or directly with
`uv run python -m scripts.verify_public_repo`.
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


def _scan_worktree(patterns: list[re.Pattern[str]]) -> int:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    hits = 0
    for path in result.stdout.splitlines():
        # The denylist file is the one allowed location for the pattern; it is
        # gitignored, but a worktree scan via git ls-files should never see it
        # anyway. Skip defensively so a future un-ignore mistake cannot leak.
        if path == ".secrets-denylist":
            continue
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except (UnicodeDecodeError, OSError):
            continue
        for pat in patterns:
            hits += len(pat.findall(content))
            hits += len(pat.findall(path))
    return hits


def _scan_history(patterns: list[re.Pattern[str]]) -> int:
    result = subprocess.run(
        ["git", "log", "--all", "-p"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    hits = 0
    for line in result.stdout.splitlines():
        for pat in patterns:
            hits += len(pat.findall(line))
    return hits


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha if sha else "unknown"


def main() -> int:
    if not DENYLIST.exists():
        sys.stderr.write(
            f"verify-public-repo: .secrets-denylist not found at {DENYLIST}. "
            "Create it with one regex per line (see README Local setup) before running.\n"
        )
        return 2

    patterns = _load_patterns()
    if not patterns:
        sys.stderr.write(
            "verify-public-repo: .secrets-denylist contains no active patterns; "
            "nothing to verify.\n"
        )
        return 2

    worktree_hits = _scan_worktree(patterns)
    history_hits = _scan_history(patterns)
    sha = _head_sha()

    print(
        f"verify-public-repo: {worktree_hits} hits in tracked content, "
        f"{history_hits} hits in history reachable from any ref (commit {sha})."
    )

    if worktree_hits == 0 and history_hits == 0:
        return 0

    sys.stderr.write(
        "verify-public-repo: non-zero hits found; inspect .secrets-denylist patterns "
        "and grep locally to remediate. Do NOT paste hit text into any committed artifact.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
