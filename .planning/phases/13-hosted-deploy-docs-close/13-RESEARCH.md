# Phase 13: Hosted Deploy & Docs Close - Research

**Researched:** 2026-07-17
**Domain:** Fly.io deployment of a Python streamable-HTTP MCP server; charter/README documentation close
**Confidence:** MEDIUM-HIGH (code-level decisions HIGH; Fly.io-specific deploy mechanics MEDIUM per the roadmap's own "no confirmed reference" flag)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fly machine lifecycle (HOST-06)**
- D-01: Idle behavior is auto-suspend (`auto_stop_machines = "suspend"`), not full stop and not always-on. Suspend freezes VM memory on idle and restores it on wake, so the in-memory `DemoLimiter` counters survive quiet periods; counters reset only on deploys/crashes (already accepted). Sustained abuse keeps the machine awake.
- D-02: Cost ceiling is a few dollars per month (up to ~$5/mo acceptable). Sane defaults: shared-cpu-1x, 256MB, one machine, suspend on idle. Expected realistic spend under $1-2/mo. Document expected monthly cost in the deploy runbook.
- D-03: `fly.toml` pins exactly one machine (roadmap criterion 2 verbatim) so the in-memory counters are truly global. No external counter storage; single-machine globality is the mechanism.

**Public hostname & app identity (HOST-06)**
- D-04: Fly app name is `poc-scraper-mcp` (public URL `poc-scraper-mcp.fly.dev`, published in the README). If the name is taken, pick the closest available repo-plus-surface variant and keep README/fly.toml consistent.
- D-05: The public hostname is a NEW setting distinct from `mcp_http_host` (which stays a pure bind address per 11-SECURITY's scope correction). When set, it sources the `TransportSecuritySettings` allowed-hosts allowlist. Exact setting name and allowlist entry mechanics (port variants) are Claude's discretion.
- D-06: Fail fast at startup when serving HTTP on a non-loopback bind (e.g. `0.0.0.0`) with no public hostname configured: refuse to start with a clear message, matching the WR-01/WR-03 fail-loud precedent. Loopback binds keep Phase 11's existing localhost allowlist untouched, so `make mcp-http`/`make mcp-demo` local workflows are unaffected.
- D-07: The `0.0.0.0` bind must never appear in `allowed_hosts` (roadmap criterion 2). The integration test pairs a `0.0.0.0` bind with the external Fly hostname in the Host header and asserts acceptance, plus rejection of non-allowlisted hosts. This closes the 12-REVIEW WR-03 observation that `0.0.0.0:{port}` was itself allowlisted.

**README & docs shape (DOCS-01, DOCS-02)**
- D-08: README placement: a short "Try it live" hook near the top with the hosted URL, plus a fuller MCP section lower down carrying the three client config snippets (Claude Desktop JSON, Claude Code, `npx mcp-remote`) and the grounding contrast.
- D-09: Full BYOK subsection in the README's MCP section: `make mcp`, which keys unlock the full tier, and what `research_account_full` returns.
- D-10: The grounding-by-instruction (thin) vs grounding-by-construction (full) contrast is the centerpiece framing of the MCP section. Exact prose is Claude's discretion; no em-dashes in published markdown.
- D-11: CLAUDE.md gets a full charter sync: `mcp>=1.28,<2.0` in the locked stack, MCP surface noted in scope, file-layout tree updated with `src/mcp_server/` (`evidence.py`/`limits.py`/`server.py`/`wiring.py`/`__main__.py`), new Makefile targets (`mcp`, `mcp-http`, `mcp-demo`, `smoke-mcp`, `deploy`), and MCP-relevant failure modes (rationing, fail-closed IP, sanitized tool errors).
- D-12: The pinned Loom keeps its commit pin and gains a one-line scope note that the video covers the v1.0 pipeline and the MCP surface is newer. No re-record this phase.

**Deploy workflow & verification (HOST-03, HOST-05)**
- D-13: Dockerfile and `fly.toml` are committed to the public repo (no secrets; Exa key lives as a Fly secret). Deploys run via `make deploy` wrapping `fly deploy`. No GitHub Actions CD.
- D-14: Live verification of HOST-03 and HOST-05 is a manual real-client checkpoint: a human pastes the URL into a real client (Claude Code or `npx mcp-remote`), retrieves cited evidence for one domain, then triggers an invalid-domain failure and inspects the error payload for leaks. Offline tests carry repeatable error-path coverage; the live check is a one-time gate. No scripted live-smoke target.
- D-15: Operator runbook lives at `docs/DEPLOY.md`: `fly launch` dry run notes, secrets setup, deploy, suspend/cost expectations, teardown. README's MCP section links to it.

**Locked by prior phases / requirements (do not re-litigate)**
- Hosted deploy always sets `MCP_DEMO_MODE=1`: thin tier only, `NullBrowserbase`, rationing on. The Dockerfile runs the `make mcp-demo` equivalent (HTTP + demo mode) and overrides the bind host to `0.0.0.0`.
- Full tier over HTTP requires explicit `MCP_ALLOW_FULL_HTTP=true` opt-in (already shipped, commit `8d76728`); the public endpoint never advertises the full tier and Phase 13 adds no auth (AR-12-05 accepted risk).
- Rationing errors, sanitized `isError: true` results, plain messages, no machine codes; "rationed, never broken" credit-exhaustion masquerade.
- Client IP from `Fly-Client-IP` only, fail-closed shared bucket (already shipped Phase 11).
- `mcp_http_host` is a bind address, never a Host header value.
- Stack pin `mcp>=1.28,<2.0`; strict mypy, no new overrides; 5-layer test strategy; conventional commits; no emojis; no em-dashes in published markdown.
- Roadmap research flag: do an early `fly launch` dry run before writing the Dockerfile/`fly.toml` in earnest -- no confirmed reference exists for Python + streamable HTTP on Fly.

### Claude's Discretion
- Public-hostname setting name (e.g. `MCP_PUBLIC_HOSTNAME`) and exact allowlist entry composition (port variants, whether `hostname:443` is needed alongside bare hostname).
- Dockerfile shape (base image, uv-in-Docker pattern, layer caching), Fly region, health-check configuration, and `fly.toml` internals beyond the locked one-machine pin and suspend behavior.
- Exact README prose, snippet formatting, and section ordering within D-08/D-09/D-10 constraints; DEPLOY.md structure.
- How the fail-fast non-loopback check is implemented and its exact message wording (D-06 semantics are locked).
- Suspend-fallback handling if Fly falls back from suspend to stop on a given host (accept silently; counters reset is already an accepted outcome).

### Deferred Ideas (OUT OF SCOPE)
- Loom re-record or a short MCP demo clip -- not this phase; candidate for a future milestone if the MCP surface becomes the primary artifact.
- PyPI packaging, endpoint auth, GitHub Actions CD, external counter storage, full-tier exposure on the public endpoint (stays opt-in-only per AR-12-05) -- all out of scope for the milestone.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HOST-03 | A stranger can connect to the hosted Fly.io URL (directly or via `npx mcp-remote`) with zero setup and retrieve cited evidence | Dockerfile + fly.toml patterns below; `mcp-remote` verified legitimate (npm registry, 401k weekly downloads, GitHub repo); Fly.io Host-header-forwarding behavior researched to confirm client-visible hostname |
| HOST-05 | Tool error payloads never contain stack traces, env names, or key fragments | Existing sanitized-error pattern (Phase 10/11/12) already covers this; research adds a recommended cross-cutting banned-substring test plus the D-14 live-check protocol |
| HOST-06 | Explicit `TransportSecuritySettings` allowed-hosts allowlist sourced from a public-hostname setting distinct from the bind address; `0.0.0.0` never appears in `allowed_hosts`; `fly.toml` pins exactly one machine | `TransportSecuritySettings` source read directly from the installed `mcp==1.28.x` package (exact-match + `:*` wildcard-port semantics confirmed); Fly.io single-machine pinning mechanics researched (`fly scale count 1`, `min_machines_running`, `auto_stop_machines`) |
| DOCS-01 | CLAUDE.md amended: `mcp>=1.28,<2.0` in locked stack, MCP surface noted in scope | Already true in `pyproject.toml`; CLAUDE.md stack section is the only gap -- direct edit, no new research needed |
| DOCS-02 | README gains an MCP section with client config snippets (Claude Desktop, Claude Code, `npx mcp-remote`) plus the grounding contrast | Verified current syntax for all three client configs (Claude Desktop JSON, `claude mcp add --transport http`, `npx mcp-remote <url>`) against official/current sources |
| TEST-01 | Full offline test suite covers tiering, limits (injected clock), evidence construction, error paths; strict mypy stays clean | Existing test files inventoried (`tests/functional/test_mcp_http_transport.py`, `tests/unit/test_mcp_main_guard.py`, `tests/unit/test_limits.py`) to identify the exact pattern this phase's new tests (public-hostname allowlist, fail-fast guard) must follow |

</phase_requirements>

## Summary

This phase has almost no new Python surface: the `mcp` SDK is already pinned (`mcp>=1.28,<2.0` in `pyproject.toml`), the rate limiter, tier gating, and error-sanitization patterns already exist and are already security-audited (11-SECURITY.md, 12-SECURITY.md). What's new is (1) a small, well-scoped code change -- a `mcp_public_hostname` setting that parametrizes the *existing* `TransportSecuritySettings` allowlist construction in `src/mcp_server/server.py`, plus a fail-fast startup guard in `__main__.py` mirroring the already-shipped WR-03 pattern -- and (2) genuinely new artifacts: `Dockerfile`, `fly.toml`, `docs/DEPLOY.md`, a `make deploy` target, and README/CLAUDE.md doc edits.

The 12-SECURITY.md scope note is explicit that Phase 11's allowlist work does NOT make the `0.0.0.0` Docker bind work in production: a real client sends the public Fly hostname (`poc-scraper-mcp.fly.dev`) as its `Host` header, which the current loopback-only allowlist would reject with 421. This phase closes that gap by adding a hostname entry sourced from a setting that is deliberately separate from the bind address, and by adding the integration test the roadmap's success criterion 2 names explicitly (pair a `0.0.0.0` bind with the external Host header, assert acceptance and rejection).

The riskiest unknowns are Fly.io-specific, not MCP-specific, and the roadmap already flags this ("no confirmed reference exists for Python + streamable HTTP on Fly"): Fly's own official docs mostly document Node.js MCP deployments, not Python; the `fly launch` smoke-check step is documented to "confuse" MCP servers (POST-only JSON-RPC endpoint, no plain GET health response) and Fly's own guide recommends `--smoke-checks=false`; and "pin to exactly one machine" is an operational discipline (`fly scale count 1`, single region, no autoscaler) more than a single `fly.toml` key. The roadmap's own instruction to run an early `fly launch` dry run before finalizing the Dockerfile/`fly.toml` is the right mitigation and should be a literal Wave 0 task in the plan.

**Primary recommendation:** Add `mcp_public_hostname: str = ""` to `Settings`, thread it into `build_server`'s existing `TransportSecuritySettings` construction (additive entries, not a replacement), add the D-06 fail-fast guard in `__main__.py` following the `guard_full_tier_http_exposure` pattern exactly, then do a throwaway `fly launch --no-deploy` (or equivalent dry run) to observe the actual generated `fly.toml` and any Fly-side surprises before hand-authoring the final Dockerfile/`fly.toml` with `internal_port` matching `mcp_http_port` (8000), `auto_stop_machines = "suspend"`, `min_machines_running = 0`, and `--smoke-checks=false` on the eventual `fly deploy`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Public hostname routing / TLS termination | CDN / Edge (Fly Proxy) | — | Fly terminates TLS at its edge and forwards plain HTTP to the app; the app never sees a certificate, only the `Host`/`Fly-Client-IP` headers Fly sets |
| DNS-rebinding / Host-header validation | API / Backend (MCP server process) | — | `TransportSecuritySettings` runs inside the FastMCP/Starlette app, not at the Fly edge; this is application-layer defense, matching the existing localhost-allowlist pattern from Phase 11 |
| Per-IP / global rate limiting | API / Backend (`DemoLimiter`, in-memory) | Database / Storage (implicitly, via single-machine pin) | In-memory counters only stay globally correct if exactly one process holds them -- the single-machine `fly.toml` pin is what keeps "API tier owns limiting" true; multiple machines would silently fragment it into per-machine limits |
| Container build / dependency install | Build/Deploy (Dockerfile, uv) | — | New tier for this project; no existing Dockerfile precedent, so the uv multi-stage pattern is adopted wholesale from `docs.astral.sh` guidance |
| Secret delivery (EXA_API_KEY) | Platform / Fly secrets store | — | Never baked into the image or `fly.toml` (both committed to the public repo); delivered at runtime via `fly secrets set`, matching D-13 |
| Client connection (stranger's MCP client) | Browser / Client (Claude Desktop, Claude Code, `npx mcp-remote`) | — | Entirely outside this repo's process boundary; the repo only needs to document three connection shapes, not implement any client code |
| Documentation surface (README, CLAUDE.md, DEPLOY.md) | Docs (no runtime tier) | — | Pure content; no code path reads these at runtime |

## Standard Stack

### Core

No new Python packages this phase. The `mcp` SDK pin is already in place and already audited.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | `>=1.28,<2.0` (already pinned, `pyproject.toml:20`) | FastMCP server, `TransportSecuritySettings`, streamable HTTP transport | Already the project's locked SDK; `T-11-SC`/`T-12-SC` in prior security audits confirm no new dependency risk this phase since nothing changes in `pyproject.toml`/`uv.lock` |

### Supporting (non-Python, deploy-time)

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `fly` CLI (flyctl) | latest stable | `fly launch`, `fly deploy`, `fly secrets set`, `fly scale count` | Every deploy-workflow step in D-13/D-15 |
| Docker | any recent Engine | Build the container image `fly deploy` ships | Required by `fly deploy` unless using Fly's remote builder (still needs a Dockerfile either way) |
| `uv` | already the project's package manager | Installs deps inside the Docker build stage via `uv sync --frozen` | Matches the project's existing `Makefile`/`pyproject.toml` conventions; avoids a second dependency-resolution tool inside the container |
| `mcp-remote` (npm, run via `npx`, **not a repo dependency**) | `0.1.38` current (verified via `npm view`) | Bridges stdio-only MCP clients to the hosted streamable-HTTP URL | README's `npx mcp-remote <url>` snippet (D-08); end-user-run, never installed into this repo's `package.json`/`pyproject.toml` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fly.io | Railway | Design spec's explicit fallback if Fly friction appears (`docs/superpowers/specs/2026-07-15-mcp-server-design.md` §Deployment); CONTEXT.md and REQUIREMENTS.md both commit to Fly as primary, so this stays a documented fallback only, not something to build in parallel |
| `auto_stop_machines = "suspend"` | `"stop"` (cold start) or `"off"` (always-on) | Locked by D-01; suspend uniquely preserves in-memory `DemoLimiter` state across idle periods without the cost of always-on |
| Manual `fly deploy` via `make deploy` | GitHub Actions CD | Explicitly out of scope (D-13); deploy stays a deliberate manual act |
| `TransportSecuritySettings` allowlist | Custom ASGI Host-header middleware | Don't hand-roll (see below); the SDK ships exactly this feature and it's already wired into `build_server` |

**Installation:** No new Python installs. Dockerfile installs the existing lockfile via `uv sync --frozen --no-dev` (production image; `--extra dev` is a local/CI-only concern).

**Version verification:** `mcp>=1.28,<2.0` confirmed present in `pyproject.toml:20` (already installed, `.venv` inspection confirms `mcp/server/transport_security.py` matches the documented `allowed_hosts`/`allowed_origins` exact-match-plus-`:*`-wildcard semantics). No package version drift risk this phase since no `pyproject.toml`/`uv.lock` changes are planned.

## Package Legitimacy Audit

No new packages are installed by this phase's code (`pyproject.toml`/`uv.lock` unchanged). One npm package is *documented* in the README for end users to run via `npx` (never installed into this repo):

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `mcp-remote` | npm | ~1.3 yrs (published 2025-03-17, per `time.created`) | ~401,258/wk | `github.com/geelen/mcp-remote` | OK | Approved for README documentation (not a repo dependency) |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

`mcp-remote` was verified via `npm view mcp-remote` (registry existence, version, repo URL, creation date) AND via `gsd-tools query package-legitimacy check --ecosystem npm mcp-remote` (verdict `OK`, no `postinstall` script, not deprecated) `[VERIFIED: npm registry]`. It is also the package named in Fly.io's own official `remote-mcp-servers`/`streaming-http` documentation and in third-party MCP client docs as the standard stdio-to-HTTP bridge, which is independent corroboration beyond registry existence alone.

## Architecture Patterns

### System Architecture Diagram

```text
Stranger's MCP client                     Fly.io edge (Fly Proxy)                  Container (one pinned machine)
----------------------                    -------------------------                ------------------------------
Claude Desktop / Claude Code    HTTPS      TLS termination                POST/GET   uvicorn (via FastMCP) bound
  (native remote MCP support)  -------->   Adds Fly-Client-IP header     -------->   0.0.0.0:8000
        OR                                 Forwards original Host                     |
npx mcp-remote <url>                       header verbatim                            v
  (stdio bridge for clients                (no port suffix on 443)          TransportSecurityMiddleware
   without native remote support)                                          .validate_request()
                                                                              - Content-Type check (POST)
                                                                              - Host header in allowed_hosts?
                                                                                (public hostname entry,
                                                                                 NEVER "0.0.0.0:*")
                                                                              - Origin header in allowed_origins?
                                                                                    |
                                                                          reject -> 421 / 400 / 403
                                                                          accept -> FastMCP tool dispatch
                                                                                    |
                                                                              get_account_evidence(domain)
                                                                                    |
                                                                          resolve_client_ip(request)
                                                                          -> Fly-Client-IP header only
                                                                          -> DemoLimiter.check_and_consume()
                                                                             (single machine = one global
                                                                              counter set, per D-03)
                                                                                    |
                                                                          allowed -> DemoClampedExa -> Exa API
                                                                          refused -> sanitized ValueError
                                                                             (HOST-05: no stack trace,
                                                                              no env name, no key fragment)
                                                                                    |
                                                                          EvidencePack JSON back to client
```

A reader tracing HOST-03's success criterion follows the top path left to right; a reader tracing HOST-06's allowlist requirement follows the Fly-edge-to-middleware hop in the middle; a reader tracing HOST-05 follows the bottom-right refusal branch.

### Recommended Project Structure (new files this phase)

```
Dockerfile              # multi-stage uv build; runs `python -m src.mcp_server --transport http`
fly.toml                # single-machine pin, auto_stop_machines="suspend", internal_port=8000
docs/
  DEPLOY.md             # operator runbook (D-15): fly launch dry-run notes, secrets, deploy, teardown
Makefile                # +deploy target wrapping `fly deploy`
src/config.py            # +mcp_public_hostname: str = ""
src/mcp_server/server.py # build_server: additive allowlist entries when mcp_public_hostname is set
src/mcp_server/__main__.py # +guard_non_loopback_requires_public_hostname (D-06)
tests/functional/test_mcp_http_transport.py  # +D-07 bind-vs-Host integration test
tests/unit/test_mcp_main_guard.py            # or a sibling file: +D-06 fail-fast unit tests
README.md                # +"Try it live" hook, +MCP section (client snippets, grounding contrast, BYOK)
CLAUDE.md                 # +mcp stack line, +MCP scope note, +file layout, +Makefile targets, +failure modes
```

### Pattern 1: Additive TransportSecuritySettings allowlist, parametrized by a NEW setting

**What:** `build_server`'s existing HTTP branch already builds a 3-entry `allowed_hosts`/`allowed_origins` list from loopback constants plus `settings.mcp_http_host`. This phase adds a 4th (and 5th) entry sourced from `settings.mcp_public_hostname`, only when it is set -- it does not replace or remove the existing entries, so local `make mcp-http` behavior is unaffected.

**When to use:** Any time a bind address (what the process listens on) and the externally-visible hostname (what a real client's Host header says) diverge -- true for every reverse-proxied or containerized deployment, not just Fly.

**Example:**
```python
# Source: src/mcp_server/server.py:276-295 (existing code, read at research time)
# and mcp/server/transport_security.py (installed package, read at research time)
allowed_hosts = [
    f"127.0.0.1:{settings.mcp_http_port}",
    f"localhost:{settings.mcp_http_port}",
    f"{settings.mcp_http_host}:{settings.mcp_http_port}",
]
allowed_origins = [
    f"http://127.0.0.1:{settings.mcp_http_port}",
    f"http://localhost:{settings.mcp_http_port}",
    f"http://{settings.mcp_http_host}:{settings.mcp_http_port}",
]
if settings.mcp_public_hostname:
    # Bare hostname: Fly's edge forwards the client's original Host header
    # verbatim, and HTTPS on the default port 443 omits the port suffix.
    allowed_hosts.append(settings.mcp_public_hostname)
    # Defensive second entry in case any client path includes an explicit
    # port (matches the mcp SDK's exact-string matching -- no port means
    # the bare-hostname entry above is required, not optional).
    allowed_hosts.append(f"{settings.mcp_public_hostname}:443")
    allowed_origins.append(f"https://{settings.mcp_public_hostname}")
```
Note: `TransportSecurityMiddleware._validate_host` does exact string matching against `allowed_hosts`, with a SEPARATE wildcard form (`"host:*"`, matched via `host.startswith(base_host + ":")`) that only helps when the incoming Host header DOES include a port. Since Fly forwards the client's Host header unmodified and a browser/MCP client hitting `https://poc-scraper-mcp.fly.dev` sends `Host: poc-scraper-mcp.fly.dev` (no port, per HTTP/1.1 semantics for default ports), the bare-hostname entry is the one that matters; the `:443` entry is defense-in-depth only `[CITED: fly.io/docs/networking/request-headers/, mcp package source]`.

### Pattern 2: Fail-fast startup guard, mirroring the shipped WR-03 pattern exactly

**What:** A small named function in `__main__.py`, called from `main()` right after tier/transport are known, that raises `SystemExit` with a clear message rather than silently serving with a broken (or accidentally-open) allowlist.

**When to use:** Exactly the D-06 condition: `transport == "http"` and the bind host is non-loopback and no public hostname is configured.

**Example:**
```python
# Source: src/mcp_server/__main__.py:24-44 (existing guard_full_tier_http_exposure,
# the pattern this new guard should copy verbatim in shape)
def guard_non_loopback_requires_public_hostname(settings: Settings, transport: str) -> None:
    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if (
        transport == "http"
        and settings.mcp_http_host not in loopback_hosts
        and not settings.mcp_public_hostname
    ):
        raise SystemExit(
            f"refusing to bind {settings.mcp_http_host!r} without MCP_PUBLIC_HOSTNAME set "
            "(a non-loopback bind with no public hostname means real clients' Host headers "
            "would 421 against the DNS-rebinding allowlist, or worse, get silently "
            "misconfigured). Set MCP_PUBLIC_HOSTNAME to the externally-visible hostname, "
            "or bind to 127.0.0.1/localhost for local development."
        )
```
Call site: same place `guard_full_tier_http_exposure` is called in `main()`, so both guards run before `build_server`/`asyncio.run`.

### Pattern 3: uv multi-stage Dockerfile

**What:** Build stage installs the locked dependency set via `uv sync --frozen`; runtime stage copies only the resulting `.venv` and source, keeping the final image lean and avoiding uv/pip in the runtime layer.

**When to use:** Any Fly.io deploy of a `uv`-managed Python project.

**Example:**
```dockerfile
# Source: docs.astral.sh/uv/guides/integration/docker/ (fetched at research time)
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY src ./src
COPY evals ./evals
COPY configs ./configs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.11-slim
COPY --from=builder /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    MCP_DEMO_MODE=1 \
    MCP_HTTP_HOST=0.0.0.0
EXPOSE 8000
CMD ["python", "-m", "src.mcp_server", "--transport", "http"]
```
`requires-python = ">=3.11"` (`pyproject.toml:6`) sets the floor; `python:3.11-slim` is the minimal matching base image. `MCP_PUBLIC_HOSTNAME` and `EXA_API_KEY` are deliberately NOT set here: the hostname is non-secret and belongs in `fly.toml`'s `[env]` block (committed, greppable); the Exa key is a Fly secret injected at runtime, never baked into the image (D-13).

### Pattern 4: fly.toml single-machine, suspend-on-idle

**What:** `internal_port` matches `mcp_http_port` (8000); `auto_stop_machines = "suspend"` plus `auto_start_machines = true` plus `min_machines_running = 0` gives the D-01 suspend-not-stop idle behavior at near-zero cost when idle.

**When to use:** This deployment, exactly as locked by D-01/D-02/D-03.

**Example:**
```toml
# Source: fly.io/docs/launch/autostop-autostart/, fly.io/docs/reference/configuration/
# (fetched at research time; exact schema keys confirmed, machine-count
# semantics inferred and flagged as an Open Question below)
app = "poc-scraper-mcp"
primary_region = "iad"  # pick one region; single-region is part of "one machine"

[build]

[env]
  MCP_PUBLIC_HOSTNAME = "poc-scraper-mcp.fly.dev"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```
**Machine-count pinning is NOT a single fly.toml key.** Fly.io controls the number of Machines via `fly scale count <n>` (imperative) and via how many machines a given region/`fly launch` invocation creates -- `fly.toml` itself has no `max_machines`/`machine_count` field `[CITED: fly.io/docs/launch/scale-count/]`. The operational discipline that satisfies D-03/roadmap-criterion-2 is: (1) deploy to exactly one `primary_region`, (2) run `fly scale count 1` once after the first deploy to make the pin explicit and durable across future `fly deploy` runs (`fly deploy` preserves whatever scale was last set via `fly scale count`), and (3) document in `docs/DEPLOY.md` that nobody should ever run `fly scale count >1` or add a second region. Verify with `fly status` / `fly scale show` after every deploy.

### Anti-Patterns to Avoid
- **Allowlisting the bind address instead of the public hostname:** the 12-REVIEW WR-03/12-SECURITY finding this phase exists to close. `0.0.0.0:{port}` (or any bind-derived entry) must never appear in `allowed_hosts`; only the hostname a real client's Host header carries belongs there.
- **Wildcard-allowlisting `allowed_hosts=["*"]` or disabling `enable_dns_rebinding_protection`** to "just make it work" against a confusing 421 during first deploy -- defeats HOST-06 entirely. If a 421 appears in testing, the fix is confirming the exact Host header value (log it once, temporarily, never in production), not loosening the allowlist.
- **Running `fly scale count 2+` "for reliability"** -- silently fragments `DemoLimiter`'s in-memory counters into per-machine limits, multiplying the effective daily cap without any code change noticing (Pitfall 2 from `.planning/research/SUMMARY.md`, now operationally relevant for the first time in Phase 13).
- **Baking `EXA_API_KEY` into the Dockerfile via `ARG`/`ENV`** -- persists in image layers/history even if later removed; always `fly secrets set EXA_API_KEY=...` at deploy time (D-13).
- **Leaving Fly's default smoke-check enabled against an MCP JSON-RPC endpoint** -- Fly's own `streaming-http` doc calls this out explicitly ("smoke checks... will confuse the server"); use `fly launch --smoke-checks=false` (or the deploy-time equivalent) and, if configuring an explicit `[[http_service.checks]]`, point it at a path/method the MCP endpoint actually answers (see Common Pitfalls below), not a bare GET `/`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DNS-rebinding / Host-header validation | A custom ASGI middleware checking `request.headers["host"]` | `mcp.server.transport_security.TransportSecuritySettings` (already wired into `build_server`) | The SDK ships exact-match plus wildcard-port semantics, a 421 response, Content-Type and Origin validation together -- reimplementing any slice of this risks missing the Origin/Content-Type checks that ship with it for free |
| Client IP resolution | A new "is this Fly?" header-sniffing helper for the deploy phase | `src/mcp_server/limits.py::resolve_client_ip` (unchanged, already audited T-11-01/T-11-11) | Already fail-closed, already tested against real ASGI headers over HTTP; nothing about deployment changes its contract |
| Secrets injection | `.env` file baked into the image, or a custom secrets-fetch script at container startup | `fly secrets set EXA_API_KEY=...` | Fly's native secrets mechanism; injected as env vars at runtime, never touches the image or `fly.toml`, satisfies "no secrets in the public repo" for free |
| Health checking | A custom `/healthz` endpoint registered as a new FastMCP tool/route | Fly's own health-check config pointed at a path the app already answers, OR no explicit `[[http_service.checks]]` block at all (Fly's TCP-level passive checking is often sufficient for a low-traffic demo) | Adding a bespoke health route means a fifth registered surface to keep in the tool/resource inventory and re-audit; simplest to avoid entirely unless a dry-run `fly launch` shows it's needed |
| Machine-count enforcement | A background job that calls the Fly Machines API to kill excess machines | `fly scale count 1` (imperative, one-time) plus a DEPLOY.md warning against ever running a higher count | This is an operational discipline problem, not a code problem; building automation for a single-operator demo app is over-engineering |

**Key insight:** every piece of "new" security-relevant machinery this phase needs (Host validation, client IP, sanitized errors) already exists and is already audited from Phases 10-12. The actual net-new code surface is two small, additive changes (a setting + an allowlist entry, a fail-fast guard) -- resist the temptation to generalize either into something bigger (e.g., a full multi-hostname allowlist config format) that the roadmap never asked for.

## Common Pitfalls

### Pitfall 1: `fly launch`'s default smoke check breaks against an MCP JSON-RPC endpoint
**What goes wrong:** `fly launch`/`fly deploy` issues an HTTP request to verify the app is alive before considering a deploy healthy. The MCP streamable-HTTP endpoint (`POST /mcp` with `Content-Type: application/json` and specific `Accept` headers) does not respond usefully to a generic smoke-check GET, so the deploy can appear to hang or fail even though the server is actually fine.
**Why it happens:** Fly's smoke-check assumes a conventional web app that answers GET requests with a 2xx; an MCP server's root path and `/mcp` GET (without the required headers/session) do not fit that shape.
**How to avoid:** Fly's own `streaming-http` MCP doc explicitly recommends `fly launch --ha=false --smoke-checks=false` for this exact scenario `[CITED: fly.io/docs/mcp/transports/streaming-http/]`. Carry `--smoke-checks=false` (or its `fly deploy` equivalent, confirm exact flag during the dry run) into `docs/DEPLOY.md`'s documented deploy command.
**Warning signs:** `fly deploy` reports a failed health check / rolls back a deploy that is otherwise serving traffic correctly when tested manually with `curl`/`mcp-remote`.

### Pitfall 2: `min_machines_running` and single-machine pinning are two different Fly concepts
**What goes wrong:** Assuming `min_machines_running = 1` in `fly.toml` is what pins the app to one machine (it isn't -- it's a floor on how many stay running when `auto_stop_machines` is active; the actual count of machines that exist is set via `fly scale count`, independent of this key).
**Why it happens:** `fly.toml`'s `[http_service]` block reads like a complete scaling policy, but machine count and autostop/autostart floors are genuinely separate Fly mechanisms.
**How to avoid:** After the first `fly deploy`, explicitly run `fly scale count 1` and verify with `fly status`; document this as an irreversible-until-changed step in `docs/DEPLOY.md`, not something `fly.toml` alone guarantees. With `auto_stop_machines = "suspend"` and D-02's cost goal, `min_machines_running = 0` is correct (allows full idle-suspend) -- do not set it to 1, which would keep the machine perpetually running/billing.
**Warning signs:** `fly status` shows more than one machine after any deploy; DemoLimiter counters appear to reset more often than expected, or the daily cap appears to allow more than 25 calls (evidence of counter fragmentation across machines).

### Pitfall 3: The public hostname's Host header has no port; a `:443`-only allowlist entry silently 421s every real request
**What goes wrong:** Adding only `f"{public_hostname}:443"` to `allowed_hosts` (reasoning "Fly serves HTTPS on 443, so that's the port") while the actual Host header a client sends is the bare hostname with no port suffix.
**Why it happens:** HTTP/1.1 clients omit the port from the Host header when it's the protocol's default port (443 for HTTPS); this is easy to forget when mentally modeling "the URL has a port."
**How to avoid:** Add the bare-hostname entry as the primary/required one; treat any `:443` variant as defensive-only, never the sole entry. The D-07 integration test (bind `0.0.0.0`, external Host header = the Fly hostname exactly as a real client would send it, i.e. no port) is the concrete regression guard for this.
**Warning signs:** 421 responses in the D-14 live manual check even though the allowlist "looks" configured.

### Pitfall 4: Docker layer caching invalidates on every source change if dependency install and source copy aren't separated
**What goes wrong:** A naive single-stage `COPY . .` followed by `uv sync` reinstalls the entire dependency set (including the `mcp` SDK and its transitives) on every code change, slowing iteration during the Wave 0 dry-run loop this phase explicitly calls for.
**Why it happens:** Docker's layer cache is invalidated by the first changed `COPY`; if `pyproject.toml`/`uv.lock` are copied together with source in one layer, any source edit busts the dependency-install cache too.
**How to avoid:** Pattern 3 above (copy `pyproject.toml`/`uv.lock` and run `uv sync --no-install-project` first, then copy source, then a final `uv sync`) is the standard uv-recommended layering `[CITED: docs.astral.sh/uv/guides/integration/docker/]`.
**Warning signs:** Every `docker build` during the dry-run iteration re-downloads/rebuilds the full dependency set even for a one-line Dockerfile CMD change.

### Pitfall 5: Forgetting `force_https = true` leaves an HTTP-plaintext path open at the Fly edge
**What goes wrong:** Without `force_https`, Fly will serve both `http://` and `https://` to the public hostname; a client (or attacker) hitting plain HTTP still reaches the app, and the `Origin`/`Host` validation logic doesn't care about scheme, only header values -- so this isn't a DNS-rebinding gap, but it is an unnecessary unencrypted path for what should be an HTTPS-only demo endpoint.
**Why it happens:** `force_https` defaults to Fly's own generated value depending on `fly launch` prompts; easy to leave unset when hand-authoring `fly.toml` from scratch.
**How to avoid:** Set `force_https = true` explicitly in the `[http_service]` block (Pattern 4 above already includes it).
**Warning signs:** `curl http://poc-scraper-mcp.fly.dev/mcp` succeeds instead of redirecting to HTTPS.

## Code Examples

### Claude Desktop config (remote URL, direct connection)
```json
// Source: mcp-remote npm README / Anthropic MCP client docs (verified via WebSearch,
// current syntax cross-checked against Fly.io's own remote-mcp-servers example)
{
  "mcpServers": {
    "poc-scraper": {
      "command": "npx",
      "args": ["mcp-remote", "https://poc-scraper-mcp.fly.dev/mcp"]
    }
  }
}
```
Note: Claude Desktop does not yet universally support native remote-HTTP MCP server config across all versions/platforms; `mcp-remote` is the portable bridge that works regardless. If/when the target client supports a native `"url"` field (some MCP clients already do, per Fly's own `remote-mcp-servers` example: `{"mcpServers": {"everything": {"url": "https://appname.fly.dev/mcp", "env": {}}}}`), document both forms in the README since D-08 names "Claude Desktop JSON" as one of three distinct snippets `[CITED: WebSearch aggregation of mcp-remote npm docs + fly.io/docs/blueprints/remote-mcp-servers/]`.

### Claude Code CLI (remote URL, native HTTP transport)
```bash
# Source: code.claude.com/docs/en/mcp (verified via WebSearch; "streamable-http" is
# accepted as an alias for "http" per current Claude Code docs)
claude mcp add --transport http poc-scraper https://poc-scraper-mcp.fly.dev/mcp
```

### `npx mcp-remote` (stdio-only clients bridging to the hosted URL)
```bash
# Source: npmjs.com/package/mcp-remote (verified: version 0.1.38, github.com/geelen/mcp-remote)
npx mcp-remote https://poc-scraper-mcp.fly.dev/mcp
```

### D-07 integration test shape (bind `0.0.0.0`, external Host header)
```python
# Source: existing test pattern in tests/functional/test_mcp_http_transport.py
# (test_configured_non_loopback_host_is_allowed, test_dns_rebinding_rejected_for_foreign_host),
# extended per D-07 / roadmap success criterion 2
async def test_public_hostname_allowed_but_bare_bind_address_is_not() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        mcp_http_host="0.0.0.0",
        mcp_public_hostname="poc-scraper-mcp.fly.dev",
    )
    app = build_server(lifespan=_lifespan_factory(FakeExa(...)), settings=settings)
    asgi_app = app.streamable_http_app()

    async with asgi_app.router.lifespan_context(asgi_app):
        # External Fly hostname in Host header: must be accepted.
        ok = await _post_initialize(asgi_app, base_url="https://poc-scraper-mcp.fly.dev")
        # The bind address itself as a Host header: must NEVER be accepted
        # (this is the literal WR-03/12-SECURITY observation this test closes).
        rejected = await _post_initialize(asgi_app, base_url="http://0.0.0.0:8000")

    assert ok.status_code != 421
    assert rejected.status_code == 421
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| MCP SSE transport for remote servers | Streamable HTTP transport | MCP spec revision, already adopted project-wide since Phase 11 | No action needed this phase; the project is already on the current transport |
| Threading `X-Forwarded-For` for client IP | `Fly-Client-IP` (Fly-specific, edge-set, not client-spoofable) | Already adopted in Phase 11 (T-11-01 hardening, commit `13036ab`) | No action needed this phase; carried forward unchanged |
| Bare `allowed_hosts` wildcard or disabled DNS-rebinding protection | Explicit per-deployment allowlist, `enable_dns_rebinding_protection=True` | `mcp>=1.23.0` per `.planning/research/SUMMARY.md` Pitfall 3 (CVE-2025-66414/66416) | Already the project's posture since Phase 11; this phase extends the allowlist, doesn't change the posture |

**Deprecated/outdated:** none newly identified this phase; the milestone's earlier research (Phase 9-12) already front-loaded the SDK-version and transport-security currency checks.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fly's edge forwards the client's original Host header verbatim (bare hostname, no port for default-port HTTPS) to the backend app, rather than substituting an internal address | Pattern 1, Pitfall 3 | If wrong, the allowlist entry composition needs a different form (e.g., always includes `:443`, or Fly injects a different header entirely) -- the D-07 integration test plus a real `fly launch` dry-run request will surface this immediately, low actual risk since it's cheaply falsifiable before the phase ships |
| A2 | `fly scale count 1` plus single-`primary_region` deploy is sufficient to satisfy "fly.toml pins exactly one machine" -- there is no dedicated `fly.toml` key that hard-caps machine count | Pattern 4 | If a `fly.toml`-native machine-count key exists that the WebFetch/WebSearch summaries missed, the plan should prefer it (declarative > imperative); worth a 5-minute check against `fly config validate` output during the Wave 0 dry run |
| A3 | Fly's default (unconfigured) health checking is TCP-level/passive and won't itself smoke-check the MCP endpoint the way `fly launch`'s interactive smoke-check does | Don't Hand-Roll (health checking row), Pitfall 1 | If wrong and an explicit `[[http_service.checks]]` block is required, the check needs to target a path the MCP app actually answers correctly (not a bare GET `/`) -- verify during the Wave 0 dry run before committing `fly.toml` |
| A4 | Claude Desktop's JSON config format for a fully-native remote-HTTP MCP server (`{"url": "..."}`) is not yet universally supported, so `mcp-remote` is the more portable snippet to lead with | Code Examples (Claude Desktop) | Low risk either way since D-08 only requires "a Claude Desktop JSON snippet" -- worth a quick current-version check at write time, not blocking for planning |

**If this table is empty:** N/A -- see entries above; all four are cheaply falsifiable during the roadmap-mandated `fly launch` dry run and do not block planning.

## Open Questions

1. **Exact Fly.io machine-count-pinning mechanism**
   - What we know: `fly scale count 1` is the documented imperative command; `fly.toml` has no dedicated machine-count key per the docs fetched this session.
   - What's unclear: whether a fresh `fly launch` for this app (single Dockerfile, single region, no explicit process groups) creates exactly one machine by default, or whether an explicit step is required even for the very first deploy.
   - Recommendation: the Wave 0 `fly launch` dry run (already mandated by the roadmap) should include running `fly status` immediately after, and `docs/DEPLOY.md` should document the exact confirmed command sequence, not a guessed one.

2. **Whether an explicit Fly health check is needed at all for a low-traffic single-machine demo**
   - What we know: Fly's `streaming-http` MCP doc recommends disabling the `fly launch` smoke-check; it does not say whether an ongoing `[[http_service.checks]]` block is recommended or harmful for this workload.
   - What's unclear: whether omitting `[[http_service.checks]]` entirely leaves Fly's proxy routing traffic to a suspended/crashed machine for longer than desired, versus a misconfigured check causing spurious restarts.
   - Recommendation: default to no explicit `[[http_service.checks]]` block for the first deploy (simplest, matches "no confirmed reference" caution); revisit only if the D-14 live check or early operation reveals a real problem.

3. **Exact wording Claude Desktop's current client-config UI/file expects** (native `url` field vs `mcp-remote` bridge, both, or a version-gated mix)
   - What we know: both forms exist in current ecosystem documentation (Anthropic's own docs, Fly's `remote-mcp-servers` blueprint).
   - What's unclear: which one is more broadly compatible as of the README-writing date, since MCP client support for native remote HTTP evolves quickly.
   - Recommendation: lead the README snippet with the `mcp-remote` bridge (works everywhere, matches D-08's explicit `npx mcp-remote` requirement) and mention the native-URL form as a one-line "if your client supports it directly" aside, rather than presenting two full snippets.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `fly` CLI (flyctl) | `fly launch`, `fly deploy`, `fly secrets`, `fly scale` (D-13, D-15, Wave 0 dry run) | Not checked this session (operator machine, not sandboxed dev environment) | — | None -- deploy work cannot proceed without it; planner should add an install-check as an early plan step, not assume it's present |
| Docker Engine | `fly deploy` local build path | Not checked this session | — | Fly's remote builder (`fly deploy --remote-only`) is a documented fallback if local Docker is unavailable, per general Fly.io deploy docs |
| `npm`/`npx` | End-user's `mcp-remote` bridge (not this repo's build) | Not this repo's concern to verify (runs on the connecting client's machine) | — | N/A -- documented as a client-side prerequisite in the README, not something this repo installs |
| `EXA_API_KEY` (as a Fly secret) | Hosted server's only live dependency (demo mode forces thin tier, no writer/judge/Browserbase needed) | Present locally per `.env` (not directly inspected this session per file-access restrictions); confirmed required by `Settings.mcp_tier()` | — | None -- `mcp_tier()` raises at startup if absent, both locally and in the container |

**Missing dependencies with no fallback:**
- `fly` CLI presence on the operator's machine (must be verified/installed before Wave 0's dry-run task).

**Missing dependencies with fallback:**
- Local Docker Engine (Fly's remote builder covers this if truly unavailable, though `docs/DEPLOY.md` should still recommend local Docker for the iterative dry-run loop, since remote builds are slower to iterate on).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ / pytest-asyncio (auto mode), already configured (`pyproject.toml`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, already present, no changes needed) |
| Quick run command | `uv run pytest tests/unit/test_mcp_main_guard.py tests/functional/test_mcp_http_transport.py -q` |
| Full suite command | `make test` (`uv run pytest -m "not smoke"`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HOST-03 | Live client retrieves cited evidence via hosted URL | manual-only (D-14) | N/A -- human paste-URL-and-call checkpoint | N/A by design |
| HOST-05 | Deliberately triggered failure never leaks stack trace / env name / key fragment | integration (offline) + manual (D-14) | `uv run pytest tests/integration/test_mcp_error_sanitization.py -x` (new file; existing sanitized-error tests already partially cover this in `tests/functional/test_mcp_server.py`) | Partial -- Wave 0 gap: one new cross-cutting banned-substring assertion recommended |
| HOST-06 (allowlist) | `0.0.0.0` bind + external Fly Host header accepted; bind-address-as-Host rejected | functional | `uv run pytest tests/functional/test_mcp_http_transport.py::test_public_hostname_allowed_but_bare_bind_address_is_not -x` | ❌ Wave 0 -- new test per D-07 |
| HOST-06 (fail-fast) | Non-loopback bind with no public hostname refuses to start | unit | `uv run pytest tests/unit/test_mcp_main_guard.py -k non_loopback -x` (or a new sibling file) | ❌ Wave 0 -- new test per D-06 |
| TEST-01 | Strict mypy stays clean across all touched files | static | `uv run mypy src evals` | Existing gate, re-run after every change this phase |

### Sampling Rate
- **Per task commit:** the quick run command above (guard + allowlist tests), plus `uv run mypy src/config.py src/mcp_server`.
- **Per wave merge:** `make test` (full offline suite, `-m "not smoke"`).
- **Phase gate:** full suite green, `make typecheck` clean, plus the D-14 manual live checkpoint recorded in the phase's verification artifact before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/functional/test_mcp_http_transport.py::test_public_hostname_allowed_but_bare_bind_address_is_not` -- covers HOST-06's roadmap-criterion-2 D-07 integration test
- [ ] A new unit test (in `tests/unit/test_mcp_main_guard.py` or a sibling) covering `guard_non_loopback_requires_public_hostname` -- covers HOST-06's D-06 fail-fast guard, following the exact `test_refuses_full_tier_over_http_without_opt_in` shape already in that file
- [ ] One cross-cutting HOST-05 test asserting a deliberately-triggered internal error's message contains none of: `"Traceback"`, any configured secret value substring, `"EXA_API_KEY"`/other env-var names -- extends the existing sanitized-error pattern rather than introducing a new one
- [ ] Framework install: none -- pytest/pytest-asyncio already fully configured, no new test infra needed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Explicitly out of scope this milestone (AR-12-05); rate limiting is the only gate, unchanged this phase |
| V3 Session Management | No | `stateless_http=True` already locked (Phase 11 D-locked); no session state to secure |
| V4 Access Control | No | Read-only public surface, no privilege tiers reachable over the public URL (full tier stays HTTP-gated behind `MCP_ALLOW_FULL_HTTP`, unchanged and not deployed publicly this phase) |
| V5 Input Validation | Yes (unchanged) | `Account` domain validator, already the sole validation boundary for `get_account_evidence`/`research_account_full`; this phase adds no new user-controlled input surface |
| V6 Cryptography | Yes (new this phase, deploy-only) | TLS termination is Fly's edge responsibility (`force_https = true` in `fly.toml`); the app itself never handles certificates or key material directly -- never hand-roll TLS in the container |
| V9 Communications | Yes (new this phase) | `force_https = true` plus documenting that Fly terminates TLS at the edge and forwards plain HTTP internally (standard for platform-managed TLS; internal traffic stays within Fly's private network) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DNS rebinding via a crafted Host header pointed at the app's real IP | Spoofing | `TransportSecuritySettings(allowed_hosts=[...])`, extended this phase to include the public hostname (never the bind address) -- already the project's Phase 11 posture, extended not reinvented |
| In-memory rate-limit counters silently fragmenting across multiple machines | Tampering / DoS (economic) | Single-machine `fly.toml` pin (`fly scale count 1`, single region), documented and manually verified via `fly status` -- this phase's core new mitigation |
| Secret leakage via committed `Dockerfile`/`fly.toml` or image layer history | Information Disclosure | `EXA_API_KEY` delivered exclusively via `fly secrets set`; Dockerfile/`fly.toml` contain zero secret values, verified by the same `scripts/check_public_discipline.py` pre-commit guard already covering the rest of the repo |
| Error payload leaking stack traces / env var names / key fragments over the wire | Information Disclosure | Already-shipped sanitized-`ValueError`-from-None pattern (Phase 10/11/12); this phase adds a deliberately-triggered-failure test plus the D-14 live manual check as the closing verification, per HOST-05 |
| Fly's smoke-check or health-check misfiring against the MCP-only endpoint, causing repeated restarts that reset in-memory counters more than the design accepts | Denial of Service (self-inflicted) | `--smoke-checks=false` on `fly launch`/`fly deploy`; no explicit `[[http_service.checks]]` unless the Wave 0 dry run shows one is actually needed (Pitfall 1) |

## Sources

### Primary (HIGH confidence)
- `pyproject.toml`, `src/config.py`, `src/mcp_server/server.py`, `src/mcp_server/__main__.py`, `src/mcp_server/wiring.py`, `src/mcp_server/limits.py`, `Makefile`, `README.md`, `CLAUDE.md` -- direct repo reads at research time
- `.venv/lib/python3.12/site-packages/mcp/server/transport_security.py` -- installed package source, direct read (confirms `TransportSecuritySettings` exact-match + `:*` wildcard-port semantics)
- `.planning/phases/11-rate-limits-streamable-http-transport/11-SECURITY.md`, `.planning/phases/12-full-tier-tool-resources-prompt/12-SECURITY.md` -- prior-phase security audits with grep-verified evidence
- `docs/superpowers/specs/2026-07-15-mcp-server-design.md`, `.planning/research/SUMMARY.md` -- milestone design authority and research
- `gsd-tools query package-legitimacy check --ecosystem npm mcp-remote` -- verdict OK, evidenced signals (downloads, repo, no postinstall)
- `npm view mcp-remote` -- direct registry query (version 0.1.38, repo, creation date)

### Secondary (MEDIUM confidence)
- `fly.io/docs/mcp/transports/streaming-http/` -- official Fly.io MCP deployment doc (Node.js-oriented, but explicit on `--smoke-checks=false` and the `/mcp` URL/client-config shape) `[CITED]`
- `fly.io/docs/blueprints/remote-mcp-servers/` -- official Fly.io remote MCP blueprint (single-tenant vs multi-tenant patterns, `fly-replay`) `[CITED]`
- `fly.io/docs/reference/configuration/`, `fly.io/docs/launch/autostop-autostart/`, `fly.io/docs/launch/scale-count/` -- official `fly.toml` schema and scaling docs `[CITED]`
- `fly.io/docs/networking/request-headers/` -- official header-forwarding doc (`Fly-Client-IP`, `X-Forwarded-*`; Host-header-forwarding behavior partially confirmed, flagged as A1 in Assumptions Log) `[CITED]`
- `docs.astral.sh/uv/guides/integration/docker/` -- official uv Docker integration guide `[CITED]`
- `code.claude.com/docs/en/mcp` -- Claude Code CLI MCP docs (`claude mcp add --transport http` syntax) `[CITED, via WebSearch aggregation]`

### Tertiary (LOW confidence, directional only)
- WebSearch aggregation summaries for `mcp-remote`/Claude Desktop JSON config shape (community blog posts, Medium articles, Dev.to) -- corroborate but are not the primary source; the npm registry data and Fly's own blueprint example are the load-bearing citations
- Community forum threads on Fly.io machine-count/health-check behavior (`community.fly.io`) -- directional only, not verified against a real deploy of this specific app; hence Open Questions 1-2 and Assumptions A2-A3

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new Python dependencies; existing `mcp` pin already audited twice (Phase 10, Phase 11) with zero drift this phase
- Architecture: MEDIUM-HIGH -- the code-level changes (setting, allowlist, fail-fast guard) are HIGH confidence (verified against installed package source and existing shipped patterns); the Fly.io deploy mechanics are MEDIUM per the roadmap's own explicit "no confirmed reference" flag, mitigated by the mandated Wave 0 dry run
- Pitfalls: MEDIUM -- security/transport pitfalls (allowlist composition, single-machine pinning importance) are HIGH confidence, cross-verified against installed source and prior audits; Fly-specific operational pitfalls (smoke checks, health checks) are MEDIUM, sourced from Fly's own docs but not yet verified against a real deploy of this app

**Research date:** 2026-07-17
**Valid until:** 14 days for the Fly.io-specific mechanics (fast-moving platform, and this phase's own roadmap note flags it as unconfirmed); 30 days for the MCP SDK/code-pattern findings (already-locked, slow-moving)
