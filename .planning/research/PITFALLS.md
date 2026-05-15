# Pitfalls Research

**Domain:** Grounded LLM account-research POC, demo-ready v1, public hiring artifact
**Researched:** 2026-05-14
**Confidence:** HIGH (drawn from CLAUDE.md first-class failure modes, the codebase CONCERNS.md audit, and well-documented LLM-eval literature)

The pitfalls below are organized around the two declared demo-killers (ungrounded outreach claims, eval numbers that don't tell a story) plus the public-repo discipline that makes the artifact shareable at all. Each pitfall is specific to this codebase: it names files, current behavior, and the exact failure shape, not generic "LLM apps are tricky" advice.

Phase abbreviations used below match the milestone's eight phases:
- **audit** — groundedness audit
- **fix-grounding** — close gaps the audit surfaces
- **expand-eval** — grow `evals/labeled.jsonl` with coverage rationale
- **narrative** — eval narrative artifact (report / README / screenshot)
- **harden-failures** — rate limits, scraping blocked, empty enrichment, sub-threshold
- **polish-sheet** — Sheet output legibility
- **readme-loom** — README refresh + Loom re-record
- **public-repo-audit** — scrub vertical / vendor / domain leaks

## Critical Pitfalls

### Pitfall 1: Partial-citation laundering (one good cite, three fabricated claims)

**What goes wrong:**
The writer-side guard at `src/outreach.py:71-80` drops a paragraph only when it contains *zero* valid `[N]` markers. A paragraph with one real citation and three fabricated claims passes the guard and ships to the sheet. The judge later flags low groundedness, but the paragraph text still appears in the cell, and the eval cell coloring is the only visible signal.

**Why it happens:**
"Has at least one citation" is the obvious, easy invariant to enforce. Sentence-level coverage requires either decomposing the paragraph the same way the judge does, or constraining the writer to one-claim-per-sentence and requiring `[N]` per sentence — both more involved than a "any marker present?" check.

**How to avoid:**
Raise the writer-side bar to sentence-level coverage. Two viable shapes:
1. Require every sentence to end with a `[N]` marker; drop sentences that don't (keep the paragraph if at least N sentences survive).
2. Have the writer emit a list of `(claim, supporting_indices)` tuples and the renderer assembles the paragraph from only the cited claims.
Pair this with a sheet-level suppression: when judge groundedness is below threshold, replace the hook text with a visible "[suppressed: groundedness {score} below {threshold}]" stub so a hallucinated claim never reaches a viewer's eye.

**Warning signs:**
- Spot-checking demo rows shows paragraphs with one `[2]` cite and several specific-looking claims (numbers, dates, product names) that don't trace to any retrieval.
- Judge groundedness frequently lands in the 0.4-0.7 band rather than bimodal at extremes — partial-coverage paragraphs cluster here.
- The README claims "every claim is grounded" but a viewer can find a paragraph where they can't match a claim to a retrieval.

**Phase to address:** audit (detect), fix-grounding (raise the bar), polish-sheet (suppress display)

---

### Pitfall 2: Judge-writer collusion (same model, same prompt patterns)

**What goes wrong:**
DeepSeek v4-flash writes the hook, DeepSeek v4-pro judges it. Same model family, similar tokenizer, similar instruction-following biases. The judge gives high marks to hook patterns the writer reliably produces, including hook patterns that aren't actually well-grounded — the judge has the same blind spots as the writer. Groundedness scores look great; a different judge (a human, or a different model family) would disagree.

**Why it happens:**
Cost and configuration convenience. One provider key, one client, one config. Same-family judges are also genuinely better at parsing the writer's output format, which makes them seem more "accurate."

**How to avoid:**
Run a calibration pass: for a small slice of `evals/labeled.jsonl` (10-20 examples), score with both the DeepSeek judge and a different family (NVIDIA Build's `bytedance/seed-oss-36b-instruct` is already wired up as the NVIDIA judge default). Report inter-judge agreement (kappa or simple % agreement) in the narrative artifact. If agreement is high, the same-family judge is defensible; if low, surface that honestly and use the cross-family score as the headline number.

**Warning signs:**
- Judge groundedness on `labeled.jsonl` is uniformly higher than human spot-check agreement.
- The judge never flags a specific failure pattern (e.g. dates without source) that a human reader catches immediately.
- Adding a clearly-fabricated claim to a test hook still scores >0.8.

**Phase to address:** expand-eval (add the cross-judge calibration slice), narrative (report inter-judge agreement honestly)

---

### Pitfall 3: Eval-set overfitting on a tiny `labeled.jsonl`

**What goes wrong:**
`evals/labeled.jsonl` is small (the milestone goal is to "expand to a size that makes the rigor claim defensible"). When the eval set is small, every prompt tweak gets validated against the same handful of examples. The writer prompt drifts toward patterns that score well on those specific examples and loses generality. By demo day, the eval number is impressive but reflects the prompt's adaptation to the labels, not real generalization.

**Why it happens:**
Iteration speed. A 10-example eval set runs in seconds and gives a clean number. The temptation is to tune-until-green, then move on. There's no held-out slice because partitioning a tiny dataset feels wasteful.

**How to avoid:**
- Hold out a fixed slice (e.g. 30%) at expansion time and *never* look at writer outputs on it during prompt iteration. Score the headline number on the held-out slice only.
- Track eval-set size, train/holdout split, and coverage axes (industry / size / public-vs-private / news-thin-vs-thick) in a `evals/COVERAGE.md` so a reader can see what the rigor claim is actually backed by.
- Iterate against the *training* slice (visible) only; promote prompt changes to holdout only when training slice scores stop moving.

**Warning signs:**
- Eval score climbs steadily across prompt tweaks with no plateau.
- Adding a new domain to `labeled.jsonl` causes a noticeable score drop on that one example.
- The eval-set size in the README is a round small number ("10 examples") and the score is suspiciously high (>0.9).

**Phase to address:** expand-eval (size and coverage), narrative (disclose split honestly)

---

### Pitfall 4: Eval-set composition that doesn't mirror real failure modes

**What goes wrong:**
`labeled.jsonl` over-represents the easy case: domains with rich about-pages and recent news where the writer has plenty of material to cite. The hard cases — thin enrichment, news older than 90 days, ambiguous fit — are under-represented. The headline groundedness number is high because the eval set is the easy slice. On a real CSV with a mix of well-known and obscure companies, the pipeline fails in ways the eval never measured.

**Why it happens:**
Hand-labeling is expensive, and the natural instinct is to label examples that have something interesting to label — which means examples with rich retrievals. Failure cases (empty enrichment, scraping blocked) feel like "not really testing the writer" and get omitted.

**How to avoid:**
Define a coverage matrix before expanding, documented in `evals/COVERAGE.md`:
- Enrichment quality: thin / moderate / rich (≈ 1/3 each)
- News recency: stale / fresh / mixed
- ICP fit: clear yes / clear no / borderline
- Public profile: well-known / mid-tier / obscure (where retrievals are scarce)
- Failure modes: at least one example each of empty enrichment, blocked scrape, no recent news
Aim for the matrix to be filled before chasing eval-set size. Twenty well-distributed examples beat fifty over-sampled from the easy quadrant.

**Warning signs:**
- All examples in `labeled.jsonl` have non-empty `news` and non-empty `about` retrievals.
- No example has `status == "unscoreable"`.
- All groundedness labels cluster in 0.7-1.0; nothing labeled as a "writer correctly refused" case.

**Phase to address:** expand-eval (define and fill the matrix), audit (identify which failure modes need to appear in the eval set)

---

### Pitfall 5: Judge `groundedness=1` sentinel collision (failed-judge looks like fully-hallucinated)

**What goes wrong:**
`evals/rubric.py:106-113` returns `groundedness=1` when the judge fails to produce a parseable response. A fully-hallucinated hook also scores `groundedness=1`. The sheet flags both as red. A reader concludes the writer is fabricating when actually the judge crashed.

**Why it happens:**
Sentinel collision: using a real score value to mean "failure." Both "judge failed" and "writer fabricated" are bad outcomes, so collapsing them feels harmless. It isn't — they have different fixes (retry the judge vs fix the writer prompt) and different stories at demo time.

**How to avoid:**
Already noted in CONCERNS.md (MEDIUM). Introduce a separate `eval_failed: bool` on `EvalScore`, or make groundedness `Optional[float]` with `None` = judge failed. Surface in the sheet as a distinct color (e.g. grey for judge-failed, red for sub-threshold writer output).

**Warning signs:**
- A row is flagged red, but inspecting the hook shows visible, correct citations.
- Judge failure rate isn't tracked as a separate metric in the narrative artifact.
- Re-running a "red" row sometimes turns it green with no code change.

**Phase to address:** fix-grounding (separate the sentinel), polish-sheet (distinct visual treatment), narrative (track judge-failure rate as a separate KPI)

---

### Pitfall 6: Semantic drift between claim and cited source

**What goes wrong:**
The writer emits "Company X is hiring aggressively in support" and cites `[3]`. Retrieval `[3]` actually says "Company X opened a new London office." The `[N]` marker is structurally valid (the cross-check at `src/outreach.py:71-80` passes), but the *semantic* link doesn't hold. The judge in `evals/rubric.py` is the only line of defense, and it's an LLM that can also miss this.

**Why it happens:**
Citation-extraction is treated as a structural problem (is the marker present? does the index exist?) rather than a semantic one (does the source actually support this specific claim?). The judge does semantic checking but is itself fallible, and there's no spot-check process that pairs claim + source side-by-side for human review.

**How to avoid:**
- In the eval narrative artifact, include a "verbatim audit" slice: for 5-10 hooks, render each claim next to its full cited retrieval text. A reader can visually verify the link.
- Tighten the judge prompt to explicitly demand "quote the exact span of the source that supports this claim." If the judge can't quote a span, the claim is uncited regardless of whether a `[N]` marker is present.
- Consider adding a semantic-similarity floor (embedding cosine between claim and cited justification text) as a cheap secondary check; flag below-floor rows for human review rather than auto-dropping.

**Warning signs:**
- The judge gives high groundedness, but when you read the hook and its retrievals side by side, the topical match is fuzzy.
- Hooks that cite `[N]` with a number-or-date-heavy claim (most prone to drift) score the same as hooks citing simpler claims.
- The eval prompt asks "is the claim supported?" without requiring the judge to identify the supporting span.

**Phase to address:** audit (manual claim-source pairing on a sample), fix-grounding (judge prompt + writer prompt tightening), narrative (verbatim audit section)

---

### Pitfall 7: Vertical / vendor / domain leaks in the public repo

**What goes wrong:**
CONCERNS.md HIGH findings: `inputs/accounts.csv` lists 10 real, identifiable companies; `src/contacts.py:61-66` hardcodes CX-vertical persona names; `src/enrich.py:22, 147` and `evals/run_live.py:10` name specific vendors (Zendesk, Mercury). A public repo with these intact is a public list of named sales prospects branded with a specific vertical. The hiring artifact becomes unshareable; worse, it becomes a *liability* artifact.

**Why it happens:**
Vertical-specific examples are easier to write than abstract ones — they make prompts concrete and tests realistic. Defaults get added when a function "needs to return something" on a failure path. Real domains end up in fixtures because they're the domains you tested against. Each individual leak is innocent in isolation; together they form a vertical signature.

**How to avoid:**
Dedicated phase, not ad-hoc scrubbing:
- Replace real domains in `inputs/accounts.csv` with synthetic placeholders matching the `evals/labeled.jsonl` pattern (`examplefin.com`, `examplestream.com`). Move the real list to gitignored `inputs/accounts.local.csv`.
- Either drop `_default_contacts()` (emit empty + sheet error) or move defaults to `configs/icp.yaml` so swapping the YAML swaps the defaults.
- Scrub prompt examples and docstring examples to generic placeholders.
- `git log --all -p | grep -i` for the known leaked terms (Zendesk, Mercury, the customer list) — leaks in history are also leaks.
- Add a pre-commit grep against a deny-list of strings to prevent regression.

**Warning signs:**
- A `grep -ri` over the repo for any of the documented leaked terms returns hits.
- The README's described vertical can be inferred from `configs/icp.yaml` content alone without other context — that's expected for a local run, but the *committed* version should be abstract enough that a reader can't pin a specific vertical without the operator's intent.
- A new contributor reading the code asks "is this a CX tool?" — the abstraction failed.

**Phase to address:** public-repo-audit (the entire phase)

---

### Pitfall 8: Eval theater (numbers that look great but don't reflect real failure modes)

**What goes wrong:**
The README shows "groundedness 0.94 across 50 examples" and that becomes the rigor headline. The reader can't tell: how was the dataset built? What's the judge? What's the writer? Is the judge the same model family? How many of those 50 examples are easy vs hard? What does 0.94 mean in terms of "a viewer would notice a hallucination" vs "the judge nitpicked one phrase"? Without that context, the number is theater — it signals rigor without delivering it.

**Why it happens:**
A single number is the easiest thing to put in a README. The supporting context is laborious to write and easy to skip. The bar for "looks rigorous" is depressingly low; most AI demos don't even have an eval number, so any number feels like progress.

**How to avoid:**
The eval narrative artifact (a dedicated phase) is the antidote. It should answer, in order, on one page:
1. What does the writer produce? (one example hook with citations)
2. What does the judge check? (the rubric, with its 1-5 categorical scale per NeMo guidance)
3. What's the dataset? (size, split, coverage matrix from Pitfall 4)
4. What's the headline number, on the *held-out* slice?
5. What are the known failure modes that the eval *doesn't* catch? (be explicit: "the judge is same-family; cross-family agreement is X%")
6. One worked example of a hook that scored low and why.
Treat 5 and 6 as non-negotiable; they're what distinguishes a real eval from theater.

**Warning signs:**
- The README cites a groundedness number but can't answer "what does the judge look for, exactly?"
- No worked example of a failure case in the artifact.
- No mention of what the eval *doesn't* cover.

**Phase to address:** narrative (this is the artifact's whole purpose)

---

### Pitfall 9: Demo-day rate-limit cliff

**What goes wrong:**
The Loom is recorded weeks before the demo; live re-runs during a hiring conversation hit DeepSeek or Exa rate limits because the operator queued a different test 30 seconds earlier. The pipeline retries with exponential backoff (`src/clients/nvidia_client.py:115-120`, 6 attempts) and the demo viewer watches a spinner for 60 seconds. Worse: Exa's `Retry-After` header is ignored (CONCERNS.md MEDIUM), so backoff is decoupled from when the rate-limit window actually resets.

**Why it happens:**
Rate-limit handling is tested for correctness (does it eventually succeed?) but not for *latency under contention*. The retry logic looks bulletproof in isolation but creates dead air in a live demo.

**How to avoid:**
- Parse `Retry-After` in `src/clients/exa_client.py` and `src/clients/browserbase_client.py` so wait time tracks the server's actual hint.
- Pre-cache a "demo bundle": a fixed CSV of synthetic domains where every retrieval is pre-recorded (vcr.py cassettes or a stub Exa client). The Loom records against this, the live demo can replay it offline.
- Make the live-run mode a clearly labeled second tier: "here's the cached demo; if you want to see it hit live APIs, that takes 2-3 minutes."

**Warning signs:**
- `make run` on the demo CSV takes more than ~90 seconds wall time.
- A second run started within 5 minutes of the first triggers retries.
- The Loom shows a noticeable pause during enrichment or scoring.

**Phase to address:** harden-failures (Retry-After parsing), readme-loom (offline demo bundle, cached fixtures)

---

### Pitfall 10: Loom-vs-code drift

**What goes wrong:**
The Loom shows the pipeline output as it was three weeks ago. Since then: the sheet columns changed, the scoring rubric got a new axis, the citation rendering moved from "(1)" to "[1]". A viewer hits the README, watches the Loom, then clones the repo and runs it — the outputs don't match. The artifact looks careless.

**Why it happens:**
Re-recording is a 30-minute commitment that gets deferred. The Loom is recorded once "to unblock the README" and then code keeps changing.

**How to avoid:**
- Lock the README/Loom refresh to the *closing* phase of the milestone (it already is — `readme-loom` is intentionally last). Do not re-record until every other phase has shipped.
- Add a README section "Loom recorded against commit `<sha>`" so a viewer can pin the version.
- Take a single "demo screenshot" of the final Sheet output and embed it in the README so even if the Loom drifts, the static reference matches the current code.

**Warning signs:**
- The README mentions a column or feature visible in the Loom but not in `src/sheets.py`.
- The Loom shows `score: 7.5/10` and the current code emits `score: 7.5` with no `/10`.
- A clone-and-run reader has to manually reconcile what they see vs what was demoed.

**Phase to address:** readme-loom (re-record against the final pipeline output, pin the commit SHA)

---

### Pitfall 11: Generic LLM "personalization" that obviously isn't

**What goes wrong:**
The outreach hook reads "I noticed you're a fast-growing company in your industry" — technically grounded (the about-page does say the company is growing), citation present, judge scores it `groundedness=1`. A human reader recognizes it as the kind of slop that anyone who's received B2B outreach can spot in two seconds. The rigor system passes; the *output quality* fails.

**Why it happens:**
Groundedness is necessary but not sufficient. A claim can be both true and useless. The eval rubric measures whether claims are supported, not whether they are *specific, recent, and non-generic*. The writer optimizes for what the judge measures.

**How to avoid:**
- Add a "specificity" axis to the judge rubric — does the claim name a concrete artifact (product, event, hire, quote, number, date) from the source, or is it a generic restatement? Score 1-5 like groundedness.
- Add a "recency" axis — is the cited source dated within the last 90 days where claimed? News retrievals already have a recency window; the judge should verify the *hook* actually leverages that recency.
- Surface specificity and recency alongside groundedness in the sheet and the narrative artifact. The story becomes "grounded AND specific AND recent," not just "grounded."

**Warning signs:**
- Reading 5 random hooks, you can't tell which company each is about without looking at the row's domain.
- Hooks contain phrases like "fast-growing," "industry leader," "innovative" — all groundable, all generic.
- The judge's groundedness scores are uniformly high but a human reader rates only some hooks as "I'd actually send this."

**Phase to address:** fix-grounding (judge rubric expansion), expand-eval (label specificity + recency on examples), narrative (report all three axes)

---

### Pitfall 12: Sheet legibility failure (rigor invisible to the viewer)

**What goes wrong:**
The Sheet contains all the right data — citations, groundedness, score breakdown, error reasons — but the viewer can't *find* it. Citations are tiny gray `[1]` markers in a wall of text. The eval-cell red-flag (`src/sheets.py:431-471`) is one cell in a 20-column row that scrolls off-screen. The score breakdown is a single number, not a row of axis-by-axis scores. A demo viewer asks "where's the citation?" and the operator has to scroll, zoom, and explain — which kills the "this is rigorous and self-evident" pitch.

**Why it happens:**
Sheet polish is treated as a last-mile cosmetic concern. The data is correct; making it *legible* requires column ordering, freeze panes, conditional formatting on multiple cells, and link rendering — each small, none individually exciting.

**How to avoid:**
- Citation column: render hyperlinks, not bare URLs. The `[N]` marker in the hook cell links to the corresponding row in a separate "Sources" tab.
- Score breakdown: one column per axis with the raw score + the weight applied, summing to the total in the final column. A viewer can see why the total is what it is.
- Conditional formatting on `status == "unscoreable"` rows (whole row greyed) and on sub-threshold groundedness rows (whole row tinted, not just one cell).
- Freeze the domain column and the first header row. The sheet has many columns; scrolling without a freeze pane is disorienting.
- Hover-text / cell notes on judge groundedness explaining what the number means.

**Warning signs:**
- A viewer asks "what does this number mean?" about anything on the sheet.
- The viewer can't immediately spot the flagged rows when shown the sheet for the first time.
- Citations are present but a viewer doesn't realize they're clickable / cross-referencable.

**Phase to address:** polish-sheet (the entire phase)

---

### Pitfall 13: Broad `except Exception` masks real bugs as network failures

**What goes wrong:**
`src/pipeline.py:60, 71, 79, 86, 103` each wrap a stage in `except Exception`, log a warning, and continue. A genuine bug introduced during the milestone (a `KeyError` from a refactor, a `ValidationError` from a model change) is indistinguishable from a network blip. The pipeline finishes, the row is flagged with a generic error, and the operator concludes "Exa was flaky again" — when actually the code is broken. Demo day surfaces this at the worst time.

**Why it happens:**
Resilience is correctly prioritized for the documented failure modes (rate limits, scraping blocked), and `except Exception` is the path of least resistance to achieve it. The downside (debuggability collapse) only surfaces during a refactor or a model change, which is exactly when this milestone is happening.

**How to avoid:**
- Either narrow to `(httpx.HTTPError, APIError, BrowserbaseError, json.JSONDecodeError, ValidationError)` and let unexpected types propagate, OR
- Keep the broad catch but log with `exc_info=True` and tag the row's `error` field with the exception class name. A `KeyError: 'foo'` in the error column is unmistakable; "scraping failed" is not.
- Add a "swallowed exception" counter that surfaces in the run summary. If a clean run has 0 and a broken run has 8, the signal is obvious.

**Warning signs:**
- An error column shows the same generic message across many rows when previously rows had varied errors.
- Tests pass but `make run` produces rows with errors that match no documented failure mode.
- Stack traces are nowhere in the logs because they were swallowed.

**Phase to address:** harden-failures (narrow the catches + tag with exception class)

---

### Pitfall 14: Empty enrichment path untested + falls back to vertical defaults

**What goes wrong:**
Two issues interact. (1) CONCERNS.md notes no integration test wires `FakeExa(about=[], news=[])` end-to-end. (2) `src/contacts.py:61-66` falls back to CX-vertical defaults when the contacts LLM call fails. Combined: on a domain with no enrichment, the pipeline emits "unscoreable" — but if the score path succeeded and only the *contacts* call failed, the row ships with hardcoded CX personas regardless of `configs/icp.yaml`. A devtools-vertical run shows "VP Customer Experience" in the persona column. Demo-credibility hit.

**Why it happens:**
Fallback values are added during initial development to keep the pipeline from emitting empty cells. Once added, they're invisible — the code path only fires on LLM failure, which is rare in dev. The vertical-coupling sneaks in because the developer was testing CX.

**How to avoid:**
- Either drop `_default_contacts()` entirely (emit empty contacts + clear "contacts inference failed" in the sheet error column), OR
- Move the defaults to `configs/icp.yaml` under a `default_personas` block; read them in `_default_contacts()`. Swapping the YAML swaps the defaults.
- Add the missing integration test: `FakeExa(about=[], news=[])` plus a stub that fails the contacts call, asserting either empty contacts or YAML-driven defaults (depending on which fix is chosen).

**Warning signs:**
- `make run` on a devtools `configs/icp.yaml` shows CX personas in the output.
- Removing the contacts LLM client temporarily still produces output with reasonable-looking personas.
- `grep -ri 'VP\|Director\|Head of'` in `src/` returns hardcoded title strings.

**Phase to address:** fix-grounding (drop or YAML-ify the defaults), harden-failures (add the integration test)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Broad `except Exception` in pipeline stages | One-line resilience for every stage | Real bugs masquerade as network failures, debuggability collapses during refactors | Acceptable IF accompanied by `exc_info=True` logging + exception-class tagging in the error column |
| Hardcoded defaults in `_default_contacts()` | Keeps the persona column non-empty when LLM fails | Vertical coupling in `src/`, violates the "vertical lives in YAML" design, leaks CX terms into a public repo | Never acceptable in current form; either drop the defaults or move them to `configs/icp.yaml` |
| Truncating `enrichment.justifications[:10]` silently (`src/score.py:138`, `src/outreach.py:133`) | Prompt size stays bounded | Writer is biased toward about-page entries (assigned lower indices); justifications 11+ are invisible to both writer and judge | Acceptable for POC scale; document the cap in the prompt so the writer knows it's working with a subset |
| Same model family for writer and judge | One API key, one client, one configuration | Judge inherits the writer's blind spots; "groundedness 0.94" overstates real reliability | Acceptable IF reported alongside cross-family inter-judge agreement on a calibration slice |
| Tiny `evals/labeled.jsonl` with no train/holdout split | Fast iteration on prompts | Eval-set overfitting, headline number reflects prompt-tuning not generalization | Never acceptable for the rigor claim; split is the cost of credibility |
| Single sheet without freeze panes / hyperlinked citations | Sheet ships faster | Viewer can't navigate, citations are invisible, rigor work doesn't land | Acceptable for an internal-tool POC; not acceptable for a public-artifact demo |
| Ignoring `Retry-After` in Exa / Browserbase clients | Simpler retry code | Retries land before the server's window resets, multiplying 429s; demo-day cliff | Acceptable until the first time it bites a live demo; the harden-failures phase should fix it preemptively |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| Exa | Trusting that "top-N results" always include the most-recent news within the 90-day window | Sort by published date after retrieval; the API's relevance score isn't recency-aware. Also: cap retrieved-content age in the prompt explicitly (don't just trust the Exa filter) |
| Exa rate limits | Ignoring `Retry-After`; using fixed exponential backoff only | Parse `Retry-After`; honor it when present, fall back to exponential when absent (CONCERNS.md MEDIUM) |
| Browserbase | Retrying only on `httpx.HTTPError`; `BrowserbaseError` ("empty rendered content") is not retried (CONCERNS.md observation) | Document this explicitly so a viewer of the code doesn't expect retries on every failure; if empty-render retry is desired, widen the retry exception list |
| DeepSeek `response_format={"type":"json_object"}` | Assuming it works on NVIDIA fallback path too | It doesn't; NVIDIA uses the heuristic `find first-{-to-last-}` parser in `src/_json_utils.py`. Acknowledge in README ("NVIDIA path is unreliable for live demos") |
| Google Sheets API | Creating a sheet via service account that can create but not share, leaving the user with a URL they can't open (CONCERNS.md LOW) | After `_create_empty_spreadsheet`, attempt a read; if 403, surface the permission gap in the log so the user knows to fix sharing |
| Google Sheets API | Writing all rows in a single batch request and blowing through the API quota | Use `batchUpdate` with chunked row writes; current scale (≤10 domains) is fine, but a 100-domain run will rate-limit |
| OpenAI-compatible client constructors | Passing API keys as plain strings; `repr()` would leak (CONCERNS.md LOW) | Use `pydantic.SecretStr` on `Settings`, call `.get_secret_value()` at the client boundary |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Serial LLM calls per account (enrich → score → contacts → 3x outreach → 3x judge ≈ 8 calls) | Single-account latency 60-160s; concurrency hides it in aggregate | Acceptable at POC scale; if scaling matters, batch outreach + judge calls per account | At 100+ accounts with tight latency requirements |
| Exa retrieval per domain with no cache | Wall-clock time on re-runs is identical to first run | Add a retrievals cache keyed by `(domain, retrieval_type, date)` — only relevant if a domain is hit repeatedly | At 1000+ domains, or when iterating on prompts against a fixed set |
| Justification cap of 10 truncating retrieved content | Writer never sees retrievals 11-16; about-page entries dominate citations | Either lift cap, paginate retrievals across multiple writer calls, or document in prompt | Today, on any domain with rich enrichment; not a scale issue, a quality issue |
| Loom recorded against a single live run (no cached fixture) | Demo-day rate limit produces a 60s spinner | Pre-record a demo bundle with cassette-style retrieval stubs | First contended demo |
| Pre-commit hooks light, CI does the heavy lifting | A bad commit lands, CI fails 5 minutes later, the developer has to rebase | Acceptable per CLAUDE.md split; add `detect-secrets` / `gitleaks` to pre-commit so the *expensive* failures (leaked credentials) are caught locally | The first time `git add -A` picks up an unintended file |

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| `credentials.json` correctly gitignored but no pre-commit guard against `git add --force` | Service-account creds in a public repo = full Google Sheets API access for whoever finds them | Add a `detect-secrets` or `gitleaks` hook to `.pre-commit-config.yaml`; hard-fail on any `credentials*.json`, `service-account*.json`, or `.env` in the index (CONCERNS.md HIGH) |
| Real customer-target domains in `inputs/accounts.csv` committed to a public repo | Publishes a named prospect list under a specific vertical framing; reputational + arguably privacy concern | Replace with synthetic placeholders; gitignore `inputs/accounts.local.csv` for real runs (CONCERNS.md HIGH) |
| Vertical-specific terms in code / prompts / docstrings | Reveals the target vertical, identifies the operator's context, prevents the repo from being shareable as a generic artifact | `grep -ri` against a deny-list pre-commit hook (CONCERNS.md HIGH) |
| API keys passed as plain strings through client constructors | Any future `logger.debug(client)` would leak the key in repr() | Wrap in `pydantic.SecretStr`, call `.get_secret_value()` at the boundary (CONCERNS.md LOW) |
| Eval / fixture files with real domain names | Same as the accounts.csv leak but in `evals/`; CONCERNS.md notes `labeled.jsonl` already uses synthetic placeholders — preserve that pattern | Audit `evals/` for any real-domain regressions; lock the synthetic naming convention in the public-repo-audit phase |
| Git history leaks | Even after scrubbing `main`, history retains the leaks; a forensic reader can `git log --all -p` | Decide deliberately: either rewrite history before going public (BFG or git-filter-repo), or accept the history as-is with a documented note. Rewriting is preferred if the repo isn't yet widely cloned |

## UX Pitfalls

The "users" here are: (1) hiring-audience viewers reading the README + watching the Loom, (2) GTM-audience viewers looking at a live Sheet output.

| Pitfall | User Impact | Better Approach |
|---|---|---|
| README opens with implementation details (stack, install) before the *what and why* | Hiring viewer bounces in 30 seconds; the rigor story never lands | Lead with a one-paragraph "what this is + why it's interesting" + a screenshot of the final sheet; relegate install to the back half |
| Loom is 8 minutes long and front-loads setup | Viewer skips to the middle, misses the framing, sees raw output without context | Target 3-4 minutes: 30s framing, 90s narrated live run, 90s walking through the sheet output highlighting rigor signals |
| Sheet cells with raw URLs instead of hyperlinks | Viewer can't tell what's a citation vs a domain vs a sheet metadata field | Hyperlink citations to a separate "Sources" tab; render domains as clickable hyperlinks; bold-face citation markers in hook text |
| Eval results buried in a separate file the viewer never opens | The rigor work exists but doesn't show up in the artifact | Embed a screenshot of the eval narrative in the README; link to the full artifact for depth |
| Sub-threshold rows look identical to passing rows except for one tinted cell | Viewer scrolls past them, doesn't notice the rigor system is *catching* failures | Whole-row tinting on flagged rows; explicit "flagged: groundedness {x} below threshold" text in a dedicated column |
| Loom shows the operator's local environment (vertical-specific YAML, real domains) | Viewer infers the target vertical, the repo's "abstract" framing collapses | Record against the synthetic `inputs/accounts.csv` + an abstract `configs/icp.yaml`; if vertical-specific results are needed for the GTM audience, do that as a separate, unrecorded conversation |

## "Looks Done But Isn't" Checklist

- [ ] **Groundedness guard:** Drops paragraphs with zero `[N]` markers — verify it drops paragraphs where >50% of sentences lack markers (Pitfall 1)
- [ ] **Judge:** Returns a groundedness score — verify it can distinguish "judge failed" from "fully hallucinated" (Pitfall 5)
- [ ] **Eval dataset:** Has >N examples — verify coverage matrix is filled (enrichment quality x recency x fit x public-profile x failure-mode) (Pitfall 4)
- [ ] **Eval score:** Reported in README — verify it's on a held-out slice, not the slice you tuned against (Pitfall 3)
- [ ] **Eval narrative:** Exists as an artifact — verify it includes a worked failure-case example and a "what this doesn't catch" section (Pitfall 8)
- [ ] **Citation rendering:** `[N]` markers appear in hook text — verify they're hyperlinked to the corresponding source row in the sheet (Pitfall 12)
- [ ] **Sheet flagging:** Sub-threshold rows are flagged — verify whole-row tinting, not just one cell, and that flagging is visible without scrolling (Pitfall 12)
- [ ] **Rate-limit handling:** Retries with backoff — verify `Retry-After` header is parsed (Pitfall 9)
- [ ] **Empty enrichment:** Marked unscoreable — verify a test wires `FakeExa(about=[], news=[])` end-to-end and asserts the right status (Pitfall 14)
- [ ] **Persona defaults:** Pipeline emits personas on contacts-LLM failure — verify defaults are not vertical-specific hardcoded strings in `src/contacts.py` (Pitfall 14)
- [ ] **Public-repo scrub:** `inputs/accounts.csv` uses synthetic domains — verify `git log --all -p | grep` against the deny-list returns nothing (Pitfall 7)
- [ ] **README:** Mentions the rigor claim — verify it can also answer "what does the judge check, exactly?" and "what doesn't this eval cover?" (Pitfall 8)
- [ ] **Loom:** Recorded after the final phase — verify the commit SHA referenced in the README matches the Loom's pipeline output (Pitfall 10)
- [ ] **Error handling:** Pipeline catches exceptions per stage — verify the error column distinguishes "rate-limit" from "code bug" (Pitfall 13)
- [ ] **Specificity / recency:** Judge measures groundedness — verify it also measures whether claims are specific and recent (Pitfall 11)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Vertical / vendor / domain leaks discovered post-publication | HIGH | (1) Pull the repo private immediately. (2) Scrub `main` and rewrite history with `git-filter-repo`. (3) Force-push (with a clear note to any clones if possible). (4) Add the deny-list pre-commit hook. (5) Re-publish. Reputational impact is partial and time-decaying; speed of remediation matters more than completeness |
| Hallucinated claim in the Loom | HIGH | Re-record. There's no patching a recorded artifact; the cost of re-recording is much less than the cost of a viewer catching a hallucination |
| Eval-set overfitting discovered post-publication | MEDIUM | Add the held-out slice, re-score, update the README number honestly. The honesty of the update is itself a positive signal — but only if it lands before someone else catches the gap |
| Demo-day rate-limit cliff | LOW-MEDIUM | Switch to the cached demo bundle mid-demo; explain "the live API is rate-limited from earlier testing, here's the same pipeline against cached retrievals." A graceful fallback signals operational maturity rather than failure |
| Judge-writer collusion exposed by a viewer | MEDIUM | Run the cross-family calibration after the fact; report the inter-judge agreement; update the narrative. If agreement is bad, the rigor claim has to soften, but explicit limits are better than hidden ones |
| `groundedness=1` sentinel collision flagged a real hook as red | LOW | Apply the fix-grounding change (separate `eval_failed` field), re-score, the false-positive resolves. Low cost because the fix is local to `evals/rubric.py` and `src/sheets.py` |
| Loom-vs-code drift | LOW | Re-record. Cheap if caught before sharing; expensive in trust if caught after |
| Broad `except Exception` masked a real bug | MEDIUM | Narrow the catches, re-run on the failing CSV, the actual exception surfaces. Cost depends on whether the bug shipped in a demo |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 1. Partial-citation laundering | audit (detect), fix-grounding (raise bar), polish-sheet (suppress display) | Spot-check 10 hooks: every sentence with a substantive claim has an `[N]` marker; sub-threshold rows show suppression stub, not original text |
| 2. Judge-writer collusion | expand-eval (calibration slice), narrative (report agreement) | Cross-family agreement number appears in the narrative artifact; same-family judge framing is explicitly disclosed |
| 3. Eval-set overfitting | expand-eval (train/holdout split) | Headline number in README is from the held-out slice; split is documented in `evals/COVERAGE.md` |
| 4. Eval composition skewed to easy cases | expand-eval (coverage matrix), audit (identify gaps) | `evals/COVERAGE.md` exists; every cell of the matrix has ≥1 example; failure-mode examples are present |
| 5. Judge=1 sentinel collision | fix-grounding (separate field), polish-sheet (distinct color), narrative (separate KPI) | Sheet uses two distinct visual treatments for "judge failed" vs "writer failed"; judge-failure rate appears as its own number in the narrative |
| 6. Semantic drift between claim and source | audit (manual pairing), fix-grounding (judge prompt), narrative (verbatim audit section) | The narrative artifact includes a verbatim audit slice where claims and sources are rendered side-by-side |
| 7. Public-repo leaks | public-repo-audit (the entire phase) | `grep -ri` against the deny-list returns nothing; `git log --all -p | grep` returns nothing; pre-commit hook is in place |
| 8. Eval theater | narrative (the entire phase) | Narrative answers the 6 questions in Pitfall 8; includes a worked failure example and a "what this doesn't catch" section |
| 9. Demo-day rate-limit cliff | harden-failures (Retry-After), readme-loom (cached demo bundle) | `make run` on the demo CSV finishes in <90s; cached-fixtures mode exists and is documented |
| 10. Loom-vs-code drift | readme-loom (final-phase re-record + SHA pin) | README references a specific commit SHA; the Loom's visible output matches a fresh `make run` against that SHA |
| 11. Generic LLM personalization | fix-grounding (specificity/recency axes), expand-eval (label new axes), narrative (report all three) | Judge rubric has ≥3 axes (groundedness, specificity, recency); sheet shows all three; narrative reports all three |
| 12. Sheet legibility failure | polish-sheet (the entire phase) | First-time viewer can find a citation, identify a flagged row, and read the score breakdown without operator narration |
| 13. Broad `except` masking bugs | harden-failures (narrow or tag exceptions) | Error column shows distinct messages for different failure types; exception class is visible in the log/sheet |
| 14. Empty enrichment + vertical defaults | fix-grounding (drop or YAML-ify defaults), harden-failures (add the missing test) | `tests/integration/test_pipeline_failures.py` covers the empty-enrichment path; `_default_contacts` is either gone or driven by `configs/icp.yaml` |

## Sources

- `/Users/pnhek/usf msds/acme/poc_scraper/CLAUDE.md` — first-class failure modes, public-repo discipline, testing strategy
- `/Users/pnhek/usf msds/acme/poc_scraper/.planning/PROJECT.md` — declared demo-killers, audience, milestone scope
- `/Users/pnhek/usf msds/acme/poc_scraper/.planning/codebase/CONCERNS.md` — file-and-line evidence for current state of leaks, error handling, fragile areas, and test coverage gaps
- NeMo guidance referenced in CLAUDE.md — 1-5 categorical rubric beats 1-10 numeric for LLM-as-judge
- General LLM-eval literature on judge calibration, train/holdout splits in small datasets, and same-family judge bias (HIGH confidence on the patterns, MEDIUM on exact magnitude — calibration slice numbers should be measured, not assumed)

---
*Pitfalls research for: grounded LLM account-research POC, demo-ready v1*
*Researched: 2026-05-14*
