---
phase: 08-readme-and-loom-refresh
plan: 04
status: complete
completed: 2026-07-14
subsystem: docs
tags: [readme, demo, loom-substitute, sha-pin, requirements-flip, atomic-close]
requirements:
  - DEMO-01
close_commit: 74aaa3a
sha_pin: f868a09
---

# Plan 08-04 Summary

Milestone-closing plan. Operator re-recorded the walkthrough; Claude wired it into
the README, inserted the SHA pin, flipped DEMO-01, and landed the atomic close commit.

## Deliverables

- **Walkthrough recording (DEMO-01).** Published on kommodo.ai
  (`https://kommodo.ai/recordings/E751BaRaerNaXw78iXEc`), recorded against a live
  `make run` over the real 20-account `inputs/accounts.csv`. 3:32 runtime. Covers
  Rubric, Inputs, Legend, Results with an `[N]` citation click into the Sources tab,
  and closes on `evals/REPORT.md`. Confirmed publicly viewable (no login wall).
- **README ## Demo.** Embed shape kept (image-as-link). Poster is
  `images/demo-thumbnail.jpg`, a cropped frame of the recording (macOS menu bar and
  dock removed; sheet, webcam bubble, and recording indicator retained).
- **SHA pin (D-08).** `> Recording made at commit [f868a09](.../commit/f868a09).
  README and assets at that SHA match what the video shows.` Pins to the pre-close
  commit per the D-08 single-commit-gap convention.
- **DEMO-01 flipped to Complete** in both the REQUIREMENTS.md traceability table and
  the checkbox section. All three DEMO-NN requirements now Complete.
- **Image assets committed.** `images/hero.png`, `images/failure-modes/clean.png`,
  `images/failure-modes/low-groundedness.png`, and the new `demo-thumbnail.jpg`,
  plus `.gitkeep` placeholders. These were untracked and therefore 404ing on GitHub;
  the close commit adds them so the hero and gallery render once pushed.

## Deviations from plan

- **kommodo.ai instead of Loom.** Loom's free tier hit a limit, so the operator used
  kommodo.ai. The requirement is a published walkthrough linked from the README, not
  Loom specifically. The plan's Loom-specific acceptance greps (`loom.com/share/`) do
  not apply; the equivalent kommodo URL + SHA-pin + DEMO-01 asserts all pass. All
  three README "Loom" references were updated to "recording"/"walkthrough".
- **README aggressive trim (out of original plan scope, operator-requested).** Beyond
  wiring the embed, the operator asked for a full README trim. Cut duplicated ICP /
  model / AccountStatus prose, the redundant demo-flow paragraph, and the deep env-var
  reference (now pointed at `.env.example`); compressed the citations and stack
  sections. README went 188 -> 156 lines. Also updated the judge to reflect all five
  eval axes (groundedness + icp_relevance, personalization, specificity, recency),
  consistent with quick task 260714-mrg.
- **Three PNGs, not five.** `hook_suppressed` and `judge_failed` never surfaced across
  08-02's real-run attempts (documented gap); 08-03 already dropped their gallery
  entries. The close commit stages the three captured PNGs, not five.

## Verification

- `grep -E "—|–" README.md` -> 0 (no em-dashes).
- `grep -i loom README.md` -> 0 (all references updated).
- All four `images/...` references resolve to committed files.
- kommodo URL, `github.com/pjnhek/poc_scraper/commit/f868a09` pin, and the D-08 prose
  sentence each present; `<!-- SHA-PIN` placeholder fully removed.
- `DEMO-01 | Phase 8 | Complete` and `[x] **DEMO-01**` each present once.
- `make verify-public-repo` exits 0 (0 hits, commit f868a09).

## Follow-ups

- **Push required.** The close commit is local; the images render on GitHub only after
  `git push`.
- **Stale STATE.md Deferred Items row.** AXIS-01 still lists specificity/recency as
  v2-deferred though they are implemented and now surfaced. Out of scope here.
