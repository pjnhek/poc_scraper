from __future__ import annotations

import sys
from pathlib import Path

from evals.run_eval import LABELED_PATH, load_labeled

REQUIRED_CELLS: frozenset[str] = frozenset(
    {
        # Pitfall-4 enrichment-quality axis
        "thin-enrichment",
        "moderate-enrichment",
        "rich-enrichment",
        # Pitfall-4 news-recency axis
        "stale-news",
        "fresh-news",
        "mixed-news",
        # Pitfall-4 ICP-fit axis
        "icp-clear-yes",
        "icp-clear-no",
        "icp-borderline",
        # Pitfall-4 public-profile axis
        "well-known",
        "mid-tier",
        "obscure",
        # Failure-mode cells (Pitfall 2, 4, 8)
        "empty-enrichment",
        "blocked-scrape",
        "no-recent-news",
        "partial-citation-laundering",
        "generic-but-grounded",
        "judge-failed",
    }
)


def check_coverage(path: Path = LABELED_PATH) -> int:
    """Return exit code 0 if all cells covered, 1 if gaps found."""
    examples = load_labeled(path)
    covered: set[str] = set()
    for ex in examples:
        covered.update(ex.coverage_cells)
    gaps = REQUIRED_CELLS - covered
    if gaps:
        print(f"COVERAGE GAP: {len(gaps)} cell(s) not covered: {sorted(gaps)}")
        return 1
    print(f"OK: all {len(REQUIRED_CELLS)} coverage cells satisfied by {len(examples)} records.")
    return 0


if __name__ == "__main__":
    sys.exit(check_coverage())
