# Deploying the hosted MCP demo

This runbook covers deploying `poc_scraper`'s MCP server to Fly.io as the public,
demo-mode-only hosted endpoint (HOST-03, HOST-06).

## Dry run findings

Before authoring the Dockerfile and `fly.toml`, the roadmap requires an early `fly launch`
dry run to falsify or confirm the deploy-mechanics assumptions in `13-RESEARCH.md`
(Assumptions A1-A3, Open Questions 1-2, Pitfalls 1-2). This section records what that dry
run found in this execution environment.

**flyctl install:** `flyctl` was not present, so it was installed via `brew install flyctl`.
`fly version` reports:

```
fly v0.4.71 darwin/arm64 Commit: 56c828f79ca41a154d5983e22b90725da37e44f5 BuildDate: 2026-07-14T14:30:51Z
```

**Authentication:** `fly auth whoami` returned `Error: no access token available. Please
login with 'flyctl auth login'`. No Fly.io account or API token was available in this
execution environment, and `fly auth login` requires an interactive browser or
email/password flow that this automated session cannot complete. Per the plan's documented
fallback for this exact case (no account, CLI install itself succeeded), the run degraded
gracefully: Task 2's Dockerfile and `fly.toml` are authored directly from the
`13-PATTERNS.md`/`13-RESEARCH.md` excerpts rather than from a generated `fly launch` config.

**Observations, confirmed or deferred:**

1. **App name availability (`poc-scraper-mcp`).** Not confirmed, requires an authenticated
   `fly launch` or `fly apps list`/`fly apps create` call. The name `poc-scraper-mcp` is used
   provisionally throughout the Dockerfile, `fly.toml`, and this runbook. Name confirmation
   (and the fallback-name substitution if taken) moves to plan 13-04's deploy preflight,
   which runs with a real, authenticated Fly.io account.
2. **Generated `fly.toml` content.** Not confirmed, no authenticated `fly launch` could run.
   `fly.toml` in this repo is hand-authored from `13-RESEARCH.md` Pattern 4 instead of
   diffed against a generated file. Plan 13-04's deploy preflight should sanity-check this
   file against a real `fly launch --no-deploy` output before the first live deploy.
3. **Smoke-checks flag spelling.** CONFIRMED without authentication: both `fly launch --help`
   and `fly deploy --help` list an identical boolean flag:
   ```
   --smoke-checks   Perform smoke checks during deployment (default true)
   ```
   This flag is available on both subcommands (not `fly launch`-only as `13-RESEARCH.md`
   speculated). `make deploy` and this runbook use `fly deploy --smoke-checks=false`,
   confirming RESEARCH Pitfall 1 (the MCP JSON-RPC endpoint does not answer a generic smoke
   check GET usefully).
4. **Machine-count key in generated `fly.toml`.** Not directly confirmed (no generated file
   to inspect in this session). Indirectly corroborated: `fly.toml`'s schema, per
   `13-RESEARCH.md`'s citation of Fly's own configuration reference, has no dedicated
   machine-count key. This repo's `fly.toml` deliberately omits any machine-count field;
   the one-machine pin is `fly scale count 1`, run once after the first authenticated
   deploy (see "Single-machine pin" below).
5. **Machine count for a freshly launched, undeployed app (`fly status`).** Not confirmed,
   requires an authenticated launch. Plan 13-04's deploy preflight should run `fly status`
   immediately after the first `fly launch`/`fly deploy` and confirm exactly one machine
   before proceeding, per Open Question 1 in `13-RESEARCH.md`.

**Summary:** 1 of 5 observations (the smoke-checks flag) was confirmed directly against the
installed `flyctl` binary without requiring authentication. The remaining four require an
authenticated Fly.io account and are deferred to plan 13-04's deploy preflight, which the
`13-CONTEXT.md` roadmap already scopes as the phase that performs the live deploy.

## Prerequisites

1. Install `flyctl`:
   ```
   brew install flyctl
   ```
2. Authenticate:
   ```
   fly auth login
   ```
3. Docker Engine is recommended for local builds and for the iterative dry-run loop
   (faster than a remote build on every change). If Docker is unavailable, `fly deploy`
   falls back to Fly's remote builder:
   ```
   fly deploy --remote-only
   ```

## First deploy

The app should already exist from the `fly launch` dry run above (or from a fresh
`fly launch` if the dry run could not run in your environment, per the findings section).

1. Set the only secret this server needs. `EXA_API_KEY` is never baked into the image or
   `fly.toml`; it is delivered as a Fly secret at runtime:
   ```
   fly secrets set EXA_API_KEY=<your-exa-key>
   ```
2. Deploy:
   ```
   make deploy
   ```

## Single-machine pin

The in-memory `DemoLimiter` rate-limit counters (per-IP hourly window, UTC-day global cap)
are only globally correct if exactly one machine process holds them. `fly.toml` has no
dedicated machine-count key, so this pin is an operational step, not a config value:

1. After the first deploy, run:
   ```
   fly scale count 1
   ```
2. Verify with both:
   ```
   fly status
   fly scale show
   ```
   Confirm exactly one machine exists in exactly one region.

**Warning:** never run `fly scale count` with a value higher than 1, and never add a second
region. Either action silently fragments the in-memory rate-limit counters into per-machine
limits, multiplying the effective daily cap with no code-level warning. This must never be
done.

## Idle behavior and cost

`fly.toml` sets `auto_stop_machines = "suspend"` (not `"stop"`, not always-on).
Auto-suspend freezes the VM's memory on idle and restores it on wake, so the in-memory
`DemoLimiter` counters survive quiet periods. Counters reset only on deploys or crashes,
an accepted tradeoff for a demo-mode endpoint.

With `shared-cpu-1x`, 256MB, one machine, and suspend-on-idle, expected realistic spend is
under 1-2 USD per month, with a ceiling of about 5 USD per month even under sustained
traffic.

## Verifying the deploy

Replace `<app-hostname>` with the confirmed app hostname (for example
`poc-scraper-mcp.fly.dev`).

1. Confirm HTTPS is enforced (`force_https = true`):
   ```
   curl -sI http://<app-hostname>/mcp
   ```
   Expect a redirect to `https://`.
2. Confirm the MCP endpoint responds to a JSON-RPC initialize call:
   ```
   curl -sS -X POST https://<app-hostname>/mcp \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"0.1"}}}'
   ```
   Expect a non-421 response (a 421 means the `Host` header did not match the
   `TransportSecuritySettings` allowlist; see `MCP_PUBLIC_HOSTNAME` below).

   This exact request shape was validated locally in plan 13-02 against a container built
   from this repo's Dockerfile: without `MCP_PUBLIC_HOSTNAME` set, the container refuses to
   start; with it set and a matching `Host` header, the request returns a 200 with the
   server's `initialize` response, and a request carrying the bind address as `Host`
   still gets a 421.

## Teardown

```
fly apps destroy <app-name>
```

## MCP_PUBLIC_HOSTNAME

`MCP_PUBLIC_HOSTNAME` is a `Settings` field (`src/config.py`) distinct from
`MCP_HTTP_HOST`. `MCP_HTTP_HOST` is a pure bind address (for example `0.0.0.0` in the
container); `MCP_PUBLIC_HOSTNAME` is the externally-visible hostname a real client's `Host`
header carries (for example `poc-scraper-mcp.fly.dev`).

- In production, `fly.toml`'s `[env]` block supplies `MCP_PUBLIC_HOSTNAME`. It is
  non-secret and safe to commit; it sources an additional entry in `build_server`'s
  `TransportSecuritySettings` allowlist so a real client's `Host` header is accepted
  without allowlisting the bind address itself.
- The server refuses to start when serving HTTP on a non-loopback bind (such as
  `0.0.0.0`) with no `MCP_PUBLIC_HOSTNAME` configured. This fail-fast guard
  (`guard_non_loopback_requires_public_hostname` in `src/mcp_server/__main__.py`) matches
  the project's existing fail-loud precedent: a misconfigured container dies visibly at
  startup instead of serving with a wrong or empty allowlist.
- Local development is unaffected: `make mcp-http` and `make mcp-demo` default to a
  loopback bind (`127.0.0.1`), which the guard and the existing localhost allowlist handle
  unchanged.
- This variable could not be added to `.env.example` in plan 13-01 (file outside that
  session's file-access permissions), so it is documented here instead.
