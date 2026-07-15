---
phase: 08-readme-and-loom-refresh
verified: 2026-07-14T00:00:00Z
status: human_needed
score: 2/3 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Open the published walkthrough at https://kommodo.ai/recordings/E751BaRaerNaXw78iXEc (no login) and watch it against the final pipeline."
    expected: "The recording shows the real 20-account run: an [N] citation click into the Sources tab (citation UX), the AccountStatus row visuals, and closes on evals/REPORT.md (eval narrative). README + assets at commit f868a09 match what the video shows."
    why_human: "Video content cannot be inspected programmatically. The README link and SHA pin are verified in-repo, but whether the recording's frames actually reflect the final scrubbed output requires a human to watch it."
---

# Phase 8: README and Loom Refresh Verification Report

**Phase Goal:** Ship the public-facing artifact that closes the milestone: a front-loaded README and a re-recorded walkthrough that reflect the final, scrubbed pipeline output and a specific commit SHA, so a hiring or GTM viewer encounters the rigor story without operator narration.
**Verified:** 2026-07-14
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | README opens with what/why/proof in the first scroll, links to `evals/REPORT.md`, and references a specific committed SHA that matches the recorded walkthrough | ✓ VERIFIED | `README.md:8-10` carry `**What.** / **Why.** / **Proof.**` above the fold; Proof line links `evals/REPORT.md` (file present, 21KB). SHA pin `README.md:20` references `f868a09`, which `git cat-file` confirms is a real commit and `git rev-parse 74aaa3a^` confirms is the parent of close commit `74aaa3a` (D-08 single-commit-gap convention). |
| 2 | A re-recorded walkthrough against the real CSV reflects the final pipeline output (citation UX, four-state Sheet visuals, eval narrative) and is linked from the README | ⚠️ Link + SHA verified; video content needs human | `README.md:18` links the published kommodo.ai recording; `README.md:20` SHA-pins it to `f868a09` with the D-08 prose "README and assets at that SHA match what the video shows". Whether the video frames actually reflect citation UX / status visuals / eval narrative is not programmatically inspectable — routed to human verification. |
| 3 | README contains an architecture diagram, a failure-mode gallery, the editable-rubric framing, and an honest "what this gets wrong" section | ✓ VERIFIED | Mermaid diagram `README.md:26-53`; failure-mode gallery `README.md:65-81` (clean + low_groundedness) with an honest note `README.md:67` that `hook_suppressed`/`judge_failed` did not surface; editable-rubric framing `## ICP rubric` `README.md:99-108` ("Edit `configs/icp.yaml` to retarget"); honest `## What this gets wrong` `README.md:83-87`. |

**Score:** 2/3 truths verified (Truth 2 present and wired, video content routed to human).

### Accepted Deviations (verified handled honestly)

| Deviation | Verified Handling |
| --- | --- |
| Walkthrough on kommodo.ai, not Loom (Loom free-tier limit) | `grep -ci loom README.md` = 0. README carries the kommodo URL, the `github.com/pjnhek/poc_scraper/commit/f868a09` pin, and the D-08 prose. Requirement is "a published walkthrough linked from the README" — satisfied. Plan 08-04 `must_haves`/`key_links` still say `loom.com/share/`; superseded by documented deviation in 08-04-SUMMARY.md. |
| Failure-mode gallery shows 2 of 4 states | `hook_suppressed` and `judge_failed` never surfaced across 08-02's 3 real-run attempts (08-02-NOTES.md); no demo-bundle fallback existed. README documents all four states in prose (`README.md:63`) and the mermaid `AccountStatus` node (`README.md:35`), and is explicitly transparent about the two not captured (`README.md:67`). SC3's "one screenshot per state" parenthetical is an accepted, honestly-disclosed gap, not a failure. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `README.md` | Front-loaded rigor story, SHA pin, diagram, gallery, honest section | ✓ VERIFIED | 157 lines; all sections present; no placeholders/`<!-- SHA-PIN`/TODO/FIXME. |
| `images/hero.png` | Sheet screenshot for proof | ✓ VERIFIED | Tracked (`git ls-files`), referenced `README.md:12`. |
| `images/demo-thumbnail.jpg` | Demo poster frame | ✓ VERIFIED | Tracked, referenced `README.md:18`. |
| `images/failure-modes/clean.png` | Clean-state capture | ✓ VERIFIED | Tracked, referenced `README.md:71`. |
| `images/failure-modes/low-groundedness.png` | Low-groundedness capture | ✓ VERIFIED | Tracked, referenced `README.md:77`. |
| `evals/REPORT.md` | Linked proof narrative | ✓ VERIFIED | Present (21KB); linked from `README.md:10,85,144`. |

All four in-README image references resolve to committed files; no 404 risk once pushed.

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `README.md` | kommodo recording | markdown link `README.md:18` | ✓ WIRED | URL present; publicly viewable per 08-04-SUMMARY. |
| `README.md` | commit `f868a09` | SHA pin `README.md:20` | ✓ WIRED | Commit exists and is parent of close commit `74aaa3a`. |
| `README.md` | `evals/REPORT.md` | proof + section links | ✓ WIRED | Target file present. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DEMO-01 | 08-04 | Re-record walkthrough against final pipeline; pin SHA | ✓ SATISFIED (link/SHA); video content → human | REQUIREMENTS.md:60 `[x]`, traceability row 129 Complete. |
| DEMO-02 | 08-01 | README first scroll = what/why/proof + link to REPORT.md | ✓ SATISFIED | REQUIREMENTS.md:61 `[x]`, row 130 Complete; `README.md:8-10`. |
| DEMO-03 | 08-03 | Architecture diagram, failure-mode gallery, rubric framing, honest section | ✓ SATISFIED | REQUIREMENTS.md:62 `[x]`, row 131 Complete; README sections verified. |

All three DEMO requirements show Complete in both the checkbox list and the traceability table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| README.md | - | none | - | No em-dashes (`grep -cE "—|–"` = 0), no loom refs, no `<!-- SHA-PIN` placeholder, no TODO/FIXME/TBD. |

### Human Verification Required

**1. Confirm the published walkthrough reflects the final pipeline output**

- **Test:** Open https://kommodo.ai/recordings/E751BaRaerNaXw78iXEc (should load with no login wall) and watch it.
- **Expected:** The recording runs against the real CSV and shows the citation UX (an `[N]` click into the Sources tab), the AccountStatus row visuals, and closes on `evals/REPORT.md`. README and repo assets at commit `f868a09` visually match the video.
- **Why human:** Video frame content is not programmatically inspectable; the in-repo link and SHA pin are verified, but the substance of the recording requires human viewing.

### Gaps Summary

No blocking gaps. Every in-repo artifact for the milestone-closing README exists, is substantive, and is wired: front-loaded what/why/proof, mermaid architecture diagram, honestly-degraded failure-mode gallery, editable-rubric framing, "what this gets wrong" section, `evals/REPORT.md` links, published-walkthrough link, and a SHA pin to `f868a09` (correct parent of close commit `74aaa3a`). All image references are committed and resolve. Both accepted deviations (kommodo.ai substitution; 2-of-4 gallery states) are handled transparently in prose. The single reason this is `human_needed` rather than `passed`: verifying the recording's content genuinely requires a human to watch the video — that is an inherent limit of automated verification, not a defect in the work.

One non-blocking follow-up noted in 08-04-SUMMARY.md: the close commit is local; images render on GitHub only after `git push`. (Verified tracked via `git ls-files`, so the push will surface them.)

---

_Verified: 2026-07-14_
_Verifier: Claude (gsd-verifier)_
