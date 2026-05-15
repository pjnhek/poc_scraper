from __future__ import annotations

from src.citations import (
    INDEX_MARKER_RE,
    assemble_paragraph,
    check_claim_coverage,
    markers_in_paragraph,
    parse_indices,
)
from src.models import Citation, Justification


def _justification(index: int, summary: str) -> Justification:
    """Build a minimal Justification for test setup without repeating boilerplate."""
    return Justification(
        index=index,
        summary=summary,
        citation=Citation.make(
            url=f"https://example.com/{index}",
            source="exa",
        ),
    )


class TestIndexMarkerRE:
    def test_index_marker_re_variants(self) -> None:
        # All three common writer formats must be captured so none slip through unverified.
        assert INDEX_MARKER_RE.search("[1]") is not None
        assert INDEX_MARKER_RE.search("[1,2]") is not None
        assert INDEX_MARKER_RE.search("[1, 4]") is not None
        # Non-numeric content must not match.
        assert INDEX_MARKER_RE.search("[abc]") is None


class TestParseIndices:
    def test_parse_indices_filters_invalid(self) -> None:
        # Out-of-range and non-integer entries must be dropped; deduplication required.
        result = parse_indices([1, 99, "bad"], {1, 2, 3})
        assert result == (1,)

    def test_parse_indices_deduplicates(self) -> None:
        # Repeated valid indices must appear once, in encounter order.
        result = parse_indices([2, 1, 2], {1, 2, 3})
        assert result == (2, 1)

    def test_parse_indices_non_list_input(self) -> None:
        # A non-list (e.g. None, str) must return empty without raising.
        assert parse_indices(None, {1, 2}) == ()
        assert parse_indices("1", {1, 2}) == ()


class TestMarkersInParagraph:
    def test_markers_in_paragraph(self) -> None:
        # Only indices that appear in both the text and the valid set must be returned.
        result = markers_in_paragraph("hello [1] and [3]", {1, 2, 3})
        assert result == {1, 3}

    def test_markers_in_paragraph_excludes_out_of_valid(self) -> None:
        # [5] appears in the text but is not in valid; it must be excluded.
        result = markers_in_paragraph("claim [5]", {1, 2, 3})
        assert result == set()


class TestCheckClaimCoverage:
    def test_claim_passes_at_threshold(self) -> None:
        # token_set_ratio of identical strings is 100; any threshold in [0, 1] must pass.
        j = _justification(1, "Mercury expanded into payroll")
        passed = check_claim_coverage(
            claim="Mercury expanded into payroll",
            cited_indices=(1,),
            justifications=(j,),
            threshold_01=1.0,  # 100/100 — identical strings hit exactly 100
        )
        assert passed is True

    def test_claim_suppressed_below_threshold(self) -> None:
        # Completely unrelated claim must score well below a high threshold.
        j = _justification(1, "Mercury expanded into payroll")
        # rapidfuzz score for "completely unrelated fabrication xyz" vs evidence is ~34.
        passed = check_claim_coverage(
            claim="completely unrelated fabrication xyz",
            cited_indices=(1,),
            justifications=(j,),
            threshold_01=0.9,  # 90/100 — unrelated claim scores ~34, well below 90
        )
        assert passed is False

    def test_claim_passes_above_threshold(self) -> None:
        # High-overlap claim (score ~85) must pass a moderate threshold (40/100).
        j = _justification(7, "Mercury expanded into payroll")
        passed = check_claim_coverage(
            claim="Mercury payroll expansion",
            cited_indices=(7,),
            justifications=(j,),
            threshold_01=0.4,
        )
        assert passed is True

    def test_claim_with_no_cited_indices_fails(self) -> None:
        # No cited indices means no evidence to compare against; must return False.
        j = _justification(1, "Mercury expanded into payroll")
        passed = check_claim_coverage(
            claim="Mercury expanded into payroll",
            cited_indices=(),
            justifications=(j,),
            threshold_01=0.0,
        )
        assert passed is False


class TestAssembleParagraph:
    def test_multi_claim_partial_suppression(self) -> None:
        # One passing claim, one completely unrelated claim that will fail a strict threshold.
        justifications = (_justification(1, "Mercury expanded into payroll services last quarter"),)
        raw_claims: list[dict[str, object]] = [
            {"claim": "Mercury expanded into payroll", "cited_indices": [1]},
            {"claim": "zzz unrelated fabricated claim aaa", "cited_indices": [1]},
        ]
        paragraph, cited = assemble_paragraph(
            raw_claims=raw_claims,
            connective_text="Looking forward to connecting.",
            justifications=justifications,
            threshold_01=0.8,  # 80/100; passing claim scores ~87, failing ~14
        )
        assert "Mercury expanded into payroll" in paragraph
        assert "zzz unrelated fabricated claim aaa" not in paragraph
        assert "Looking forward to connecting." in paragraph
        assert cited != ()

    def test_all_claims_suppressed_empty_survivors(self) -> None:
        # All claims completely unrelated to evidence must yield ("", ()).
        justifications = (_justification(1, "Mercury expanded into payroll services"),)
        raw_claims: list[dict[str, object]] = [
            {"claim": "zzz completely fabricated claim aaa", "cited_indices": [1]},
            {"claim": "bbb another unrelated statement ccc", "cited_indices": [1]},
        ]
        paragraph, cited = assemble_paragraph(
            raw_claims=raw_claims,
            connective_text="Would love to chat.",
            justifications=justifications,
            threshold_01=0.95,
        )
        assert paragraph == ""
        assert cited == ()
