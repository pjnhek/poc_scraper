# Feature Research

**Domain:** AI-product POC (account research with grounded outreach) targeting a demo-ready v1 for two audiences — AI-product hiring managers (README + Loom artifact) and GTM stakeholders (live Sheet run on a real CSV).
**Researched:** 2026-05-14
**Confidence:** HIGH on table stakes and anti-features (grounded directly in PROJECT.md demo-killers, the existing codebase's invariants, and current industry guidance on RAG groundedness/citation UX); MEDIUM on differentiator ranking (depends on what slice of the audience reviews the artifact first).

## Scope Note

This is a brownfield milestone. The pipeline (`enrich -> score -> contacts -> outreach -> eval -> sheets`) already exists per `.planning/codebase/`. "Features" below are framed as **capabilities of the demo-ready v1 artifact**, not net-new pipeline stages. Anything that adds a stage or surface is flagged v2 per `PROJECT.md` Out of Scope.

Everything is scored against the two demo-killers from `PROJECT.md`:
- **DK1**: An ungrounded outreach claim that traces to nothing.
- **DK2**: Eval numbers that do not tell a coherent story.

## Feature Landscape

### Table Stakes (Must Have or the Demo Flops)

Capabilities a serious reader assumes are present. Missing any of these makes the artifact feel like a tutorial, not a POC.

| # | Capability | Why It's Table Stakes | Complexity | Pipeline Dependency | Demo Impact |
|---|------------|----------------------|------------|---------------------|-------------|
| TS1 | **Every outreach claim is traceable to a numbered justification, with no exceptions** | DK1. If a reader can find one claim that doesn't trace, the entire rigor story collapses. Industry baseline for grounded RAG demos. | LOW (writer + extractor exist in `outreach.py`; tighten the cross-check and add a regression test) | `enrich.py` (`Justification` numbering), `outreach.py` (`[N]` markers, `cited_indices`) | Kills demo if absent |
| TS2 | **Citations are visible in the Sheet next to the hook**, not only in JSON | A reader scanning the Sheet should see "claim A [2]" and be able to read justification 2 in the same row. Without this, groundedness is invisible UX. | LOW-MED (sheet column for justifications already exists per `sheets.py`; verify inline `[N]` legibility and a "Sources" column or hover) | `sheets.py` rendering | Earns trust |
| TS3 | **Eval narrative section in README** with concrete numbers, methodology, and at least one screenshot | DK2. Hiring readers expect a written story: "We hand-labeled N examples; judge MAE vs labels is X; live groundedness on a fresh CSV is Y; here's what failed and why." | MED (write + run + capture, no new code) | `evals/run_eval.py`, `evals/run_live.py`, `evals/labeled.jsonl` | Kills demo if absent |
| TS4 | **Labeled eval set sized to make the claim defensible** | DK2. A dataset of 5 hand-labeled rows is unconvincing. Needs enough rows that judge calibration is statistically meaningful and covers the failure modes. Active item in `PROJECT.md`. | MED (manual labeling; quality > quantity) | `evals/labeled.jsonl` | Kills demo if absent |
| TS5 | **Graceful degradation for `unscoreable` rows surfaces visibly in the Sheet** | A real CSV will have dead domains, blocked scrapers, empty enrichments. Hiding them looks like cherry-picking; surfacing them with a red flag and a reason demonstrates rigor. | LOW (status column + verdict coloring exist per `sheets.py:309`; verify the `unscoreable` path renders well) | `pipeline.py` per-stage exception isolation, `sheets.py` formatting | Kills demo if absent |
| TS6 | **Sub-threshold groundedness flagged inline (red cell text on `eval_groundedness`)** | Same as TS5 for the eval axis. Already exists in `sheets.py::_apply_eval_flag_text`. Verify it triggers and is legible. | LOW (validate existing) | `sheets.py`, `evals/rubric.py`, `configs/icp.yaml` flag threshold | Kills demo if absent |
| TS7 | **README front-loads the "what / why / proof"** in the first screen of scroll | Hiring readers spend 30-60 seconds before deciding to keep going. They need: (1) what this is, (2) the rigor claim, (3) a Loom or screenshot, (4) the eval numbers. Anything else can come later. | LOW (rewrite README structure) | None | Kills demo if absent |
| TS8 | **Loom walkthrough records the final pipeline output**, not a pre-rigor cut | Re-recording is non-negotiable per `PROJECT.md` Active item. A Loom that doesn't show the eval narrative or the citation UX undersells the work. | LOW (record after rigor work lands) | All stages, sheets | Kills demo if absent |
| TS9 | **Public-repo cleanliness: zero vertical/vendor names in code, prompts, configs, commits, eval data** | A leak makes the repo unshareable, killing the hiring artifact entirely. Active item in `PROJECT.md`. | LOW-MED (audit pass + history check) | All modules, `configs/icp.yaml`, `evals/labeled.jsonl`, git history | Kills demo if absent |
| TS10 | **Pipeline survives a real 20-50 row CSV run without a stack trace** | The GTM demo IS the live run. One uncaught exception in front of a stakeholder ends the conversation. | LOW-MED (failure-mode hardening is an Active item) | `pipeline.py` exception isolation, all client retry policies | Kills demo if absent |
| TS11 | **Makefile / setup instructions that work on a fresh clone** | A hiring reader who tries `make install && make run` and fails will not file a bug; they will close the tab. | LOW (validate, document env vars, screenshot the `make setup-sheet` flow) | `Makefile`, `scripts/setup_sheet.py`, `.env.example` | Earns trust |

### Differentiators (Notable Rigor Signals)

Capabilities that move the artifact from "competent POC" to "this person thinks like an AI-product engineer." Each is justified by the rigor frame, not by feature volume.

| # | Capability | Value Proposition | Complexity | Pipeline Dependency | Demo Impact |
|---|------------|-------------------|------------|---------------------|-------------|
| D1 | **Claim-decomposition groundedness derived deterministically, not asked of the judge** | The judge counts cited atomic claims rather than scoring groundedness on a Likert scale — eliminates the judge-drift failure mode and tells a coherent methodological story in the eval narrative. Already implemented (`evals/rubric.py`); just needs to be **explained in the README**. | LOW (documentation, not code) | `evals/rubric.py` | Earns trust |
| D2 | **1-5 categorical judges with cited NeMo rationale** | Most demo POCs reach for 1-10 numeric judges and silently drift. Calling out the 1-5 choice with a citation to NeMo guidance is a small signal of taste. Already implemented; make it visible. | LOW (README + eval doc) | `evals/rubric.py`, `src/models.py::EvalScore` | Earns trust |
| D3 | **Judge calibration table (judge vs. hand-labels, MAE per axis)** in the eval narrative | Turns "we have an eval" into "here's how we know the eval is trustworthy." Distinguishes a serious POC from a vibes-check. | LOW-MED (`evals/run_eval.py` produces the table; surface it in README) | `evals/run_eval.py`, `evals/labeled.jsonl` | Earns trust |
| D4 | **Documented coverage rationale for the labeled set** ("We labeled N rows across {high-fit, low-fit, unscoreable, scraped-blocked, sub-threshold}, here's why these slices") | Hiring readers care more about *how* you picked the eval set than how big it is. Tiny + thoughtful beats large + arbitrary. Active item in `PROJECT.md`. | LOW (README section) | `evals/labeled.jsonl` | Earns trust |
| D5 | **Failure-mode gallery** in the README (one screenshot each: `unscoreable`, scraping-blocked, sub-threshold groundedness, malformed CSV row) | Most demos show only the happy path. Showing the failure-path UX demonstrates production thinking and pre-empts "what happens when…" questions. | LOW (capture during smoke run) | `sheets.py` formatting + `pipeline.py` degradation paths | Earns trust |
| D6 | **One-paragraph "what would v2 look like" section** that names CRM integration, feedback loop, dashboard explicitly as deferred | Signals scope discipline rather than feature stuffing. Matches `PROJECT.md` Out of Scope discipline. | LOW (README) | None | Earns trust |
| D7 | **Editable rubric (`configs/icp.yaml`) called out as a first-class capability** in the README | The "retarget the vertical without code" story is unusual for a portfolio POC and shows separation of concerns. Already built; just needs framing. | LOW (README + a "swap rubric" example) | `configs/icp.yaml`, `src/icp_config.py` | Earns trust |
| D8 | **Architecture diagram in README** showing the linear pipeline + DI + the protocol boundary at clients | Hiring engineers read structure faster than prose. The diagram already exists in `.planning/codebase/ARCHITECTURE.md`; lift a simplified version into the README. | LOW (extract and simplify) | None | Earns trust |
| D9 | **Live-run command (`make run` against a small sample CSV)** producing the demo Sheet end-to-end in under 2 minutes | The GTM audience wants to push a button and see a Sheet. The hiring audience wants to know the loop is tight enough to iterate on. | LOW (verify timing, tune `RUN_LIMIT`) | `pipeline.py`, `Makefile` | Earns trust |
| D10 | **A "this is what the model got wrong" callout** in the eval narrative — at least one example of a low-groundedness hook with analysis | Honesty about failures is a strong rigor signal and prevents the artifact from reading as marketing. | LOW (find one row, screenshot, write 2 sentences) | `evals/run_live.py` output | Earns trust |
| D11 | **Inline links from each cited `[N]` to the source URL** in the Sheet (hyperlink in the justification cell) | Lets a reviewer click from "claim [2]" straight to the retrieval source. Promotes citations from a number to a verifiable artifact. | LOW-MED (one Sheets API formatting addition in `sheets.py`) | `sheets.py`, `Justification.url` | Earns trust |

### Anti-Features (Looks Impressive, Kills Credibility — Do NOT Build)

These are the easy traps: features a reader of *another* POC might be impressed by, but that actively undermine the rigor claim of this one.

| # | Anti-Feature | Surface Appeal | Why It Kills Credibility | What To Do Instead |
|---|--------------|----------------|--------------------------|---------------------|
| AF1 | **Single 1-10 "quality score" per hook from the judge** | Looks like a quantitative metric, easy to put in the README | 1-10 numeric judges drift run-to-run (per `CLAUDE.md` and NeMo guidance). A reader who knows eval will immediately discount the artifact. | Keep 1-5 categorical + deterministic groundedness count (already done). Explain *why* in the README — that explanation is itself the differentiator (D2). |
| AF2 | **Auto-generated "personalization" beyond what the retrievals support** (e.g., inferring tone preference, inventing a hobby) | Looks like the LLM is doing more work, makes the outreach feel "smart" | Directly violates DK1. Any reader checking citations will find unsupported claims and the whole grounding story collapses. | Drop hooks whose claims fail the index check (already done in `outreach.py:71`). Show the dropped state in the Sheet as the empty-paragraph case. |
| AF3 | **Confidence percentage on the ICP score** (e.g., "82% confident this is a fit") | Looks quantitatively rigorous, easy to print | Confidence numbers from a writer LLM are not calibrated; pretending they are is anti-rigor. A reviewer will ask "calibrated against what?" and there's no good answer. | Keep the verdict + the supporting indices. The audit-trail (`supporting_indices`) is the honest version of "confidence." |
| AF4 | **Chat / Q&A interface over the accounts** ("ask why this account scored 3 on AI maturity") | Reads as "agentic," currently fashionable | Adds a new surface, a new failure mode, and a new evaluation problem. None of it addresses DK1 or DK2. Pushes scope into v3 webapp territory which `PROJECT.md` Out of Scope rules out. | A static Sheet column with the rubric breakdown is sufficient and verifiable. Defer to v3. |
| AF5 | **More LLM calls per account "for accuracy"** (e.g., self-critique, re-scoring, ensemble of writers) | Reads as careful, easy to add | Triples cost and latency for marginal quality gains, introduces non-determinism that makes the eval narrative harder to write, and obscures *which* call produced *which* claim — undermining citation traceability. | Keep one writer call per stage. If a stage's quality is the bottleneck, fix the prompt or the rubric, not the call count. |
| AF6 | **Auto-generated, per-run "AI-written executive summary" of the run** at the top of the Sheet | Looks polished, feels enterprise | Adds an ungroundable surface — what would the citations even be? Either invites hallucination at the top of the artifact or duplicates what the rows already say. | Let the rows and the verdict-colored cells be the summary. A static legend tab is acceptable; an LLM-written summary is not. |
| AF7 | **A "fix the eval" feedback loop where the operator labels rows in the Sheet and they retrain the judge** | Sounds like a closed-loop AI system, very en vogue | Out of Scope per `PROJECT.md` (feedback loop is v2). More importantly, in a POC with a small labeled set, a feedback loop will overfit the judge to the operator's bias and the eval claim becomes meaningless. | Keep the eval offline, hand-labeled, with documented rationale (D4). Note the feedback loop in the v2 section (D6). |
| AF8 | **Vector store / embeddings layer for the retrievals** | Reads as "real RAG," everyone expects vectors | Exa already returns ranked passages; adding a vector layer for a 90-day-news + about-page corpus per account is over-engineering. It would push complexity into the pipeline without changing groundedness, the actual concern. | Keep Exa + Browserbase fallback as-is. Mention the choice in the architecture section as a deliberate one. |
| AF9 | **A long, comprehensive README that explains every module** | Looks thorough | Hiring readers will not read it. The artifact gets weaker the longer it is. | Front-load (TS7). Keep the README under one screen of structure with deep-links to `.planning/codebase/` for engineers who want to dive deeper. |
| AF10 | **Multi-tenant config / per-user rubric uploads** | Reads as "productized" | Out of Scope per `PROJECT.md`. Adds an entire concern (auth, state, isolation) for zero demo benefit. The single-operator framing IS the story. | Keep `configs/icp.yaml` as a single file. Mention multi-tenant in v3 (D6). |
| AF11 | **An LLM-written "why this persona" paragraph for each contact beyond what firmographics support** | Makes the persona feel personal | Personas are inferred from firmographics, not retrieved facts. Wrapping them in unsupported narrative invites hallucination on the persona axis — a new DK1 surface. | Keep persona output minimal: title, function, why-relevant tied to a rubric axis. Outreach is where the grounded paragraph lives. |

## Feature Dependencies

```
TS9 (public-repo audit)
    └──blocks──> TS7 (README front-load) and TS8 (Loom)
                    [can't ship the artifact with a vendor name in it]

TS1 (every claim traceable)
    └──enables──> TS2 (citations visible in Sheet)
                    └──enables──> D11 (clickable citation links)

TS4 (labeled set sized)
    └──enables──> TS3 (eval narrative)
                    └──enables──> D3 (calibration table)
                                    └──enables──> D10 (got-wrong callout)

TS5 + TS6 (graceful degradation visible)
    └──enables──> D5 (failure-mode gallery)

TS10 (pipeline survives real CSV)
    └──blocks──> TS8 (Loom records the live output)
                  └──blocks──> milestone close
```

### Dependency Notes

- **TS9 must land before TS7/TS8.** A README/Loom recorded against a repo with vendor names becomes immediately stale once the audit happens, wasting the recording effort. Active item ordering in `PROJECT.md` should reflect this.
- **TS1 is upstream of every citation-UX feature.** Until the writer's cross-check is provably tight, polishing the Sheet rendering is decorating a leaky boat. The Phase 1 groundedness audit named in `PROJECT.md` Active items is the right gate.
- **TS4 unblocks the eval narrative.** Without a defensibly-sized labeled set, the calibration table (D3) is statistically meaningless and the narrative (TS3) reads as marketing. Size and coverage rationale (D4) ship together.
- **TS10 unblocks TS8.** Recording a Loom against a pipeline that crashes on row 17 is non-recoverable; record after the failure-mode hardening Active item lands.

## v1 Definition

### Ship in This Milestone (Demo-Ready v1)

The complete table-stakes set, plus the differentiators that come effectively for free because the code already does the work and only documentation is missing.

- [ ] TS1 — every claim traceable (audit + close any gaps surfaced)
- [ ] TS2 — citations visible inline in the Sheet
- [ ] TS3 — eval narrative section in README with numbers + screenshot
- [ ] TS4 — labeled eval set sized and coverage-rationaled
- [ ] TS5 — `unscoreable` rows render visibly with reason
- [ ] TS6 — sub-threshold groundedness flagged red (validate existing)
- [ ] TS7 — README front-loaded
- [ ] TS8 — Loom re-recorded at the end of the milestone
- [ ] TS9 — public-repo audit complete
- [ ] TS10 — survives a real CSV run end-to-end
- [ ] TS11 — fresh-clone setup verified
- [ ] D1 — claim-decomposition methodology documented
- [ ] D2 — 1-5 categorical rationale documented
- [ ] D3 — judge calibration table in README
- [ ] D4 — coverage rationale documented
- [ ] D5 — failure-mode gallery in README
- [ ] D6 — v2/v3 deferral paragraph
- [ ] D7 — editable rubric framed in README
- [ ] D8 — architecture diagram in README
- [ ] D10 — "got wrong" callout

### Cheap, Ship If Time Allows

- [ ] D9 — sub-2-minute live-run path (verify, may already hold)
- [ ] D11 — hyperlinked citations in the Sheet (one `sheets.py` addition)

### Explicitly Defer

- [ ] All anti-features (AF1–AF11) — documented above as out of scope
- [ ] Out-of-Scope items from `PROJECT.md` (feedback loop, CRM, webapp, multi-tenant, custom caching) — restated as v2/v3

## Capability Prioritization Matrix

| Capability | Demo-Impact | Implementation Cost | Priority |
|------------|-------------|---------------------|----------|
| TS1 every-claim-traceable | KILLS DEMO | LOW-MED | P1 |
| TS3 eval narrative | KILLS DEMO | MED | P1 |
| TS4 labeled set sizing | KILLS DEMO | MED | P1 |
| TS9 public-repo audit | KILLS DEMO | LOW-MED | P1 |
| TS10 survives real CSV | KILLS DEMO | LOW-MED | P1 |
| TS2 citations in Sheet | EARNS TRUST + closes DK1 UX gap | LOW-MED | P1 |
| TS5/TS6 degradation visible | KILLS DEMO if hidden | LOW | P1 |
| TS7 README front-load | KILLS DEMO if buried | LOW | P1 |
| TS8 Loom re-record | KILLS DEMO if stale | LOW | P1 |
| TS11 fresh-clone setup | EARNS TRUST | LOW | P1 |
| D1–D4 eval methodology docs | EARNS TRUST (hiring) | LOW | P1 (cheap) |
| D5 failure-mode gallery | EARNS TRUST | LOW | P1 (cheap) |
| D6–D8 framing / diagram / scope discipline | EARNS TRUST | LOW | P1 (cheap) |
| D10 honest-failure callout | EARNS TRUST | LOW | P1 (cheap) |
| D9 sub-2-min run | NICE | LOW | P2 |
| D11 hyperlinked citations | NICE | LOW-MED | P2 |
| AF1–AF11 anti-features | KILLS DEMO | varies | P3 (do not build) |

**Priority key:**
- P1: Must land for the milestone to be done.
- P2: Add if time, no rework if skipped.
- P3: Explicitly do not build; named here so the roadmapper doesn't drift toward them.

## Mapping to PROJECT.md Active Items

| `PROJECT.md` Active Item | Capabilities It Delivers |
|---------------------------|--------------------------|
| Audit groundedness coverage end-to-end | TS1 (precondition for everything DK1) |
| Close groundedness gaps | TS1, TS2 |
| Expand labeled eval set with coverage rationale | TS4, D4 |
| Produce an eval narrative artifact | TS3, D1, D2, D3, D10 |
| Harden documented failure modes | TS5, TS6, TS10 |
| Polish Sheet output for demo legibility | TS2, TS5, TS6, D11 |
| Refresh README + re-record Loom | TS7, TS8, D5, D6, D7, D8, TS11 |
| Public-repo audit | TS9 |

Every Active item maps to at least one P1 capability; every P1 capability traces back to an Active item or to one of the two demo-killers. Nothing in this list is net-new feature work in the sense `PROJECT.md` Out of Scope rules out.

## Sources

- [Measuring LLM Groundedness in RAG Systems with Evaluation Metrics — deepset](https://www.deepset.ai/blog/rag-llm-evaluation-groundedness)
- [Grounding and Evaluation for Large Language Models (arxiv survey)](https://arxiv.org/html/2407.12858v1)
- [Cite Before You Speak: Enhancing Context-Response Grounding in E-commerce LLM Agents](https://arxiv.org/html/2503.04830v2)
- [A Researcher's Guide to LLM Grounding — Neptune](https://neptune.ai/blog/llm-grounding)
- [Best Practices and Methods for LLM Evaluation — Databricks](https://www.databricks.com/blog/best-practices-and-methods-llm-evaluation)
- [RAG evaluation: Metrics, methodologies, best practices — Meilisearch](https://www.meilisearch.com/blog/rag-evaluation)
- [The AI Portfolio: What "Built With AI" Means in 2026 Interviews](https://www.techinterview.org/post/3233475399/ai-portfolio-built-with-ai-2026-interviews/)
- [How to Build a Portfolio That Impresses AI PM Recruiters — Resumly](https://www.resumly.ai/blog/how-to-build-a-portfolio-that-impresses-ai-product-management-recruiters)
- Project context: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `CLAUDE.md` (NeMo 1-5 categorical guidance referenced).

---
*Feature research for: demo-ready v1 of a grounded account-research POC*
*Researched: 2026-05-14*
