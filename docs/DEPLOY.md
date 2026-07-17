# Deploying the hosted MCP demo

This runbook covers deploying `poc_scraper`'s MCP server as the public,
demo-mode-only hosted endpoint (HOST-03, HOST-06). The primary target is
Hugging Face Spaces (free, no payment method). Fly.io is kept as a documented
alternative for operators who already have Fly billing set up.

**Deploy-target change (13-04):** the original plan targeted Fly.io. During
this phase's live deploy, `fly apps create` failed with "We need your payment
information": Fly.io now requires a card on file even for its otherwise-free
allowances. The operator chose Hugging Face Spaces instead, which has no card
requirement for a free CPU-basic Docker Space. The Fly artifacts below
(`Dockerfile` is shared with HF, `fly.toml`) stayed committed as a validated,
documented alternative; they were not carried through a live deploy in this
milestone.

## MCP_PUBLIC_HOSTNAME (applies to both targets)

`MCP_PUBLIC_HOSTNAME` is a `Settings` field (`src/config.py`) distinct from
`MCP_HTTP_HOST`. `MCP_HTTP_HOST` is a pure bind address (for example
`0.0.0.0` in the container); `MCP_PUBLIC_HOSTNAME` is the externally-visible
hostname a real client's `Host` header carries (for example
`<owner>-poc-scraper-mcp.hf.space` or `poc-scraper-mcp.fly.dev`).

- The server refuses to start when serving HTTP on a non-loopback bind (such
  as `0.0.0.0`) with no `MCP_PUBLIC_HOSTNAME` configured. This fail-fast guard
  (`guard_non_loopback_requires_public_hostname` in
  `src/mcp_server/__main__.py`) matches the project's existing fail-loud
  precedent: a misconfigured container dies visibly at startup instead of
  serving with a wrong or empty allowlist.
- When set, `MCP_PUBLIC_HOSTNAME` sources an additional entry in
  `build_server`'s `TransportSecuritySettings` allowlist so a real client's
  `Host` header is accepted without allowlisting the bind address itself.
- Local development is unaffected: `make mcp-http` and `make mcp-demo` default
  to a loopback bind (`127.0.0.1`), which the guard and the existing localhost
  allowlist handle unchanged.
- This variable could not be added to `.env.example` in plan 13-01 (file
  outside that session's file-access permissions), so it is documented here
  instead.

## Hugging Face Spaces (primary)

### Prerequisites

1. Install the HF CLI:
   ```
   uv tool install "huggingface_hub[cli]"
   ```
2. Create a free account at https://huggingface.co/join if you do not have
   one.
3. Authenticate:
   ```
   hf auth login
   ```
   Paste a User Access Token (write scope) from
   https://huggingface.co/settings/tokens.

### Create the Space

1. Create a new Docker Space. The web UI at https://huggingface.co/new-space
   (SDK: Docker, visibility: Public) is the most reliable path. The CLI
   equivalent, confirmed against the installed `hf` binary's `--help`:
   ```
   hf repo create <owner>/poc-scraper-mcp --type space --sdk docker --public
   ```
   If `poc-scraper-mcp` is taken, pick the closest available variant and keep
   this runbook's example commands, the README, and `MCP_PUBLIC_HOSTNAME`
   consistent with the name you actually got (D-04 app-identity intent).
2. Note the exact `<owner>/<space-name>` slug; it is the argument to every
   command below.

### Configure secrets and variables

In the Space's Settings page (`https://huggingface.co/spaces/<owner>/<space-name>/settings`),
under "Variables and secrets":

1. Add a **Secret** named `EXA_API_KEY` with your Exa key (from your local
   `.env` or the exa.ai dashboard). `Settings.mcp_tier` raises at startup
   without it, so the container crash-loops if this is missing.
2. Add a **Variable** (non-secret) named `MCP_PUBLIC_HOSTNAME`. Its value is
   the Space's direct URL hostname, shown at the top of the Space page once
   the first build completes (do not assume the `<owner>-<space-name>.hf.space`
   naming convention holds for every namespace; confirm the real hostname).

Both Secrets and Variables are injected into the container as environment
variables, the same mechanism `fly secrets set` uses for Fly.

### Push the build context

```
uv run python -m scripts.push_hf_space <owner>/<space-name>
```

`scripts/push_hf_space.py` copies an explicit allowlist, exactly what the
Dockerfile's `COPY` instructions need (`Dockerfile`, `pyproject.toml`,
`uv.lock`, `.dockerignore`, `src/`, `evals/`, `configs/`), plus the Space card
at `deploy/hf-space/README.md`, into a scratch directory and uploads it with
`hf upload` (a single-commit upload, not `git push`). Nothing else, no
`.env`, `credentials.json`, `.planning/`, `tests/`, or this project's own
top-level `README.md`, ever leaves the working tree. This mirrors the
`.dockerignore` discipline the local Docker build already applies, made
explicit because the Space repo is pushed as its own tree rather than
filtered by `docker build`.

### app_port and the container

Docker Spaces route external traffic to the port declared as `app_port` in
the Space card's YAML front matter (`deploy/hf-space/README.md`). It is set
to `8000` here, matching the Dockerfile's `EXPOSE 8000` and the server's
default `MCP_HTTP_PORT`. `MCP_HTTP_HOST` is already `0.0.0.0` in the
Dockerfile's `ENV`. If the internal port ever changes, update `app_port` in
`deploy/hf-space/README.md` to match.

### Single-instance and idle behavior (mapping D-01/D-03)

Free CPU-basic Spaces run exactly one container replica; there is no scale
knob to misconfigure, so the `DemoLimiter`'s in-memory counters are globally
correct by construction. This satisfies the same single-machine intent as
Fly's `fly scale count 1` pin, without a separate pinning step.

Free Spaces sleep after a period of inactivity (Hugging Face documents this
as roughly 48 hours for free-tier Spaces, subject to change) and cold-start
on the next request. The in-memory `DemoLimiter` counters reset on that
restart, the same accepted tradeoff as Fly's suspend/restart behavior (see
"Idle behavior and cost" in the Fly appendix). Expect the first request after
a sleep period to take noticeably longer while the container restarts;
subsequent requests return at normal latency.

### Verifying the deploy

Replace `<space-hostname>` with the confirmed hostname from the Space page.

1. Confirm the MCP endpoint responds to a JSON-RPC initialize call:
   ```
   curl -sS -X POST https://<space-hostname>/mcp \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"0.1"}}}'
   ```
   Expect a non-421, non-5xx response. A 421 means the `Host` header did not
   match the `TransportSecuritySettings` allowlist; confirm the `Variable`
   `MCP_PUBLIC_HOSTNAME` matches the real Space hostname exactly.
2. Check the Space's build/container logs (Space page, "Logs" tab) for the
   startup lines: the resolved tier line must say `thin`, and the demo-limits
   line must show the 5/25/5 defaults.

### Cost

Free CPU-basic Spaces cost $0/month with no payment method required. This is
the reason the hosted target switched from Fly.io, which now requires a card
on file even for otherwise-free usage, to Hugging Face Spaces.

### Teardown

Delete the Space from its Settings page, or:
```
hf repo delete <owner>/<space-name> --type space
```

## Appendix: Fly.io (alternative)

Fly.io's artifacts (`Dockerfile` is shared with the HF path above,
`fly.toml`) stay committed as a documented alternative for operators who
already have Fly billing configured. `fly apps create` now requires a
payment method on the account before it will create an app, even though the
resulting usage can stay within Fly's free allowances; this blocked the live
deploy for this milestone's operator. The commands below were validated
through the plan 13-02/13-03 dry run and app-creation attempt but were not
carried through a live deploy.

### Dry run findings

Before authoring the Dockerfile and `fly.toml`, the roadmap required an early
`fly launch` dry run to falsify or confirm the deploy-mechanics assumptions in
`13-RESEARCH.md` (Assumptions A1-A3, Open Questions 1-2, Pitfalls 1-2). This
section records what that dry run found in this execution environment.

**flyctl install:** `flyctl` was not present, so it was installed via
`brew install flyctl`. `fly version` reports:

```
fly v0.4.71 darwin/arm64 Commit: 56c828f79ca41a154d5983e22b90725da37e44f5 BuildDate: 2026-07-14T14:30:51Z
```

**Authentication (plan 13-02 dry run):** `fly auth whoami` returned
`Error: no access token available. Please login with 'flyctl auth login'`.
No Fly.io account or API token was available in that execution environment.
Per the plan's documented fallback for this exact case, the run degraded
gracefully: the Dockerfile and `fly.toml` are authored directly from the
`13-PATTERNS.md`/`13-RESEARCH.md` excerpts rather than from a generated
`fly launch` config.

**Authentication and app creation (plan 13-04):** `fly auth login` succeeded
in a later session (an authenticated account was available). `fly apps
create poc-scraper-mcp` then failed with "We need your payment information".
No Fly app exists as a result; this is the deviation documented at the top of
this file.

**Observations, confirmed or deferred:**

1. **App name availability (`poc-scraper-mcp`).** Not confirmed; blocked by
   the payment-method requirement above.
2. **Generated `fly.toml` content.** Not confirmed, no authenticated
   `fly launch` could complete. `fly.toml` in this repo is hand-authored from
   `13-RESEARCH.md` Pattern 4 instead of diffed against a generated file.
3. **Smoke-checks flag spelling.** CONFIRMED without authentication: both
   `fly launch --help` and `fly deploy --help` list an identical boolean
   flag:
   ```
   --smoke-checks   Perform smoke checks during deployment (default true)
   ```
   `make deploy-fly` and this appendix use `fly deploy --smoke-checks=false`,
   confirming RESEARCH Pitfall 1 (the MCP JSON-RPC endpoint does not answer a
   generic smoke check GET usefully).
4. **Machine-count key in generated `fly.toml`.** Not directly confirmed.
   Indirectly corroborated: `fly.toml`'s schema, per `13-RESEARCH.md`'s
   citation of Fly's own configuration reference, has no dedicated
   machine-count key. This repo's `fly.toml` deliberately omits any
   machine-count field; the one-machine pin is `fly scale count 1`, run once
   after the first authenticated deploy (see "Single-machine pin" below).
5. **Machine count for a freshly launched, undeployed app (`fly status`).**
   Not confirmed; blocked by the payment-method requirement above.

**Summary:** 1 observation (the smoke-checks flag) was confirmed directly
against the installed `flyctl` binary without requiring authentication. App
creation itself is blocked on this account by Fly's payment-method
requirement, so this appendix's remaining steps are documented but unverified
by a live deploy in this milestone.

### Prerequisites

1. Install `flyctl`:
   ```
   brew install flyctl
   ```
2. Authenticate:
   ```
   fly auth login
   ```
3. Add a payment method to the Fly.io account (required by Fly as of this
   writing, even for usage that stays within free allowances):
   https://fly.io/dashboard/personal/billing
4. Docker Engine is recommended for local builds and for the iterative
   dry-run loop (faster than a remote build on every change). If Docker is
   unavailable, `fly deploy` falls back to Fly's remote builder:
   ```
   fly deploy --remote-only
   ```

### First deploy

```
fly launch --no-deploy
```
Reconcile the generated app name and `MCP_PUBLIC_HOSTNAME` in `fly.toml` if
the name differs from `poc-scraper-mcp`.

1. Set the only secret this server needs. `EXA_API_KEY` is never baked into
   the image or `fly.toml`; it is delivered as a Fly secret at runtime:
   ```
   fly secrets set EXA_API_KEY=<your-exa-key>
   ```
2. Deploy:
   ```
   make deploy-fly
   ```

### Single-machine pin

The in-memory `DemoLimiter` rate-limit counters (per-IP hourly window,
UTC-day global cap) are only globally correct if exactly one machine process
holds them. `fly.toml` has no dedicated machine-count key, so this pin is an
operational step, not a config value:

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

**Warning:** never run `fly scale count` with a value higher than 1, and
never add a second region. Either action silently fragments the in-memory
rate-limit counters into per-machine limits, multiplying the effective daily
cap with no code-level warning. This must never be done.

### Idle behavior and cost

`fly.toml` sets `auto_stop_machines = "suspend"` (not `"stop"`, not
always-on). Auto-suspend freezes the VM's memory on idle and restores it on
wake, so the in-memory `DemoLimiter` counters survive quiet periods. Counters
reset only on deploys or crashes, an accepted tradeoff for a demo-mode
endpoint.

With `shared-cpu-1x`, 256MB, one machine, and suspend-on-idle, expected
realistic spend is under 1-2 USD per month, with a ceiling of about 5 USD per
month even under sustained traffic. This estimate assumes a payment method is
already on file; it does not account for the account-level requirement that
blocked this milestone's live deploy.

### Verifying the deploy

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
   `TransportSecuritySettings` allowlist; see "MCP_PUBLIC_HOSTNAME" above).

   This exact request shape was validated locally in plan 13-02 against a
   container built from this repo's Dockerfile: without `MCP_PUBLIC_HOSTNAME`
   set, the container refuses to start; with it set and a matching `Host`
   header, the request returns a 200 with the server's `initialize`
   response, and a request carrying the bind address as `Host` still gets a
   421.

### Teardown

```
fly apps destroy <app-name>
```
