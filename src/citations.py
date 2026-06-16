from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .models import Justification

log = logging.getLogger(__name__)

# [1], [2,3], [1, 4] — tolerate optional whitespace and comma-separated lists.
INDEX_MARKER_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class ClaimResult:
    claim: str
    cited_indices: tuple[int, ...]
    passed: bool


def parse_indices(raw: object, valid: set[int]) -> tuple[int, ...]:
    """Extract valid integer indices from an arbitrary LLM-emitted value.

    Accepts a list; silently skips non-integer and out-of-range entries so a
    malformed writer response degrades gracefully instead of crashing.
    """
    if not isinstance(raw, list):
        return ()
    out: list[int] = []
    for v in raw:
        # bool is an int subclass: int(True) == 1. A JSON true/false is never a
        # citation index, so reject booleans before coercing.
        if isinstance(v, bool):
            continue
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if i in valid and i not in out:
            out.append(i)
    return tuple(out)


def _with_markers(claim_text: str, cited: tuple[int, ...]) -> str:
    """Append the validated citation markers to a claim, e.g. 'Claim. [3] [5]'.

    Strips any [N] markers the writer typed inline first, so the markers shown
    are exactly the indices that passed validation, never the writer's raw text,
    and never doubled.
    """
    stripped = INDEX_MARKER_RE.sub("", claim_text).strip()
    if not cited:
        return stripped
    markers = " ".join(f"[{i}]" for i in cited)
    return f"{stripped} {markers}"


def markers_in_paragraph(paragraph: str, valid: set[int]) -> set[int]:
    """Return the set of valid indices that appear as [N] markers in paragraph.

    Scanning the paragraph text guards against a writer that lists indices in
    cited_justifications but forgets to include the marker inline.
    """
    found: set[int] = set()
    for match in INDEX_MARKER_RE.finditer(paragraph):
        for piece in match.group(1).split(","):
            try:
                n = int(piece.strip())
            except ValueError:
                continue
            if n in valid:
                found.add(n)
    return found


def check_claim_coverage(
    claim: str,
    cited_indices: tuple[int, ...],
    justifications: tuple[Justification, ...],
    threshold_01: float,
) -> bool:
    """Return True if claim text overlaps sufficiently with any cited evidence.

    Uses rapidfuzz token_set_ratio, which handles token-order differences and
    substring relationships well (a short claim vs a longer evidence summary).
    The threshold lives in configs/icp.yaml as [0, 1]; rapidfuzz returns [0, 100],
    so we multiply before comparing to keep the YAML scale human-readable.
    """
    if not cited_indices:
        return False
    by_index = {j.index: j for j in justifications}
    cutoff = threshold_01 * 100
    for idx in cited_indices:
        if idx not in by_index:
            continue
        score: float = fuzz.token_set_ratio(claim, by_index[idx].summary)
        if score >= cutoff:
            return True
    return False


def assemble_paragraph(
    raw_claims: list[dict[str, object]],
    connective_text: str,
    justifications: tuple[Justification, ...],
    threshold_01: float,
) -> tuple[str, tuple[int, ...]]:
    """Drop failing claims; assemble surviving claims + connective text.

    Each entry in raw_claims must have "claim" (str) and "cited_indices" (list
    of ints) keys matching the D-01 writer output shape. Claims whose cited
    evidence scores below the rapidfuzz threshold are suppressed entirely.

    Returns ("", ()) when zero claims survive — the caller treats this as an
    empty hook, consistent with the existing OutreachHook(paragraph="") shape.
    Connective text is appended after surviving claims so the hook reads as
    evidence-first, call-to-action last.
    """
    valid_indices = {j.index for j in justifications}
    surviving_texts: list[str] = []
    surviving_indices: list[int] = []

    for raw in raw_claims:
        claim_text = str(raw.get("claim") or "").strip()
        if not claim_text:
            continue
        cited = parse_indices(raw.get("cited_indices"), valid_indices)
        if check_claim_coverage(claim_text, cited, justifications, threshold_01):
            surviving_texts.append(_with_markers(claim_text, cited))
            surviving_indices.extend(cited)

    if not surviving_texts:
        return ("", ())

    paragraph = " ".join(surviving_texts)
    tail = connective_text.strip()
    # Guard: drop connective_text that embeds [N] markers — the writer has
    # placed a citable factual claim here instead of in the claims array,
    # attempting to bypass the per-claim rapidfuzz gate.  Every cited
    # assertion must live in claims so the coverage check applies to it.
    if tail and INDEX_MARKER_RE.search(tail):
        log.warning("outreach: connective_text contains index markers; dropping to prevent bypass")
        tail = ""
    if tail:
        paragraph = paragraph + " " + tail

    # Deduplicate indices while preserving encounter order.
    seen: set[int] = set()
    deduped: list[int] = []
    for idx in surviving_indices:
        if idx not in seen:
            seen.add(idx)
            deduped.append(idx)

    # Invariant: every index we report as cited must actually appear as a marker
    # in the shipped paragraph, so the sheet's per-claim citations are real.
    present = markers_in_paragraph(paragraph, valid_indices)
    missing = set(deduped) - present
    if missing:
        log.warning("outreach: cited indices %s absent from assembled paragraph", sorted(missing))

    return (paragraph, tuple(deduped))
