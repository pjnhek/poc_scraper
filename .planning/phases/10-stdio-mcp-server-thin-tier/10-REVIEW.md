---
phase: 10-stdio-mcp-server-thin-tier
reviewed: 2026-07-16T21:13:32Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/mcp_server/evidence.py
  - tests/unit/test_evidence.py
  - src/models.py
  - tests/unit/test_models.py
  - tests/functional/test_mcp_server.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 10 Plan 10-04: Code Re-Review Report

**Reviewed:** 2026-07-16T21:13:32Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Plan 10-04 resolves the original evidence-cap bypass and the verifier's named malformed-domain
families. The final `EvidencePack` is measured using its actual UTF-8 JSON serialization, the
reducer terminates through finite tail-removal and binary-search steps, nested citation text is
cleared on frozen copies, retained provenance URLs are not rewritten, numbering is rebuilt, and
status is recomputed from retained content. The parameterized MCP test also creates a fresh
`FakeExa` for every case and directly proves that its recorded call list stays empty.

Three uncovered boundary cases remain. The domain parser accepts empty URL delimiters, IP
literals, and syntactically invalid punycode A-labels; invalid input is reflected without a size
bound in the MCP error; and the evidence filter can discard valid news that follows over-limit
items. These are new edge findings, not regressions of the original serialized-size algorithm.

## Prior Finding Resolution

### CR-01: Nested citation snippets bypass the MCP payload caps

**Resolution:** RESOLVED

`src/mcp_server/evidence.py:54-97` clears citation title/snippet fields on MCP-only frozen copies
and caps news headline/summary plus justification summary fields. `src/mcp_server/evidence.py:68-146`
measures `model_dump_json()` in UTF-8 bytes and reduces deterministic candidates until the result
fits `EVIDENCE_PACK_MAX_BYTES`. The final size is based on the real serializer, so Unicode and JSON
escaping overhead are included. The reduction loops terminate because every iteration either
advances a bounded binary-search interval or removes one tuple element. The adversarial tests cover
nested text, four-byte Unicode, escaping, long URLs, immutable inputs, and sequential numbering.

### WR-01: Domain validation admits malformed, control-character, and unbounded input

**Resolution:** PARTIALLY RESOLVED

`src/models.py:36-80` now rejects the verifier-named control characters, paths, non-empty queries
and fragments, userinfo, ports, empty or malformed labels, and overlength hostnames. The in-memory
MCP matrix asserts `isError is True` and `exa.calls == []` for every listed case. The active findings
below cover residual parser ambiguity and unbounded error reflection that the matrix does not test.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Empty URL delimiters and non-domain literals still cross the provider boundary

**File:** `src/models.py:43-80`

**Issue:** The validator checks `parsed.query` and `parsed.fragment` values, so delimiters with empty
values disappear during `urlsplit`. `example.com?`, `example.com#`, `https://example.com/?`, and
`https://example.com/#` are all accepted and normalized to `example.com`, contrary to the strict
root-only contract. The DNS-label regex also accepts IPv4 literals such as `127.0.0.1`, and accepts
DNS-shaped but invalid IDNA A-labels such as `xn--a.example`. An independent probe confirmed each
accepted form. The functional test's zero-call assertion is sound for its parameter list, but these
uncovered inputs would call Exa.

**Fix:** Reject the presence of `?` or `#` syntax even when the parsed component is empty. After
normalization, reject values accepted by `ipaddress.ip_address`. If `xn--` is intended to mean valid
punycode rather than merely DNS-shaped ASCII, validate those labels with a standard-library IDNA
decode/round-trip. Add each form to both the unit matrix and the MCP zero-provider-call matrix.

### WR-02: Invalid-domain errors reflect arbitrarily large client input

**File:** `src/models.py:31-34`

**Issue:** Every validation failure embeds the complete original value in `ValueError`. The MCP
handler extracts and returns that message (`src/mcp_server/server.py:50-57`). A one-million-character
invalid domain therefore produces a tool error of approximately one million bytes, even though the
same phase introduces a 24,000-byte evidence limit to protect client context. This leaves the
untrusted client boundary vulnerable to oversized error responses and means the overlength path is
not actually bounded or minimally sanitized.

**Fix:** Use a constant client-visible message such as `invalid domain`, or include only a small,
escaped prefix plus an explicit truncation marker. Add a functional test that submits an overlength
value and asserts both zero provider calls and a small maximum error-message size.

### WR-03: News is capped before invalid provenance is removed, causing avoidable evidence loss

**File:** `src/mcp_server/evidence.py:153-159`

**Issue:** `ctx.news_items[:NEWS_ITEM_MCP_CAP]` runs before `_url_within_cap`. If the first ten news
items have over-limit URLs and the eleventh has a valid URL, the function drops all ten selected
items, never considers the valid eleventh item, and returns an empty pack. An independent probe
reproduced `retrieval_status="empty"` with zero retained news despite valid cited evidence later in
the source tuple. This conflicts with discarding invalid evidence units while preserving the source
order of retained units. The current tests cover all-safe truncation and a lone over-limit unit, so
they do not expose the ordering bug.

**Fix:** Filter indivisible over-limit news units first, preserve their relative order, and then take
the first `NEWS_ITEM_MCP_CAP` retained units. Add a regression with ten over-limit items followed by
one safe item and assert that the safe item is returned with sequential justification numbering.

## Gate Results

- Offline suite: 398 passed, 3 smoke tests deselected (orchestrator-confirmed)
- Strict mypy: clean across 32 source files (orchestrator-confirmed)
- Ruff: clean (orchestrator-confirmed)
- Black: clean, 76 files unchanged (orchestrator-confirmed)
- Review probes: exact empty-delimiter/IP acceptance, unbounded error size, and post-cap safe-news
  loss reproduced locally without network access

---

_Reviewed: 2026-07-16T21:13:32Z_
_Reviewer: the agent (gsd-code-reviewer, generic-agent compatibility workaround)_
_Depth: standard_
