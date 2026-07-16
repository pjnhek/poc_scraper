---
phase: 10
slug: stdio-mcp-server-thin-tier
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-16
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest>=8.2.0` with `pytest-asyncio>=0.23.0` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, strict markers) |
| **Quick run command** | `uv run pytest tests/unit/test_evidence.py tests/unit/test_models.py tests/functional/test_mcp_server.py -x -q` |
| **Strict type command** | `uv run mypy src/mcp_server/evidence.py src/models.py tests/unit/test_evidence.py tests/unit/test_models.py tests/functional/test_mcp_server.py` |
| **Full suite command** | `make test && make typecheck && make lint` |
| **Feedback target** | Each targeted task command completes within 60 seconds; use the full offline gate after the wave |

---

## Sampling Rate

- **After Task 10-04-01:** Run `uv run pytest tests/unit/test_evidence.py -x -q && uv run mypy src/mcp_server/evidence.py tests/unit/test_evidence.py`
- **After Task 10-04-02:** Run `uv run pytest tests/unit/test_models.py tests/functional/test_mcp_server.py -x -q && uv run mypy src/models.py tests/unit/test_models.py tests/functional/test_mcp_server.py`
- **After Wave 4:** Run `make test && make typecheck && make lint`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for each targeted task command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-04-01 | 04 | 4 | MCP-01 | T-10-04 | Exact serialized UTF-8 byte budget covers multibyte text and long URLs; retained citations are never truncated | unit | `uv run pytest tests/unit/test_evidence.py -x -q && uv run mypy src/mcp_server/evidence.py tests/unit/test_evidence.py` | yes | pending |
| 10-04-02 | 04 | 4 | MCP-07 | T-10-03 / T-10-08 | Malformed domains return sanitized tool errors before any Exa request | unit + functional | `uv run pytest tests/unit/test_models.py tests/functional/test_mcp_server.py -x -q && uv run mypy src/models.py tests/unit/test_models.py tests/functional/test_mcp_server.py` | yes | pending |

*Status values: pending, green, red, flaky.*

---

## Wave 0 Requirements

Existing infrastructure covers Wave 0. `pytest`, `pytest-asyncio`, strict mypy, Ruff, Black, the MCP in-memory client, `FakeExa.calls`, and all three target test modules already exist. Plan 10-04 adds RED cases directly to those files before production changes; no scaffold, dependency, fixture module, or marker is missing.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MCP-01, MCP-07 | All gap-closure behavior is deterministic and covered by unit plus in-memory MCP tests | No manual step |

The prior real-client stdio checkpoint remains valid and is outside the two automated gap-closure tasks.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification commands
- [x] Sampling continuity: both tasks have targeted test and strict-type gates
- [x] Wave 0 has no missing infrastructure references
- [x] No watch-mode flags
- [x] Feedback target is under 60 seconds for targeted commands
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved for Plan 10-04 gap execution, 2026-07-16
