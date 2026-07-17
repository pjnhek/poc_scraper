---
phase: 13
slug: hosted-deploy-docs-close
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-17
---

# Phase 13 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Scope note:** the threat register below was authored across all five PLAN files against a Fly.io deploy target. Mid-phase (plan 13-04), the deploy target pivoted Fly.io -> Hugging Face Spaces -> Oracle Cloud Always Free, because both Fly.io and HF Spaces gate container hosting behind a payment method or PRO subscription. The live public endpoint is `https://170.9.7.144.sslip.io/mcp` on a single Oracle Cloud VM behind a Caddy reverse proxy, not a Fly.io URL. This pivot was reviewed and accepted at phase-verification time (`13-VERIFICATION.md` frontmatter `overrides`). This audit verifies each threat's declared mitigation *intent* against the code that actually ships and runs live (Oracle + Caddy), not the literal Fly.io wording, consistent with the critical context supplied for this audit run. `Dockerfile`, `fly.toml`, and `scripts/push_hf_space.py` remain committed as documented, non-primary alternatives (`docs/DEPLOY.md` appendices) and are still verified below since they are shipped, reachable code paths.

This audit also verifies **five post-phase hardening commits** (`3460bc1`..`fa93920`, landed after the phase's own commits, found by two adversarial Codex reviews) that harden threats already in this register: Caddy `Fly-Client-IP` header overwrite (closes a spoofing gap in T-13-11/HOST-04's trust boundary), Oracle env file `chmod 600` (T-13-09), HF Space push secret/symlink rejection (T-13-04's intent, extended to the HF alternative), the bind-address drop from the DNS-rebinding allowlist (hardens T-13-01 beyond its original wildcard-only exclusion), and the `fly scale count 1` addition to `make deploy-fly` (T-13-05).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|----------------|
| Internet client -> hosted edge -> app HTTP transport | Untrusted Host/Origin headers cross here; DNS-rebinding surface. Live implementation: Caddy (TLS termination + Host vhost match) in front of a loopback-only container on the Oracle VM; `fly.toml`'s Fly-edge equivalent remains committed as the documented alternative. | Host/Origin headers, JSON-RPC MCP payloads |
| Operator env -> Settings | `MCP_PUBLIC_HOSTNAME` / `MCP_HTTP_HOST` configuration errors become security posture errors | Env vars -> `Settings` fields |
| Public repo -> deploy artifacts | `Dockerfile`, `fly.toml`, `.dockerignore`, `deploy/oracle/*.sh`, `scripts/push_hf_space.py` are committed publicly; any secret placed in them leaks | Build-context files, deploy scripts |
| Deploy platform -> container/VM runtime | Secrets delivered as runtime env vars (Fly secrets, or the Oracle VM's owner-only `mcp.env`), never baked into image layers | `EXA_API_KEY` |
| Server internals -> MCP client payload | Exception content crosses from trusted process internals to untrusted clients; sanitization is the control under test | Tool error text (`isError` results) |
| Internet -> public hosted URL | Fully untrusted traffic reaches the demo endpoint; rate limits and the DNS-rebinding allowlist are the only gates (by design, AR-12-05; no auth this milestone) | JSON-RPC MCP requests, `Fly-Client-IP` header |
| Operator terminal -> secrets store | `EXA_API_KEY` crosses here once (Fly secrets, or manual edit of the Oracle VM's `mcp.env`); never enters the repo or the executor's context | `EXA_API_KEY` value |
| Public repo README/CLAUDE.md -> the internet | Published markdown; must not leak secrets or violate public-repo discipline (seller identity stays abstract) | Client config snippets, live URL, project charter text |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-13-01 | Spoofing | `TransportSecuritySettings` allowlist in `build_server` | high | mitigate | Public hostname sourced from a dedicated setting (`mcp_public_hostname`); bind address entirely excluded from `allowed_hosts` (post-phase hardening `7ff38d6` went beyond the original wildcard-only exclusion and dropped the bind-derived entry unconditionally) | closed |
| T-13-02 | Tampering | Startup configuration path in `__main__.py` | medium | mitigate | D-06 fail-fast guard: non-loopback bind with no public hostname raises `SystemExit` before serving | closed |
| T-13-03 | Information Disclosure | Guard `SystemExit` message | low | accept | Message names the bind value and the env var name of the fix; operator-facing stderr at startup, never a tool payload | closed |
| T-13-04 | Information Disclosure | `Dockerfile` / `fly.toml` / `.dockerignore` | high | mitigate | `EXA_API_KEY` only ever via `fly secrets set` (D-13); grep gate asserts neither committed artifact contains the key name; `.dockerignore` excludes `.env`/`credentials*.json`; pre-commit public-discipline guard runs on both files | closed |
| T-13-05 | Denial of Service (economic) | `fly.toml` machine scaling / live single-instance posture | high | mitigate | Single region, `min_machines_running = 0`, suspend-on-idle (D-01/D-02); `make deploy-fly` now runs `fly scale count 1` (post-phase hardening `ad36f73`); live Oracle target is by-construction single-VM/single-container (no scale-out mechanism), independently confirmed (`docker ps -a` = 1 container) | closed |
| T-13-06 | Denial of Service (self-inflicted) | Fly smoke/health checks vs MCP JSON-RPC endpoint | medium | mitigate | `make deploy-fly` uses `--smoke-checks=false`; no `[[http_service.checks]]` block in `fly.toml` | closed |
| T-13-07 | Information Disclosure | `get_account_evidence` error paths | high | mitigate | Banned-substring integration tests over all three error paths including a poisoned internal exception; sanitized `ValueError`-from-`None` pattern | closed |
| T-13-08 | Repudiation | Server-side logging of real errors | low | accept | Full detail (`exc_info=True`) stays on stderr logs for the operator; only sanitized text crosses the client boundary | closed |
| T-13-09 | Information Disclosure | `EXA_API_KEY` handling during deploy | high | mitigate | Secret set only by the operator (Fly: `fly secrets set`; live Oracle target: manual SSH edit of `mcp.env`, executor never saw the value); env file now `chmod 600` (post-phase hardening `b931994`) | closed |
| T-13-10 | Denial of Service (economic) | Public unauthenticated endpoint spending Exa credits | high | mitigate | `MCP_DEMO_MODE=1` baked into the image and the Oracle env file; live log/verification confirmed thin tier and 5/25/5 limits; single-instance pin keeps caps truly global | closed |
| T-13-11 | Spoofing | Live Host-header handling at the hosted edge | medium | mitigate | Live `initialize` POST confirmed the allowlist accepts the real forwarded Host (both Fly-style and the live Caddy edge); Caddy now overwrites client-supplied `Fly-Client-IP` from `{remote_host}` (post-phase hardening `3460bc1`), closing a rate-limit-bucket spoofing gap this threat's original wording did not anticipate | closed |
| T-13-12 | Information Disclosure | Live tool error payloads | high | mitigate | D-14 checkpoint: human triggered an invalid-domain failure over the live URL and inspected the payload for leaks before approving | closed |
| T-13-13 | Information Disclosure | README/CLAUDE.md edits | medium | mitigate | Docs contain only the public hostname and public commands; no keys, no vendor names; pre-commit public-discipline guard and `verify-public-repo` both pass (0 hits) | closed |
| T-13-14 | Spoofing (social) | Published client snippets | low | accept | Snippets point only at the project's own confirmed live hostname; no third-party URLs beyond `npx mcp-remote` | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Verification Evidence

| Threat ID | Evidence |
|-----------|----------|
| T-13-01 | `src/config.py:141-148` (`mcp_public_hostname` field, D-05 WHY comment); `src/mcp_server/server.py:261-304` (`build_server`, local `allowed_hosts`/`allowed_origins`, bind address never appended, public hostname appended bare + `:443` only when set); `tests/functional/test_mcp_http_transport.py::test_public_hostname_allowed_but_bare_bind_address_is_not`, `::test_bind_address_is_not_trusted_as_host`, `::test_public_hostname_is_allowed`, `::test_dns_rebinding_rejected_for_foreign_host` — all pass (27/27 in the phase-13 test run below) |
| T-13-02 | `src/mcp_server/__main__.py:47-72` (`guard_non_loopback_requires_public_hostname`), called at `__main__.py:83` before `build_server`/`asyncio.run`; `tests/unit/test_mcp_main_guard.py` (4 new tests: refuse / allow / loopback-unaffected / stdio-unaffected) |
| T-13-03 | `src/mcp_server/__main__.py:66-72` — `SystemExit` message contains `repr(settings.mcp_http_host)` and the literal substring `MCP_PUBLIC_HOSTNAME`; raised before any server/transport starts, never reaches a client |
| T-13-04 | `Dockerfile` (no `EXA_API_KEY`/`MCP_PUBLIC_HOSTNAME` string present); `fly.toml` (no `EXA_API_KEY` string); `.dockerignore:15-19` (`.env`, `.env.local`, `credentials*.json`, `service-account*.json`); `grep -qi EXA_API_KEY Dockerfile fly.toml` returns no hits (independently re-run) |
| T-13-05 | `fly.toml:1-22` (single `primary_region`, `min_machines_running = 0`, `auto_stop_machines = "suspend"`, no machine-count key); `Makefile:96-98` (`deploy-fly` target runs `fly deploy --smoke-checks=false` then `fly scale count 1 --yes`); live Oracle: `13-04-SUMMARY.md` D3 (`oci compute instance list` = 1, `docker ps -a` = 1 container) |
| T-13-06 | `fly.toml` has no `[[http_service.checks]]` block (confirmed by read); `Makefile:97` (`fly deploy --smoke-checks=false`) |
| T-13-07 | `tests/integration/test_mcp_error_sanitization.py` — `BANNED_SUBSTRINGS` tuple (line 17) checked in a loop against `result.content[0].text` across 3 tests (`test_invalid_domain_error_is_sanitized`, `test_provider_failure_error_is_sanitized`, `test_unexpected_internal_error_is_sanitized`); all pass, including the poisoned-secret-fragment case |
| T-13-08 | `src/mcp_server/server.py:104-106` and `:228-230` — `log.warning(..., exc_info=True)` for both `get_account_evidence` and `research_account_full` catch-all paths |
| T-13-09 | `13-04-SUMMARY.md` "User Setup Required" (operator SSH'd in, edited `/opt/poc-scraper/mcp.env`, re-ran `setup.sh`; executor never read the value); `deploy/oracle/setup.sh:134-137` (`chmod 600 "$ENV_FILE"` applied every run, both fresh-write and pre-existing file paths) |
| T-13-10 | `Dockerfile:16-18` (`MCP_DEMO_MODE=1`, `MCP_HTTP_HOST=0.0.0.0` baked in); `deploy/oracle/setup.sh:126` (env file template sets `MCP_DEMO_MODE=1`); `13-04-SUMMARY.md` D1/D3 (live confirmation of thin tier, single container) |
| T-13-11 | `13-VERIFICATION.md` behavioral spot-check table (fresh `curl` re-confirmation: forged `Host: evil.example.com` returns 0-byte body at the Caddy edge, matching the recorded live result); `deploy/oracle/setup.sh:140-151` (Caddyfile `header_up Fly-Client-IP {remote_host}`); `tests/unit/test_deploy_caddy_config.py::test_caddy_overwrites_fly_client_ip_from_real_peer`, `::test_caddy_reverse_proxies_only_to_loopback` — both pass |
| T-13-12 | `13-04-SUMMARY.md` D2 (D-14 checkpoint: `get_account_evidence("not-a-domain")` over the live URL returned exactly one line, `"Error executing tool get_account_evidence: invalid domain"`, no stack trace/env names/key fragments/file paths) |
| T-13-13 | `grep -c '—' README.md` = 0 (independently re-run); `git show 51f46a5 -- CLAUDE.md` shows 0 em-dash additions, 17 insertions all in hand-authored sections; `uv run python -m scripts.verify_public_repo` = "0 hits in tracked content, 0 hits in history reachable from any ref (commit fa93920)" (independently re-run) |
| T-13-14 | `grep -n "sslip.io" README.md` — all 5 client-snippet URLs point at `https://170.9.7.144.sslip.io/mcp` (the project's own confirmed live endpoint); no other external URL present besides the `npx mcp-remote` bridge package name |

**Independently re-run test evidence (this audit, not cited from SUMMARY):**
```
uv run pytest tests/functional/test_mcp_http_transport.py tests/unit/test_mcp_main_guard.py \
  tests/integration/test_mcp_error_sanitization.py tests/unit/test_deploy_caddy_config.py \
  tests/unit/test_push_hf_space.py -q
=> 27 passed, 6 warnings (deprecation notices only, unrelated to security)

uv run python -m scripts.verify_public_repo
=> verify-public-repo: 0 hits in tracked content, 0 hits in history reachable from any ref (commit fa93920)
```

---

## Unregistered Flags (informational, non-blocking)

No `## Threat Flags` section was present in any of the five `13-0N-SUMMARY.md` files (confirmed by grep across all five). However, this audit's own review of the shipped diff identified attack surface that emerged from the mid-phase deploy-target pivot (Fly.io -> HF Spaces -> Oracle Cloud Always Free) without a dedicated STRIDE entry in the original register. Both are already well-mitigated in the shipped code (verified above); they are logged here so future audits do not silently assume the original 14-threat Fly.io-scoped register is exhaustive for the live target:

1. **`deploy/oracle/setup.sh` / `deploy/oracle/provision.sh`** — an entirely new hosting stack (Oracle Cloud VM, SSH access, Caddy reverse proxy, host-level iptables rules, systemd services, a swapfile on low-RAM shapes) introduced mid-phase. No discrete threat IDs were registered for this surface; its intent is covered piecemeal by T-13-04/T-13-05/T-13-09/T-13-11 (accepted at phase-verification time via the documented override), but items like host firewall correctness (`setup.sh:75-87`) and the external-IP-echo-service fallback (`setup.sh:97-121`, added as a Rule-1 bug fix) had no explicit STRIDE registration. Recommend a future phase or milestone give the Oracle deploy path its own threat register entries if it becomes the permanent primary target.
2. **`scripts/push_hf_space.py`** — a new deploy artifact (uploads a Docker build context to a public Hugging Face Space) with no threat entry in any of the five PLAN files (all five predate the HF Spaces pivot attempt). Its secret/symlink filtering (`_reject_secrets_and_symlinks`, `_refuse_symlink`) is well-tested (`tests/unit/test_push_hf_space.py`, 6 tests, all pass) and conceptually mirrors T-13-04's intent, but was never formally registered.

Neither item blocks this audit (`threats_open: 0`): both are shipped with working mitigations independently verified above, and both are non-primary, documented alternatives (`docs/DEPLOY.md` appendices), not the live production path.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|--------------|------|
| AR-13-01 | T-13-03 | Fail-fast `SystemExit` message names the misconfigured bind value and `MCP_PUBLIC_HOSTNAME` by design (actionable operator diagnostics); it only ever reaches an operator's own stderr at process startup, before any transport is listening, never a network client or tool payload. Same pattern already accepted for the Phase 12 WR-01/WR-03 guards. | 13-CONTEXT.md D-06 design intent; this audit | 2026-07-17 |
| AR-13-02 | T-13-08 | Full exception detail (`exc_info=True`) is deliberately retained in server-side stderr logs so an operator can diagnose real failures; only the sanitized client-facing message crosses the trust boundary tested by T-13-07/HOST-05. Consistent with the shipped Phase 10-12 posture. | 13-CONTEXT.md; this audit | 2026-07-17 |
| AR-13-03 | T-13-14 | Published client-connect snippets reference only the project's own confirmed live hostname (`170.9.7.144.sslip.io`) plus the `npx mcp-remote` bridge, which RESEARCH.md already legitimacy-audited before this phase's docs were written. No third-party URL is asserted as trustworthy beyond that. | 13-RESEARCH.md Open Question 3; this audit | 2026-07-17 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|----------------|--------|------|--------|
| 2026-07-17 | 14 | 14 | 0 | gsd-security-auditor (Claude, State B retroactive audit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-17
