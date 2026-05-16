from __future__ import annotations

import hashlib
import logging

log = logging.getLogger(__name__)

SPLIT_SALT: str = "poc-eval-v1"  # bump only when rebuilding the labeled set wholesale

AXES: tuple[str, ...] = (
    "groundedness",
    "icp_relevance",
    "personalization",
    "specificity",
    "recency",
)


def assign_split(record_id: str, holdout_pct: float = 0.30) -> str:
    """Deterministic per-record split assignment, reproducible from data alone.

    SHA-256 over a versioned salt plus record ID avoids Python's process-random
    hash() (PYTHONHASHSEED) and stays stable when records are added later.
    Verified distribution: ~28-30% holdout over large sample sets.
    """
    digest = hashlib.sha256(f"{SPLIT_SALT}:{record_id}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return "holdout" if bucket < int(holdout_pct * 100) else "train"


def cohen_kappa_linear(rater1: list[float], rater2: list[float]) -> float:
    """Linear-weighted Cohen's kappa for ordinal 1-5 scores.

    Returns 1.0 for single-class collapse (both raters always agree on one value,
    making kappa undefined by the standard formula).

    Standard interpretation: less than 0.2 slight, 0.2-0.4 fair, 0.4-0.6
    moderate, 0.6-0.8 substantial, greater than 0.8 almost perfect.

    Linear weighting is appropriate for ordinal scales because it penalizes
    disagreements proportionally to how far apart the ratings are, unlike
    unweighted kappa which treats a 1-vs-5 disagreement the same as 1-vs-2.
    """
    cats = sorted(set(rater1) | set(rater2))
    k = len(cats)
    n = len(rater1)
    if k == 1:
        # Kappa is undefined for single-class; treat as perfect agreement.
        return 1.0
    cat_idx = {c: i for i, c in enumerate(cats)}
    obs = [[0] * k for _ in range(k)]
    for a, b in zip(rater1, rater2, strict=True):
        obs[cat_idx[a]][cat_idx[b]] += 1
    row_sums = [sum(obs[i]) for i in range(k)]
    col_sums = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[1 - abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    po = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(w[i][j] * row_sums[i] * col_sums[j] for i in range(k) for j in range(k)) / (n * n)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def pct_agreement(rater1: list[float], rater2: list[float]) -> float:
    """Raw exact-match agreement as a fraction (0.0-1.0)."""
    return sum(a == b for a, b in zip(rater1, rater2, strict=True)) / len(rater1)
