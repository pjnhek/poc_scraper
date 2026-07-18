---
quick_id: 260718-ev4
slug: mcp-usage-docs-redeploy
description: Document how to use the hosted MCP server, and redeploy so the live endpoint matches the docs
completed: 2026-07-18
status: complete
commits:
  - af4efc0 docs(mcp) README tools/resources table and worked example
  - 605691f docs(deploy) landing page First call section
---

# Quick Task 260718-ev4: Summary

## What was wrong

The hosted demo had drifted a full milestone behind the repo, and the drift was invisible from the README.

`/opt/poc-scraper/repo` on the Oracle host sat at `3c5c846` (end of v1.1) while `origin/main` was at `7f960df` (end of v1.2). Confirmed by probing the live endpoint rather than by reading the deploy log:

- `tools/list` returned only `get_account_evidence`; `score_account` did not exist.
- `get_account_evidence` inputSchema had only `domain`; `news_days` was absent.
- `prompts/list` returned the pre-v1.2 `research_account` description.
- `/` still served "Evidence retrieval only ... The full pipeline (ICP scoring, personas, citation-checked outreach) is BYOK".

Meanwhile `README.md:24` told visitors that "deterministic ICP scoring via `score_account` runs on top of it unrationed". Anyone who followed the connect instructions and reached for that tool would not have found it. The whole of v1.2 was shipped to git and never to the box.

Separately, neither the README nor the landing page documented usage. Connecting was covered four ways on both surfaces; what to do after connecting was one grey sentence on the landing page and nothing but architecture prose in the README.

## What was done

**Redeploy.** `make deploy-oracle ORACLE_HOST=170.9.7.144.sslip.io SSH_KEY=~/.ssh/poc_scraper_oracle`. The host pulled `origin/main` to `7f960df`, rebuilt the image (32.5s, the pre-existing 2GB swapfile covered the 1GB box), and replaced the container and Caddy config.

**Captured real output.** Rather than invent a sample response, called `get_account_evidence("notion.so")` and then scored the four axes against the rubric from that evidence. Retrieval returned `ok` with 13 numbered justifications. The resulting `score_account` call returned `total: 4.2`, `verdict: strong`. Both payloads went into the docs as-is, trimmed for length only.

**Landing page** (`deploy/oracle/setup.sh`): added a "First call" section leading with the `research_account` slash command, a three-item inventory of the tools and the two readable resources, and a "What comes back" section showing the trimmed evidence and score payloads. Added `ul`/`li` styling to the existing inline CSS.

**README** (`README.md`): added a six-row tools/resources table covering every live surface across both tiers, and a worked example running the same real evidence through `score_account` with the by-hand arithmetic check.

## Verification

| Check | Result |
|---|---|
| Live `tools/list` | Returns `get_account_evidence` and `score_account` |
| Live `get_account_evidence` schema | Contains `News Days` |
| Live `prompts/list` | Six-step description ("end to end") present |
| Live `score_account` call | `total: 4.2`, `verdict: strong`, identical to local |
| `bash -n deploy/oracle/setup.sh` | Passes |
| Landing page heredoc rendered locally | 5586 bytes, hostname substituted 5x, no unexpanded vars, JSON intact |
| `tests/unit/test_deploy_caddy_config.py` | 2 passed |
| `make test` | 558 passed, 3 deselected |
| `make verify-public-repo` | 0 hits tracked, 0 hits in history |
| Em-dashes / emojis in changed files | None |

## Notes for next time

The gap between "milestone complete" and "milestone live" is not currently checked by anything. `make deploy-oracle` is a manual step with no reminder at milestone close, and nothing compares the deployed commit against `origin/main`. A cheap guard would be a milestone-close checklist item that probes `tools/list` on the public endpoint and diffs it against the local tool inventory. Worth considering when the v1.3 scope is set, since the public URL is the artifact most readers will actually touch.

## Out of scope, still open

- `tmp/` is not gitignored and currently holds a personal PNG.
- `AGENTS.md` is untracked; needs a decision on whether it is committed.
- `NEXT_MILESTONE_SALES_WORKFLOW.md` is an untracked draft brief for v1.3.
