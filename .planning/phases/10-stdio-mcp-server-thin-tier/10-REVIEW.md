---
phase: 10-stdio-mcp-server-thin-tier
reviewed: 2026-07-16T20:16:45Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - Makefile
  - pyproject.toml
  - src/config.py
  - src/mcp_server/__init__.py
  - src/mcp_server/__main__.py
  - src/mcp_server/evidence.py
  - src/mcp_server/server.py
  - src/mcp_server/wiring.py
  - src/models.py
  - tests/functional/test_mcp_server.py
  - tests/smoke/test_mcp_e2e.py
  - tests/unit/test_config.py
  - tests/unit/test_evidence.py
  - tests/unit/test_models.py
  - uv.lock
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-16T20:16:45Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

The stdio entrypoint, lifespan wiring, tool-level exception sanitization, dependency lock,
and test harness are coherent. The full offline suite passed with 357 tests, strict mypy
passed, and ruff plus black passed. Two defects remain: the MCP payload does not actually cap
all embedded evidence snippets, and the domain validator is too permissive for an untrusted
tool boundary.

## Critical Issues

### CR-01: Nested citation snippets bypass the MCP payload caps

**Classification:** BLOCKER

**File:** `src/mcp_server/evidence.py:30-46` (data fields originate at
`src/models.py:37-42`, `src/models.py:65-69`, and `src/models.py:81-83`)

**Issue:** `pack_from_context` caps `about_text`, the news item count, and each
`Justification.summary`, but it returns the original `NewsItem` instances and preserves each
original `Justification.citation`. Every `Citation` therefore retains its uncapped `snippet`.
News snippets are also duplicated under both `news[*].citation.snippet` and
`justifications[*].citation.snippet`. A crafted context at the existing upstream limits (five
2,000-character about snippets and ten 1,500-character news snippets) produces a 50,610-byte
`EvidencePack` JSON payload even though the visible justification summaries are capped. This
violates MCP-01's requirement that evidence snippets be capped at the MCP boundary and keeps
the context-window failure D-03 was intended to prevent.

**Fix:** Build MCP-safe copies of every nested `Citation` and `NewsItem` before constructing
the pack. Either remove `Citation.snippet` from the wire copies because
`Justification.summary` is the canonical evidence text, or cap it explicitly. Also cap
`NewsItem.summary`, which is another evidence-text path in the same payload. Add a regression
test that checks all nested snippet and summary lengths plus a defensible maximum serialized
payload size. For example:

```python
def _mcp_citation(citation: Citation) -> Citation:
    return citation.model_copy(update={"snippet": None})

safe_news = [
    item.model_copy(
        update={
            "summary": _truncate_words(item.summary, JUSTIFICATION_SUMMARY_MCP_CAP),
            "citation": _mcp_citation(item.citation),
        }
    )
    for item in news
]
```

Apply the same citation copy to every justification so no raw snippet remains through that
path.

## Warnings

### WR-01: Domain validation admits malformed, control-character, and unbounded input

**Classification:** WARNING

**File:** `src/models.py:27-34` (current coverage at `tests/unit/test_models.py:28-34`)

**Issue:** The validator only rejects the literal space character and requires one dot. It
accepts internal newlines or tabs, paths and query strings such as `example.com/path`, empty
labels such as `a..com`, labels beginning with a hyphen, and arbitrarily long strings. The MCP
tool treats this validator as its untrusted-input boundary, so malformed values can reach Exa
queries, consume provider requests, and inject control characters into warning logs instead
of returning the promised invalid-domain tool result.

**Fix:** Normalize an optional HTTP(S) URL with `urllib.parse`, then validate only the
hostname. Reject userinfo, ports unless deliberately supported, paths, queries, fragments,
control characters, hostnames longer than 253 characters, labels outside 1-63 characters,
and labels with invalid characters or leading/trailing hyphens. Add unit and in-memory MCP
tests for newline, tab, path, query, empty-label, bad-hyphen, and overlength inputs, all of
which should produce `isError: true` without calling the provider.

---

_Reviewed: 2026-07-16T20:16:45Z_
_Reviewer: the agent (gsd-code-reviewer, generic-agent workaround)_
_Depth: standard_
