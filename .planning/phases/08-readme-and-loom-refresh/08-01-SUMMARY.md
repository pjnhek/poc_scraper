---
phase: 08-readme-and-loom-refresh
plan: 01
subsystem: docs
tags: [readme, mermaid, failure-mode-gallery, account-status, citations, evals-report]

# Dependency graph
requires:
  - phase: 06-sheet-polish
    provides: four AccountStatus visual contract (clean/low_groundedness/hook_suppressed/judge_failed), per-run Sources tab, HYPERLINK on `[N]` cells, Legend tab
  - phase: 04-eval-narrative
    provides: committed evals/REPORT.md with the 2.73 / 5.0 holdout headline and §5 cross-family kappa block
  - phase: 02-groundedness-fix
    provides: src/citations.py shared citation parser (referenced by the diagram update)
  - phase: 05-failure-mode-hardening
    provides: fixtures/demo-bundle/ machinery (assessed as empty in the pre-flight)
provides:
  - Front-loaded README first scroll (hero, what/why/proof, hero screenshot placeholder)
  - Mermaid diagram updated for citations.py, AccountStatus, Sources tab, five workbook tabs
  - Failure-mode gallery markdown scaffold with four PNG placeholders
  - What this gets wrong section with three D-07 items
  - SHA-PIN placeholder comment for Plan 04
  - Stale verdict-color row claim removed
  - 08-PREFLIGHT.md documenting that the demo bundle is empty and Plan 02 must capture from real runs
affects: [08-02-PLAN.md, 08-03-PLAN.md, 08-04-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - README front-loading: what/why/proof on the first scroll before any operator-doc content
    - Visual-contract documentation: README failure-mode gallery mirrors the in-sheet Legend tab so the two surfaces agree on the AccountStatus palette
    - SHA-pin placeholder pattern: HTML comment marker (`<!-- SHA-PIN: ... -->`) so Plan 04 has a deterministic anchor to replace

key-files:
  created:
    - .planning/phases/08-readme-and-loom-refresh/08-PREFLIGHT.md
  modified:
    - README.md

key-decisions:
  - "Demo bundle fallback per D-06 is not viable in Phase 8; fixtures/demo-bundle/ contains only a README plus three empty subdirectories. Plan 02 captures all four AccountStatus PNGs from real make run outputs."
  - "Hero screenshot referenced as images/hero.png so Plan 02 has a known capture target; placeholder caption frames the four-state visual contract."
  - "SHA-pin placeholder is an HTML comment `<!-- SHA-PIN: Loom + commit SHA block goes here; populated in Plan 04 per D-08 -->` so Plan 04 can grep-anchor without ambiguity."
  - "Sample-workbook link callout under the Loom dropped the em-dash from current line 14 by rewriting `, the Rubric, Inputs, ...` instead of using a dash."
  - "Failure-mode gallery uses `### state (color)` H4 headings with image plus italic caption blocks per D-05 (stacked sequence over 2x2 table; reads cleaner with the AccountStatus name plus color in the heading)."
  - "Eval section's `(populated after first run)` code-block placeholder replaced with a one-line headline number that reuses the proof-bullet phrasing for consistency, per Claude's Discretion in 08-CONTEXT.md."

patterns-established:
  - "README front-loading pattern: title + double-meaning callout + hero paragraph + what/why/proof bullets + hero image + ICP-config blurb, then ## Demo, then ## What it does. Operator-doc content stays below."
  - "Visual-contract documentation pattern: any palette change in src/sheets.py is mirrored both in the in-sheet Legend tab and in the README failure-mode gallery; the two surfaces must agree."

requirements-completed: []
# Note: This plan contributes to DEMO-02 and DEMO-03 but the
# REQUIREMENTS.md traceability flip lives in Plan 08-03's atomic close commit
# (per the ROADMAP plan-list). The PNG bytes are not captured yet, so the
# failure-mode gallery is currently a scaffold with broken image references;
# DEMO-03 cannot be honestly marked Complete until Plan 02/03 land.

# Metrics
duration: ~25 min
completed: 2026-05-27
---

# Phase 8 Plan 1: README Front-Loading and Failure-Mode Gallery Scaffold Summary

**Rewrote the README first scroll into a what/why/proof scaffold with the 2.73 / 5.0 holdout headline, updated the mermaid diagram for src/citations.py and the four AccountStatus states reaching a five-tab workbook, scaffolded a failure-mode gallery pointing at four PNG placeholders Plan 02 will capture, added the what-this-gets-wrong section, removed the stale verdict-color row claim, and documented the demo-bundle pre-flight finding that fixtures/demo-bundle/ is empty so Plan 02 must capture from real make runs.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-27T19:13Z (Phase 08 execution start per STATE.md)
- **Completed:** 2026-05-27T20:00Z (approximate)
- **Tasks:** 2
- **Files created:** 1 (08-PREFLIGHT.md)
- **Files modified:** 1 (README.md)

## Accomplishments

- Demo-bundle pre-flight surfaced that fixtures/demo-bundle/ contains only a README plus three empty subdirectories; the D-06 cached fallback is not viable in Phase 8, so Plan 02 will capture every AccountStatus state PNG from real make runs. The gap is flagged as a Phase 5 fixture follow-up but out of Phase 8's scope per 08-CONTEXT.md.
- README first scroll rewritten end-to-end with the hero paragraph, the three what/why/proof bullets including the 2.73 / 5.0 headline linked to evals/REPORT.md, and an above-the-fold hero image placeholder at images/hero.png.
- Mermaid diagram inside ## What it does updated in place to add the citation parser node (src/citations.py), the AccountStatus state node (clean / low_groundedness / hook_suppressed / judge_failed), and the per-run Sources tab; sheet node updated from three tabs to five (Rubric / Inputs / Legend / Sources / Results).
- Workbook tab description rewritten from three tabs to five, with the per-run Sources tab and the HYPERLINK [N] navigation behavior explained.
- Stale row-color claim (strong = green, borderline = yellow, weak = pink) removed and replaced with the four-state AccountStatus visual contract (clean=white, low_groundedness=yellow, hook_suppressed=orange, judge_failed=gray) and the Legend-tab mirror reference.
- Failure-mode gallery markdown scaffolded as a stacked sequence of `### state (color)` H4 blocks with image placeholders at images/failure-modes/clean.png, low-groundedness.png, hook-suppressed.png, judge-failed.png, and a one-line disclosure "Gallery rows are cropped from real runs, not necessarily the same run as the Loom."
- ## What this gets wrong section added before ## Stack and design choices with the three D-07 items (cross-family judge agreement modest with link to REPORT.md §5, persona inference is heuristic, single-source retrieval).
- SHA-PIN placeholder comment `<!-- SHA-PIN: Loom + commit SHA block goes here; populated in Plan 04 per D-08 -->` inserted below the Loom embed so Plan 04 has a deterministic anchor.
- Em-dash sweep below the fold: six em-dashes in the prior README rewritten with commas, periods, or restructured prose. Eval section's `(populated after first run)` code-block placeholder replaced with the headline rigor number link.

## Task Commits

1. **Task 1: Demo-bundle coverage pre-flight** - `5a59051` (docs)
2. **Task 2: README rewrite + surgical edits** - `243da6f` (docs)

## Files Created/Modified

- `.planning/phases/08-readme-and-loom-refresh/08-PREFLIGHT.md` (created) - Records the empty-bundle finding so Plan 02 captures from real runs; flags the Phase 5 fixture gap.
- `README.md` (modified, +67 / -18 lines) - Front-loaded first scroll, updated diagram, gallery scaffold, what-this-gets-wrong section, SHA-PIN placeholder, em-dash sweep, eval headline replacement.

## Decisions Made

See key-decisions in the frontmatter. The most consequential is the pre-flight result: the demo bundle's fixture directories are empty (the Phase 5 README explicitly defers recording to Phase 8, and the Phase 8 charter explicitly defers bundle-recording out of scope), so Plan 02's capture work is entirely on real runs. That changes Plan 02's expected duration and risk profile (multiple real runs may be needed to surface hook_suppressed and judge_failed) but does not change the deliverable shape.

## Deviations from Plan

None. Plan executed exactly as written. Both tasks landed on the first attempt, verification gates passed without re-runs, pre-commit hooks passed on both commits without modifications.

The pre-flight outcome was unexpected (the plan anticipated `make run-demo` might fail on a stale fixture; in fact the bundle is empty by design) but is documented as the pre-flight's job per the task action: "If the demo bundle fails to run (e.g. ReplayMissError on a stale fixture), record the exception in 08-PREFLIGHT.md and flag it as a Phase 5 fixture gap. Do NOT attempt to extend the demo bundle in Phase 8 (per Out of Scope in 08-CONTEXT.md)."

## Issues Encountered

- Initial draft of 08-PREFLIGHT.md included a parenthetical referencing the dash characters via `grep -E` whose pattern chars were literal em/en dashes; the grep gate caught the regression and the line was rewritten to refer to the verification by description rather than by including the pattern characters.

## Verification Performed

All Task 2 acceptance criteria were grep-verified before commit:

- `grep -F "2.73 / 5.0 mean groundedness on a 10-record holdout" README.md`: matches (proof bullet plus Eval section headline).
- `grep -c -F "evals/REPORT.md" README.md`: returns 4 (>=3 required).
- Four independent state-name greps: all pass.
- Five image-path greps: all pass.
- `grep -F "src/citations.py" README.md`: matches (diagram node).
- `grep -F "Sources" README.md`: matches (diagram plus tab description).
- `grep -F "What this gets wrong" README.md`: matches.
- `grep -F "SHA-PIN" README.md`: matches.
- Em-dash and en-dash sweep on README.md: zero matches.
- `grep -F "strong = green, borderline = yellow, weak = pink" README.md`: zero matches.
- `make verify-public-repo`: exits 0.

Pre-commit hooks (trim trailing whitespace, fix end of files, check for added large files, check for merge conflicts, public-repo-discipline) passed on both commits.

## User Setup Required

None. No external service configuration changed.

## Next Phase Readiness

Plan 02 (operator capture session) now has a stable README target to plug into:

- Five known image paths (images/hero.png, images/failure-modes/{clean,low-groundedness,hook-suppressed,judge-failed}.png) waiting for real PNG bytes.
- Confirmed via the pre-flight that all captures must come from real `make run` outputs; the D-06 cached fallback is not viable.
- The SHA-PIN comment marker is in place for Plan 04 to grep-replace after the Loom is re-recorded.

Plan 03 (PNG wiring) and Plan 04 (Loom + SHA pin) have their anchors in place.

## Self-Check: PASSED

- File `.planning/phases/08-readme-and-loom-refresh/08-PREFLIGHT.md` exists: confirmed.
- File `README.md` modified: confirmed.
- Commit `5a59051` exists in git log: will verify below.
- Commit `243da6f` exists in git log: will verify below.

---
*Phase: 08-readme-and-loom-refresh*
*Completed: 2026-05-27*
