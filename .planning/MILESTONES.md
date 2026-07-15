# Milestones

## v1.0 MVP (Shipped: 2026-07-15)

**Phases completed:** 8 phases, 33 plans

**Delivered:** A demo-ready hardening of the account-research pipeline: groundedness made provable end-to-end, an eval narrative that makes the rigor legible, hardened failure modes, a polished Google Sheet output, a scrubbed public repo, and a front-loaded README with a recorded walkthrough pinned to a specific commit.

**Key accomplishments:**

- **Groundedness enforced by construction.** Extracted a single citation parser (`src/citations.py`) with per-claim rapidfuzz coverage checks, so any outreach claim that does not match its cited evidence is dropped before it reaches the sheet (Phases 1-2).
- **Discrete failure taxonomy.** A four-state `AccountStatus` enum (clean / low_groundedness / hook_suppressed / judge_failed) plus an `eval_failed` sentinel that separates judge failure from writer fabrication (Phase 2).
- **Defensible eval set + calibration.** Expanded `evals/labeled.jsonl` to a 15-field schema with an 18-cell coverage matrix, and a calibration runner computing cross-family Cohen's kappa and agreement per axis (Phase 3).
- **Eval narrative artifact.** A pure, byte-stable `evals/REPORT.md` renderer answering the six rigor questions from concrete artifacts, headlined by 2.73 / 5.0 mean groundedness on a 10-record holdout (Phase 4).
- **Failure-mode hardening.** RFC 7231 Retry-After handling on 429s, blanket `except Exception` sites narrowed to per-stage tuples, and replay/record machinery for credit-free deterministic runs (Phase 5).
- **Sheet legibility.** Four-state row colors with a Legend tab, a per-run Sources tab with whole-cell HYPERLINK citations, per-axis score columns, and freeze panes so the workbook reads on first open (Phase 6).
- **Public-repo readiness + demo close.** History scrubbed of the hiring-company name with a pre-commit guard, then a front-loaded what/why/proof README, a failure-mode gallery, and a recorded walkthrough pinned to commit `f868a09` (Phases 7-8).

**Known caveats (disclosed):**
- The recorded walkthrough does not demonstrate the `[N]`-citation click into the Sources tab; the citation mechanism is documented in the README prose, gallery, and live Sources tab (Phase 8, operator-accepted).
- The failure-mode gallery shows 2 of the 4 `AccountStatus` states; `hook_suppressed` and `judge_failed` did not surface across the real-run capture attempts and are documented in prose instead (Phase 8).

---
