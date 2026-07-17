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

## Milestone: v1.1 — MCP Server Surface

**Shipped:** 2026-07-17
**Phases:** 5 (9-13) | **Plans:** 21

### What Was Built

The grounded account-research pipeline is now an MCP server. A reusable wiring seam (`open_deps`/`collect_context`/`EvidencePack`) was extracted from `pipeline.main()` so the server shares one code path with the CLI (no duplication). On top of it: a thin, rationed `get_account_evidence` tool (stdio + streamable HTTP from one entry point), an in-memory `DemoLimiter` with fail-closed `Fly-Client-IP` resolution, a tier-gated BYOK `research_account_full` tool, `icp://rubric` / `icp://eval-report` resources, and a `research_account` prompt. Deployed live as a public thin-tier endpoint on an Oracle Cloud Always Free VM behind Caddy, with hardened/sanitized error payloads and the charter/README updated.

### What Worked

- **Dependency-driven phase order.** Extraction -> stdio -> HTTP+limits -> full tier -> deploy meant each phase built on a seam the previous one proved. The integration checker later confirmed 6/6 flows were genuinely wired, not duplicated.
- **Grounding-by-construction carried into the new surface.** Error sanitization and citation discipline were verified end-to-end (no stack traces/env/keys in any tool path), preserving the project's whole thesis over the protocol boundary.
- **Adversarial post-ship review paid off.** Two Codex reviews plus `/gsd-secure-phase` on the public endpoint caught a real, live rate-limit spoof (Caddy didn't overwrite the trusted `Fly-Client-IP` header after the deploy-target pivot) that per-phase verification and the D-14 checkpoint had missed.

### What Was Inefficient

- **Deploy-target churn.** Fly.io -> Hugging Face Spaces -> Oracle Cloud, because both Fly and HF gated previously-free container hosting behind payment mid-phase. Phase 13-04 ran ~185 min, mostly deploy troubleshooting. A cost/payment pre-check on candidate hosts before committing to one would have saved a full pivot.
- **Tracking drift again (repeat of v1.0).** STATE.md was edited through Phase 13 but never committed once, ROADMAP/REQUIREMENTS were hand-marked complete prematurely, and phase 13's VERIFICATION.md was missing at milestone-close time — all reconciled retroactively this session.
- **Security assumption silently invalidated by the pivot.** The `Fly-Client-IP`-only trust model was correct for Fly's edge (which sets the header) but unsafe behind a bare Caddy `reverse_proxy` — the pivot didn't re-derive the trust boundary.

### Patterns Established

- On any deploy-target change, re-verify the security properties the previous target provided for free (edge-set headers, single-instance guarantees, secret handling). A managed edge's implicit guarantees do not transfer to a raw VM.
- Config-content tests (asserting a security-critical directive stays in `setup.sh`/Caddyfile) as the offline guard for infra invariants no unit test can reach.
- Tier gating at registration time (not per-call refusal), so `MCP_DEMO_MODE` provably hides the full tool even with BYOK keys present.

### Key Lessons

- A deploy pivot is a security event, not just an ops event — audit the trust boundaries the old host implied.
- Commit tracking artifacts (STATE/ROADMAP/VERIFICATION) at phase close, every phase. This lesson recurred verbatim from v1.0; enforce it structurally next milestone.
- For a public endpoint, budget an explicit adversarial review pass — it found a live-exploitable gap the standard gates did not.

### Cost Observations

- Model mix: Opus orchestrator; Sonnet subagents (executors, verifier, security/integration/nyquist auditors); two Codex CLI reviews out-of-band.
- Notable: delegating verification, security, integration, and Nyquist audits to fresh Sonnet subagents kept the orchestrator lean across a long multi-command close-out session.
