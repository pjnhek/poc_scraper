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
