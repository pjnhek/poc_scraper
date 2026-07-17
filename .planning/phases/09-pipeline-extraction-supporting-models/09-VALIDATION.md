---
phase: 9
slug: pipeline-extraction-supporting-models
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-17
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Reconstructed from artifacts (State B) after the fact: this phase shipped
> before a VALIDATION.md was authored. Every requirement was already covered
> by automated tests written during execution; this document records that
> coverage. No Wave 0 or new tests were required.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (pytest-asyncio auto mode) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/functional/test_pipeline_open_deps.py tests/functional/test_enrich.py tests/unit/test_models.py -q` |
| **Full suite command** | `make test` (`uv run pytest -q`) |
| **Estimated runtime** | ~3 seconds (phase-9 subset); ~160 seconds full suite |

---

## Sampling Rate

- **After every task commit:** Run the quick command above
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds (phase-9 subset)

---

## Per-Task Verification Map

| Plan | Wave | Requirement | Threat Ref | Behavior | Test Type | Automated Command | File Exists | Status |
|------|------|-------------|------------|----------|-----------|-------------------|-------------|--------|
| 09-01 | 1 | INTEG-01 | — | `open_deps` yields the frozen `Deps` wiring seam (shared httpx pool, replay/record branching) reusable outside the pipeline entrypoint | functional | `uv run pytest tests/functional/test_pipeline_open_deps.py` | ✅ | ✅ green |
| 09-02 | 1 | INTEG-02 | — | `collect_context` promoted to module level; `NullBrowserbase` threads through the Exa-only branch | functional | `uv run pytest tests/functional/test_enrich.py tests/functional/test_browserbase_client.py` | ✅ | ✅ green |
| 09-03 | 1 | INTEG-03 | — | `EvidencePack.from_context` builds the numbered justification pack without a models<->enrich import cycle | unit | `uv run pytest tests/unit/test_models.py` | ✅ | ✅ green |
| 09-04 | 2 | INTEG-01, INTEG-02, INTEG-03 | — | Integration gate: extracted seams wired for downstream MCP reuse (no code changes; all gates green on merged Wave-1 changeset) | functional + unit | `uv run pytest tests/functional/test_mcp_server.py tests/unit/test_evidence.py` | ✅ | ✅ green |

*Status: pending · ✅ green · ❌ red · ⚠️ flaky*

Downstream consumers (`tests/functional/test_mcp_server.py`, `tests/unit/test_evidence.py`) additionally exercise the extracted seams end-to-end, so INTEG-01/02/03 are covered both in isolation and through their real MCP-server consumers.

Green evidence: `96 passed` across the phase-9 requirement tests (2026-07-17); full offline suite `512 passed`.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave 0 test scaffolding was needed — the extraction was test-driven, and each requirement shipped with dedicated coverage.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have automated verify (existing tests) or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra sufficient)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (phase-9 subset ~3s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-17 (reconstructed audit; 0 gaps, 96 tests green)
