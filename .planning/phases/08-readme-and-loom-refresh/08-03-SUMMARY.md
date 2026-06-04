---
phase: 08-readme-and-loom-refresh
plan: 03
subsystem: docs
tags: [readme, failure-mode-gallery, citations, hyperlink, requirements-flip]

# Dependency graph
requires:
  - phase: 08-readme-and-loom-refresh
    plan: 01
    provides: README scaffold with five image-path placeholders, gallery markdown, SHA-PIN comment marker, mermaid diagram update, what-this-gets-wrong section
  - phase: 08-readme-and-loom-refresh
    plan: 02
    provides: three captured PNGs (hero.png, clean.png, low-groundedness.png) plus a documented capture gap for hook_suppressed and judge_failed
provides:
  - README gallery degraded gracefully to the two captured states with a one-line honest note about the missing two
  - Citations paragraph rewritten to match the shipping implementation (per-claim cited_indices, rapidfuzz coverage gate, whole-cell HYPERLINK formula); the false inline-[N] claim is gone from every README surface
  - Hero caption corrected to describe what the capture actually shows (two of four states; not all four)
  - REQUIREMENTS.md DEMO-02 and DEMO-03 marked Complete; DEMO-01 left Pending for Plan 04
affects: [08-04-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Graceful-degrade README pattern: when an artifact-capture step under-delivers, the README is edited to remove broken image references and a one-line honest note explains the gap; the prose contract above the gallery stays intact because it describes what the pipeline does, not what the screenshots happened to show
    - Implementation-truth-over-scaffold-text: README claims about citation rendering verified against src/citations.py and src/sheets.py before commit; the Plan 01 scaffold's inline-[N] phrasing did not match the shipping whole-cell HYPERLINK behavior and was rewritten

key-files:
  created:
    - .planning/phases/08-readme-and-loom-refresh/08-03-SUMMARY.md
  modified:
    - README.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Dropped the hook_suppressed and judge_failed H4 sections and their broken image references rather than leaving alt-text-only placeholders; a broken link on GitHub reads as unfinished. The prose four-state palette description above the gallery stays intact because it documents pipeline behavior, not capture coverage."
  - "Rewrote the citations paragraph to describe the actual shipping behavior: writer emits per-claim cited_indices metadata (not inline [N] markers in prose), assemble_paragraph applies a rapidfuzz coverage gate that drops unciteable claims pre-assembly, and _hyperlink_formula wraps each whole hook and score-justification cell as a HYPERLINK to the account's first Sources-tab row. Verified against src/citations.py and src/sheets.py:_hyperlink_formula before commit."
  - "Refined the hero caption from claiming all four AccountStatus states are pictured to honestly describing what was captured: a row band across mercury, ramp, faire, and strava showing two of the four states (clean white plus low_groundedness yellow). Refers readers to the gallery and the Legend tab for the full palette."
  - "Did NOT stage images/*.png or .gitkeep files per Plan 02's deferral; Plan 04's atomic close commit stages all Phase 8 binary artifacts together (matching the Phase 7 1a4bca5 pattern)."
  - "REQUIREMENTS.md lives under .planning/ which is gitignored; the on-disk flip is the deliverable. The SDK commit helper returned skipped_gitignored as expected; force-staging would violate the user's deliberate gitignore policy."

requirements-completed: [DEMO-02, DEMO-03]
# DEMO-01 remains Pending; Plan 04 closes it after the Loom is re-recorded and the SHA is pinned.

# Metrics
duration: ~10 min
completed: 2026-06-03
---

# Phase 8 Plan 3: Wire PNGs and Flip Requirements Summary

**Degraded the README failure-mode gallery to the two states that actually surfaced in Plan 02's captures, rewrote the citations paragraph to match the shipping whole-cell HYPERLINK implementation, refined the hero caption to reflect what was captured, and flipped DEMO-02 / DEMO-03 to Complete in REQUIREMENTS.md while leaving DEMO-01 Pending for Plan 04.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-03 (this plan execution)
- **Tasks:** 2
- **Files created:** 1 (this SUMMARY)
- **Files modified:** 2 (README.md, .planning/REQUIREMENTS.md)

## Accomplishments

- README failure-mode gallery degraded gracefully to the two captured states (`clean`, `low_groundedness`) with a one-line honest note explaining that `hook_suppressed` and `judge_failed` did not surface across the three real-run attempts used for these captures. The prose four-state contract above the gallery stays intact so the README still tells the full pipeline story; only the broken image references and their H4 headers were removed.
- README citations paragraph rewritten end-to-end to match the shipping implementation. The Plan 01 scaffold's claim that the writer emits inline `[N]` markers and the sheet renders each marker as its own HYPERLINK formula was factually wrong: `src/citations.py:assemble_paragraph` joins claim text from a structured `claims` array without injecting `[N]` markers, and `src/sheets.py:_hyperlink_formula` wraps the WHOLE cell text as a single HYPERLINK pointing at the account's first row in the Sources tab. The rewrite walks the actual flow: per-claim `cited_indices` metadata, the rapidfuzz coverage gate (the rigor mechanism, surfaced for the reader), claim-level decomposition on the judge side, deterministic `(cited / max(total, 3)) * 5` groundedness math, and whole-cell HYPERLINK wrapping with named code references (`src/citations.py`, `src/sheets.py`) so a curious reader can verify in one click.
- Adjacent false claims corrected: the proof-section "What" bullet at the top of the README said `with inline [N] citation markers that hyperlink to a per-run Sources tab`; rewritten to `each hook and score-justification cell hyperlinks to the numbered evidence in a per-run Sources tab`. The Sources-tab description at line 62 said `Each [N] marker in a hook cell or a score-justification cell is a clickable hyperlink`; rewritten to `Each hook cell and each score-justification cell is wrapped end-to-end as a =HYPERLINK formula`. The demo-flow line dropped its `clicking any [N] to jump into the Sources tab` and now reads `clicking a hook or score-justification cell`.
- Hero caption refined from claiming all four AccountStatus states are pictured to honestly describing the capture: a row band across mercury, ramp, faire, and strava showing two of the four states (clean white plus low_groundedness yellow), with a pointer to the gallery and Legend tab for the full palette.
- `.planning/REQUIREMENTS.md` traceability flip: `DEMO-02 | Phase 8 | Complete`, `DEMO-03 | Phase 8 | Complete`, plus the checkboxes `[x] **DEMO-02**` and `[x] **DEMO-03**`. `DEMO-01 | Phase 8 | Pending` and `[ ] **DEMO-01**` remain unchecked for Plan 04's atomic close.

## Task Commits

1. **Task 1: README graceful-degrade plus citations rewrite** - `649692d` (docs)
2. **Task 2: REQUIREMENTS.md DEMO-02 / DEMO-03 flip** - skipped (`.planning/` is gitignored; on-disk flip is the deliverable per the user's deliberate gitignore policy)

## Files Created/Modified

- `README.md` (modified, +7 / -19 lines per the commit stat) - Dropped two H4 gallery sections, refined hero caption, rewrote citations paragraph, fixed the proof-section "What" bullet and the Sources-tab description and the demo-flow line so none of them retain the false inline-[N] claim.
- `.planning/REQUIREMENTS.md` (modified, on-disk only because `.planning/` is gitignored) - Flipped DEMO-02 and DEMO-03 to Complete in both the traceability table and the checkbox section; DEMO-01 stays Pending.
- `.planning/phases/08-readme-and-loom-refresh/08-03-SUMMARY.md` (this file, on-disk only because `.planning/` is gitignored).

## Decisions Made

See key-decisions in the frontmatter. The most consequential is the citations-paragraph rewrite: the Plan 01 scaffold made a factual claim about the implementation that the implementation does not honor, and that mismatch would have shipped to the public README at milestone close if Plan 03 had only wired PNG references and flipped the traceability table. Verifying README claims against `src/` before commit is the rigor the public artifact is supposed to demonstrate; it would be hypocritical for the README itself to misrepresent that rigor.

## Deviations from Plan

The plan's verify gate at line 89 includes `test -f images/failure-modes/hook-suppressed.png && test -f images/failure-modes/judge-failed.png`. Those two files do not exist on disk (Plan 02 documented the capture gap in `08-02-NOTES.md` and per the spawn prompt instructed graceful-degrade rather than blocking on the gap). The verify gate's binary `test -f` formulation predates the Plan 02 outcome; the plan's `acceptance_criteria` block at lines 93-94 explicitly acknowledges this case ("If a state was gracefully degraded per Step 3, that path may legitimately be absent and the SUMMARY documents the gap"), so the divergence is plan-anticipated and the SUMMARY documents it here.

**[Rule 1 - Bug] Plan-01 README claimed inline `[N]` markers that the implementation does not produce.**
- **Found during:** Task 1 (reading src/citations.py and src/sheets.py to verify the README's citation claims before commit).
- **Issue:** `src/citations.py:assemble_paragraph` joins claim text from a structured `claims` array without injecting `[N]` markers, and `src/sheets.py:_hyperlink_formula` wraps the whole cell text as a single HYPERLINK. The Plan-01 README claimed (a) the writer emits `[N]` markers inline in the prose, (b) every `[N]` marker is rendered as its own HYPERLINK formula, and (c) the demo flow involves clicking individual `[N]` markers. None of those three claims is true post-Phase-6.
- **Fix:** Rewrote the citations paragraph to describe what ships: per-claim `cited_indices` metadata, rapidfuzz coverage gate, whole-cell HYPERLINK. Fixed three adjacent false-claim surfaces: the proof-section "What" bullet (line 8), the Sources-tab description (line 62), and the demo-flow line (line 85). Verified against `src/citations.py:assemble_paragraph` and `src/sheets.py:_hyperlink_formula`.
- **Files modified:** README.md
- **Commit:** 649692d

## Issues Encountered

None blocking. The capture-gap from Plan 02 was anticipated by the spawn prompt's "graceful-degrade required" section; the README rewrite is the documented response.

## Verification Performed

All Task 1 invariants verified before commit:

- `grep -cE "—|–" README.md` returns 0 (no em-dashes).
- Python emoji regex over README.md returns 0 matches.
- Case-insensitive grep for the hiring-company name against README.md returns 0 hits.
- `grep -F "inline" README.md` returns 0 matches (the false inline-[N] claim is gone from every surface).
- `grep -oE "images/[^)]+\.png" README.md` returns exactly three paths (hero, clean, low-groundedness); all three resolve to non-zero-byte files on disk via `test -s`.
- `grep -F "hook-suppressed.png" README.md` and `grep -F "judge-failed.png" README.md` both return zero (no broken image references).
- `grep -F "SHA-PIN" README.md` returns the placeholder comment (Plan 04 needs it).
- `make verify-public-repo` exits 0.

All Task 2 invariants verified after the REQUIREMENTS.md edits:

- `grep -F "DEMO-02 | Phase 8 | Complete" .planning/REQUIREMENTS.md` returns 1.
- `grep -F "DEMO-03 | Phase 8 | Complete" .planning/REQUIREMENTS.md` returns 1.
- `grep -F "DEMO-01 | Phase 8 | Pending" .planning/REQUIREMENTS.md` returns 1.
- `grep -F "[x] **DEMO-02**" .planning/REQUIREMENTS.md` returns 1.
- `grep -F "[x] **DEMO-03**" .planning/REQUIREMENTS.md` returns 1.
- `grep -F "[ ] **DEMO-01**" .planning/REQUIREMENTS.md` returns 1.

Pre-commit hooks (trim trailing whitespace, fix end of files, check for added large files, check for merge conflicts, public-repo-discipline) passed on the README.md commit.

## User Setup Required

None. Plan 04 will require the operator to record the Loom against a live `make run` and insert the SHA-pin prose.

## Next Phase Readiness

Plan 04 (final atomic close) now has:

- A README that no longer makes any false claims about citation rendering and gracefully describes the two-state gallery with an honest gap note for the missing two states.
- DEMO-02 and DEMO-03 already Complete in `.planning/REQUIREMENTS.md`; Plan 04 only needs to flip DEMO-01 plus stage the three PNG files and the two `.gitkeep` markers atomically.
- The SHA-PIN HTML comment marker still in place for Plan 04 to grep-replace after recording.
- `make verify-public-repo` exits 0 against the worktree state.

## Self-Check

- File `.planning/phases/08-readme-and-loom-refresh/08-03-SUMMARY.md` exists: confirmed (this file).
- File `README.md` modified: confirmed via `git log --oneline -1` showing `649692d docs(08-03): degrade gallery to captured states, correct citations prose`.
- File `.planning/REQUIREMENTS.md` modified: confirmed via the six grep assertions above.
- Commit `649692d` exists in git log: verified below.

---
*Phase: 08-readme-and-loom-refresh*
*Completed: 2026-06-03*
