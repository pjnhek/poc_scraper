---
title: poc-scraper-mcp
emoji: 🔍
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
license: mit
---

# poc-scraper-mcp (demo)

Hosted, demo-mode-only MCP endpoint for `poc_scraper`, a grounded account-research
prototype. Every claim this pipeline surfaces traces to a numbered citation.

- Source and full README: https://github.com/pjnhek/poc_scraper
- MCP endpoint: `/mcp` on this Space's URL
- Demo mode only: thin tier, rate-limited, no Browserbase fallback

This Space is a deploy target built from this repository's `Dockerfile`. It is not
a standalone project; see the GitHub repo above for the pipeline, evals, and docs.
