from __future__ import annotations

import pytest

# pytest.importorskip skips the entire module (not an error) when src/contacts.py
# does not yet expose the updated _default_contacts signature (Wave 1 not landed).
# This keeps collection clean; test bodies below signal failure when collected.
contacts_mod = pytest.importorskip("src.contacts")

ContactExtractor = contacts_mod.ContactExtractor


class TestDefaultContacts:
    def test_default_contacts_from_config(self) -> None:
        # _default_contacts must read persona titles from
        # ICPConfig.default_personas (configs/icp.yaml) rather than returning
        # the hardcoded CX-vertical strings. Verifies FIX-05: config-driven
        # fallback so the pipeline can be retargeted without code changes.
        pytest.fail("not yet implemented")
