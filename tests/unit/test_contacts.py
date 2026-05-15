from __future__ import annotations

from src.contacts import _default_contacts, _to_contacts
from src.icp_config import ICPConfig


def _make_axis() -> dict[str, object]:
    return {
        "weight": 0.25,
        "description": "test axis",
        "anchors": {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"},
    }


def _make_config(personas: list[dict[str, str]]) -> ICPConfig:
    return ICPConfig.model_validate(
        {
            "buyer_description": "test buyer",
            "seller_description": "test seller",
            "axes": {
                "support_volume": _make_axis(),
                "ai_maturity": _make_axis(),
                "stage_fit": _make_axis(),
                "channel_breadth": _make_axis(),
            },
            "verdicts": {
                "strong": {"min_total": 4.0, "label": "strong", "description": "d"},
                "weak": {"min_total": 0.0, "label": "weak", "description": "d"},
            },
            "eval": {
                "groundedness_flag_threshold": 3.0,
                "groundedness_suppress_threshold": 0.4,
            },
            "default_personas": personas,
        }
    )


class TestDefaultContacts:
    def test_default_contacts_from_config(self) -> None:
        # _default_contacts must read persona titles from ICPConfig.default_personas
        # rather than returning the hardcoded CX-vertical strings (FIX-05).
        config = _make_config(
            [
                {"role_title": "Test Director A", "rationale": "rationale A"},
                {"role_title": "Test Director B", "rationale": "rationale B"},
                {"role_title": "Test Director C", "rationale": "rationale C"},
            ]
        )
        result = _default_contacts(config)

        assert len(result) == 3
        titles = [c.role_title for c in result]
        assert titles == ["Test Director A", "Test Director B", "Test Director C"]
        # Old hardcoded strings must not appear anywhere in the output.
        assert "VP Customer Experience" not in titles
        assert "Head of Support Operations" not in titles
        assert "Director of CX Automation" not in titles

    def test_default_contacts_uses_persona_rationale(self) -> None:
        # When a persona has a rationale, it propagates to the Contact.
        config = _make_config(
            [
                {"role_title": "Test Role X", "rationale": "custom reason"},
                {"role_title": "Test Role Y", "rationale": "(no rationale provided)"},
                {"role_title": "Test Role Z", "rationale": "another reason"},
            ]
        )
        result = _default_contacts(config)

        assert result[0].rationale == "custom reason"
        assert result[1].rationale == "(no rationale provided)"
        assert result[2].rationale == "another reason"

    def test_default_contacts_falls_back_for_empty_rationale(self) -> None:
        # When a persona has an empty rationale string, DEFAULT_RATIONALE is used.
        config = _make_config(
            [
                {"role_title": "Test Role P", "rationale": ""},
                {"role_title": "Test Role Q", "rationale": "explicit"},
                {"role_title": "Test Role R", "rationale": ""},
            ]
        )
        result = _default_contacts(config)

        assert result[0].rationale == "(no rationale provided)"
        assert result[1].rationale == "explicit"
        assert result[2].rationale == "(no rationale provided)"


class TestToContactsPartialFill:
    def test_partial_fill_uses_defaults_from_front(self) -> None:
        # When the LLM returns fewer than 3 contacts, padding must start from
        # defaults[0], not defaults[len(llm_contacts)].  The off-by-one bug
        # caused defaults[0] to be unreachable on any partial-fill scenario.
        config = _make_config(
            [
                {"role_title": "Default A", "rationale": "da"},
                {"role_title": "Default B", "rationale": "db"},
                {"role_title": "Default C", "rationale": "dc"},
            ]
        )
        items: list[dict[str, object]] = [{"role_title": "LLM Role", "rationale": "r"}]
        result = _to_contacts(items, config)

        assert len(result) == 3
        assert result[0].role_title == "LLM Role"
        # Padding must start from Default A (index 0), not Default B (index 1).
        assert result[1].role_title == "Default A"
        assert result[2].role_title == "Default B"
