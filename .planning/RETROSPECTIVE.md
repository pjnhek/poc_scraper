# Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-07-15
**Phases:** 8 | **Plans:** 33

### What Was Built

A demo-ready hardening of the account-research pipeline. Groundedness is now enforced by construction (a shared `src/citations.py` parser drops any claim that fails rapidfuzz coverage against its cited evidence), failures are classified into a four-state `AccountStatus`, the eval set is expanded and calibrated cross-family, and the rigor is made legible in a byte-stable `evals/REPORT.md` (2.73/5.0 holdout). Failure modes are hardened, the Google Sheet output is demo-legible (four-state colors, per-run Sources tab with HYPERLINK citations, per-axis columns), the repo is scrubbed of the hiring-company name with a pre-commit guard, and the README plus a recorded walkthrough close the milestone pinned to commit `f868a09`.

### What Worked

- **Audit-first sequencing.** Phase 1 produced findings that drove Phases 2+, avoiding speculative fixes.
- **Single source of truth for citations.** Consolidating the parser into `src/citations.py` kept the writer, judge, and sheet in sync and made the grounding guarantee testable.
- **Honest disclosure over polish.** Where reality diverged from the plan (2 of 4 gallery states captured; kommodo instead of Loom; the walkthrough missing the `[N]`-click), the artifacts document the gap rather than hide it, which fits the project's whole thesis.

### What Was Inefficient

- **Tracking drift.** Several phases (2, 6) shipped their work but were never formally closed (no `NN-VERIFICATION.md` committed, ROADMAP rows stuck In Progress), requiring retroactive reconciliation at milestone close. Committing verification artifacts at phase close would have avoided it.
- **Emergent failure states are not capturable on demand.** `hook_suppressed` and `judge_failed` never surfaced across real-run attempts, so the gallery shipped with 2 of 4 states. A deliberately thin-context fixture domain would have forced `hook_suppressed`.
- **Environment fragility.** A directory move left the venv with a stale hardcoded interpreter path; `make test` failed until rebuilt.

### Patterns Established

- Every cross-stage value is a frozen, `extra="forbid"` pydantic model, so prompt drift fails loudly.
- Public-repo discipline enforced by a local gitignored `.secrets-denylist` + pre-commit guard, keeping the vendor abstract in `configs/icp.yaml`.
- Demo artifacts pin to a specific commit SHA so "what the video shows" is verifiable.

### Key Lessons

- Commit the `VERIFICATION.md` at phase close, not later — deferred verification becomes milestone-close debt.
- For demos, prefer a recording that shows the single most load-bearing interaction (here, the `[N]`-citation click) over broad coverage; that beat is the proof.
