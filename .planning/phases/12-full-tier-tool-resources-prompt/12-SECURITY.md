---
phase: 12
slug: full-tier-tool-resources-prompt
status: secured
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-17
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| MCP client -> process_account (via research_account_full) | run_eval/on_stage values originate from an untrusted MCP client | Boolean flag, callback invocations |
| MCP client -> resource read | Untrusted clients request resource URIs; responses must not leak server filesystem details | Resource URIs, file contents (public artifacts) |
| MCP client -> prompt render | Client-supplied domain string is interpolated into returned prompt text | Domain string (untrusted) |
| MCP client -> research_account_full | Untrusted domain string and run_eval flag enter the full pipeline | Domain string, boolean flag |
| Environment -> tier resolution | Env misconfiguration (keys present on a demo instance) must not expose the full tool | Env vars, tier decision |
| Transport -> full tier (post-review) | Full tier over HTTP is a public-exposure boundary; requires explicit operator opt-in | HTTP requests to full pipeline |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-12-01 | Repudiation | process_account status precedence | medium | mitigate | D-02 branch ordering: a deliberate eval skip can only resolve to clean/hook_suppressed, never judge_failed; enforced by tests/integration/test_pipeline_run_eval.py | closed |
| T-12-02 | Tampering | run_eval parameter (client-controlled) | low | accept | run_eval only narrows work (skips the judge); cannot bypass enrichment validation, citation validation, or hook suppression | closed |
| T-12-03 | Denial of Service | on_stage callback raising mid-run | low | accept | Pipeline contract unchanged (no swallow in process_account); additionally strengthened post-review: the MCP wrapper's own on_stage is best-effort (WR-02 fix, commit 11f3b7f), so a transport failure cannot destroy a completed run | closed |
| T-12-04 | Information Disclosure | read_icp_rubric / read_eval_report failure path | high | mitigate | OSError caught in-function, sanitized "resource unavailable" message returned, real cause to stderr only (D-08); leak-proof property asserted in tests/unit/test_mcp_resources.py | closed |
| T-12-05 | Tampering | Prompt text integrity (client-supplied domain interpolation) | low | accept | Prompt is advisory text executed by the client's own agent; adversarial domain only pollutes the caller's own prompt, no server-side execution surface | closed |
| T-12-06 | Information Disclosure | Served resource content | low | accept | configs/icp.yaml and evals/REPORT.md are committed public-repo artifacts scrubbed by the Phase 7 audit; verbatim serving discloses nothing non-public | closed |
| T-12-07 | Elevation of Privilege | Full-tool registration in demo mode | high | mitigate | Tier always derives from settings.mcp_tier() (demo check precedes key check); never re-derived from key presence; enforced by test_demo_hides_full_tool_even_with_full_keys_present. Post-review: full-tier/thin-lifespan mismatch now fails loudly (WR-01 fix, commit 1206729) | closed |
| T-12-08 | Information Disclosure | research_account_full error payloads | high | mitigate | _sanitized_validation_message plus catch-all "internal error, try again" from None with exc_info to stderr only (HOST-05 pattern) | closed |
| T-12-09 | Spoofing / Input Validation | domain argument | medium | mitigate | Validated through the same Account normalizer as the thin tool (ASVS V5) before any provider access; invalid domains never reach deps | closed |
| T-12-10 | Denial of Service | 30-60s full-pipeline call as exhaustion vector | low | accept | Full tool is BYOK/full-tier only, never registered in demo mode. Post-review hardening: full tier over HTTP now refuses to start without explicit MCP_ALLOW_FULL_HTTP=true opt-in (WR-03 fix, commit 8d76728), enforced by tests/unit/test_mcp_main_guard.py | closed |
| T-12-11 | Information Disclosure | Full-tool error payloads (regression surface) | high | mitigate | test_full_tool_invalid_domain_sanitized_error asserts sanitized invalid-domain text with no traceback or filesystem-path fragments over the wire | closed |
| T-12-12 | Repudiation | run_eval skip mislabeled as failure at the wire level | medium | mitigate | test_full_tool_run_eval_false_skips_judge pins eval_score null + clean status + zero judge calls over the actual JSON-RPC round-trip | closed |
| T-12-SC | Tampering | npm/pip/cargo installs (supply chain) | low | accept | No new packages introduced in Phase 12 (all four plans); mcp SDK already audited in Phase 10 | closed |

*Status: open - closed - open below high threshold (non-blocking)*
*Severity: critical > high > medium > low; only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) - accept (documented risk) - transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-02 | run_eval can only reduce work performed; all validation gates run before the eval stage | Plan 12-01 threat model (operator-approved plans) | 2026-07-17 |
| AR-12-02 | T-12-03 | Callback raise tears down only the raising MCP session; CLI path passes no callback. Residual risk further reduced by WR-02 best-effort wrapper | Plan 12-01 threat model; WR-02 resolution chosen by operator | 2026-07-17 |
| AR-12-03 | T-12-05 | Prompt text is client-side advisory; no server-side execution surface | Plan 12-02 threat model | 2026-07-17 |
| AR-12-04 | T-12-06 | Served artifacts are already public and scrubbed (Phase 7 audit) | Plan 12-02 threat model | 2026-07-17 |
| AR-12-05 | T-12-10 | Full tool is BYOK-gated and demo-hidden; residual public-HTTP exposure now requires explicit MCP_ALLOW_FULL_HTTP=true opt-in (WR-03). Phase 13 must still add transport hardening (auth/metering) before advertising full tier on a public endpoint | Plan 12-03 threat model; WR-03 resolution chosen by operator | 2026-07-17 |
| AR-12-06 | T-12-SC | No new dependencies this phase | Plans 12-01..12-04 threat models | 2026-07-17 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-17 | 13 | 13 | 0 | gsd-secure-phase orchestrator (L1 short-circuit: plan-time register, all mitigations grep-verified; post-fix state after 12-REVIEW-FIX.md commits 1206729/11f3b7f/8d76728) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed

## Scope Note

This audit is ASVS Level 1 (grep-depth mitigation verification against the plan-time STRIDE register), run after the 12-REVIEW.md warnings were fixed. It does not replace Phase 13's transport-hardening requirements (HOST-06 TransportSecuritySettings, hardened error payloads on the public endpoint). Full-tier public exposure remains opt-in-only until Phase 13 lands authentication/metering.
