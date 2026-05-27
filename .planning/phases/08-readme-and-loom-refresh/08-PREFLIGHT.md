# Phase 8 Pre-Flight: Demo Bundle Coverage Check

**Run date:** 2026-05-27
**Source data:** `inputs/accounts.csv` (10 real prospect domains)
**Command attempted:** `DEMO_BUNDLE=fixtures/demo-bundle uv run python -m src.pipeline` (alias `make run-demo`)
**Outcome:** Run failed at the first account with `ReplayMissError`.

## Result Summary

The Phase 5 demo bundle is a minimal directory shell, not a populated fixture set. `fixtures/demo-bundle/` contains only `README.md` plus three empty subdirectories (`exa/`, `browserbase/`, `llm/`). No fixture JSON files have been recorded yet, so the replay path raises `ReplayMissError` on the very first Exa `search_about` call:

```
src.clients.replay.ReplayMissError: replay fixture missing for about: {"domain": "mercury.com", "method": "about", "num_results": 5} (expected at fixtures/demo-bundle/exa/about_13c41bc20ae221e4.json)
```

The `fixtures/demo-bundle/README.md` (committed in Phase 5) explicitly documents this state: "Phase 5 ships the replay/record machinery and a minimal directory shell. It does NOT ship the real demo bundle. Phase 8 records the real bundle (10 prospect domains, 3 external services, roughly 100-200 JSON files) against the stabilized pipeline output."

Recording that bundle was deferred to Phase 8 by design, but it is also out of scope for the Phase 8 README and Loom refresh per the 08-CONTEXT.md Out of Scope section. The pre-flight's job is to surface that gap so Plan 02 can plan around it; this document is that record.

## AccountStatus State Coverage

| AccountStatus state | Produced by the demo bundle today? | Plan 02 capture source |
|---------------------|-------------------------------------|------------------------|
| `clean`             | No, bundle is empty                 | Real `make run` against `inputs/accounts.csv` |
| `low_groundedness`  | No, bundle is empty                 | Real `make run` against `inputs/accounts.csv` |
| `hook_suppressed`   | No, bundle is empty                 | Real `make run` against `inputs/accounts.csv` |
| `judge_failed`      | No, bundle is empty                 | Real `make run` against `inputs/accounts.csv` |

Every state must come from real runs. The D-06 cached fallback is not viable in Phase 8 because the cache does not exist yet.

## Implications for Plan 02

1. Plan 02 captures all four AccountStatus state PNGs (`clean`, `low_groundedness`, `hook_suppressed`, `judge_failed`) plus `hero.png` from real `make run` outputs against `inputs/accounts.csv`. The disclosure line "gallery rows are cropped from real runs, not necessarily the same run as the Loom" per D-06 still applies because multiple runs may be needed to surface all four states.
2. `hook_suppressed` and `judge_failed` are documented as rare-by-design failure modes. Plan 02 may need 2-3 runs to surface them across 10 domains. If a state still does not surface, Plan 02 records the gap and proceeds with the three states that did; the gallery markdown placeholder for the missing state stays in the README so a future plan can fill it.
3. Recording the demo bundle itself is a Phase 5 fixture-gap follow-up, not a Phase 8 deliverable. It is flagged here but not addressed in this milestone.

## Flagged Phase 5 Fixture Gap

`fixtures/demo-bundle/` is empty of fixtures. The replay path advertised by Phase 5 cannot currently produce a demo run on the real `inputs/accounts.csv`. Recording the bundle was deferred to Phase 8 in `fixtures/demo-bundle/README.md`, but the Phase 8 charter (08-CONTEXT.md) lists bundle-recording as out of scope. The follow-up belongs in a post-milestone hardening pass; it does not block Phase 8.

## Run Artifacts

No Google Sheet was produced because the replay run crashed before any account was scored. No run-id timestamp to record.

## Constraints Honored

Vendor-neutral language throughout. No hiring company name. No em-dashes or en-dashes anywhere in this file (verified by grep). No emojis.
