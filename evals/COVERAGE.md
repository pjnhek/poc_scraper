# Phase 3: Eval Coverage Matrix

This document defines the coverage matrix that governs what `evals/labeled.jsonl` must contain.
It satisfies EVAL-01, which requires a documented matrix before any labeling begins. The matrix is
the source of truth for what the labeling session (plan 03-04) must cover. Cell names used here
match `evals/check_coverage.py::REQUIRED_CELLS` exactly; any mismatch between this document and
that frozenset causes a false coverage-gap signal.

## Coverage Matrix

| Cell | Axis | Description | Pitfall Reference | Min Examples Required |
|------|------|-------------|-------------------|-----------------------|
| thin-enrichment | Enrichment Quality | The account's about-page and news retrievals together are sparse: short about-page text, few or no news items, or content that is too generic to extract meaningful firmographics. The writer has little to work with. | Pitfall 4 (composition skewed to easy cases) | 1 |
| moderate-enrichment | Enrichment Quality | The account has a usable about-page and at least some recent news, but the total retrieved content is neither sparse nor comprehensive. The writer can form a grounded hook but has limited supporting evidence to choose from. | Pitfall 4 (composition skewed to easy cases) | 1 |
| rich-enrichment | Enrichment Quality | The account has a detailed about-page, multiple recent news items, and enough specific signals (numbers, dates, named products or events) that the writer has ample citation material. This is the easy case and should not dominate the set. | Pitfall 4 (composition skewed to easy cases) | 1 |
| stale-news | News Recency | All news retrievals for this account are older than 90 days at the time of the source run, or no news was returned at all. The writer cannot produce a recency-grounded hook. | Pitfall 4 (composition skewed to easy cases); Pitfall 11 (generic LLM personalization) | 1 |
| fresh-news | News Recency | At least one news retrieval is dated within the last 30 days. The writer has recent, specific material to cite and should produce a hook that is grounded in a concrete, recent event. | Pitfall 4 (composition skewed to easy cases) | 1 |
| mixed-news | News Recency | News retrievals span a range: some are recent (within 90 days) and some are older. The writer must discriminate between fresh and stale signals; hooks that cite only the stale items should score lower on the recency axis. | Pitfall 4 (composition skewed to easy cases); Pitfall 11 (generic LLM personalization) | 1 |
| icp-clear-yes | ICP Fit | The account matches the ICP rubric criteria strongly across multiple axes. A well-calibrated judge should score icp_relevance high (4-5). Useful for verifying the judge does not uniformly suppress high scores. | Pitfall 4 (composition skewed to easy cases) | 1 |
| icp-clear-no | ICP Fit | The account clearly does not match the ICP rubric: it may be in the wrong stage, wrong channel posture, or show signals that explicitly contradict the rubric criteria. Judge should score icp_relevance low (1-2). | Pitfall 4 (composition skewed to easy cases) | 1 |
| icp-borderline | ICP Fit | The account partially satisfies some rubric axes and fails others, making the ICP verdict ambiguous. The label rationale must record which axes tipped the balance. Tests whether the judge handles ambiguity rather than defaulting to the midpoint. | Pitfall 4 (composition skewed to easy cases) | 1 |
| well-known | Public Profile | The account is a large, widely recognized organization with substantial online presence. Exa returns rich, structured content for the about-page and news. This is the easiest retrieval case. | Pitfall 4 (composition skewed to easy cases) | 1 |
| mid-tier | Public Profile | The account has a moderate public footprint: a functional about-page and some news coverage, but not uniformly rich. Retrieval quality is variable. | Pitfall 4 (composition skewed to easy cases) | 1 |
| obscure | Public Profile | The account has thin or fragmented public presence. Exa may return near-empty about-page content or sparse news, pushing retrieval quality toward thin-enrichment. Tests whether the pipeline degrades gracefully. | Pitfall 4 (composition skewed to easy cases) | 1 |
| empty-enrichment | Failure Mode | Both Exa about-page and news retrievals return no usable content for this domain. The pipeline should mark the account unscoreable and emit no outreach hook. If a hook is present in the record, it was produced from a fallback path and its grounding cannot be verified. | Pitfall 4 (composition skewed to easy cases); Pitfall 14 (empty enrichment path untested) | 1 |
| blocked-scrape | Failure Mode | The Browserbase fallback was invoked for this domain and returned a blocked or empty response. The pipeline was unable to retrieve JS-rendered content. Tests that the pipeline logs and continues rather than failing the run. | Pitfall 4 (composition skewed to easy cases); Pitfall 9 (demo-day resilience via blocked-scrape path) | 1 |
| no-recent-news | Failure Mode | No news within the Exa 90-day window was returned for this domain. Distinct from stale-news in intent: this cell captures the failure-mode path where the news retrieval returns zero items, not just older items. The writer must produce a hook without recency-grounded evidence. | Pitfall 4 (composition skewed to easy cases); Pitfall 11 (generic LLM personalization) | 1 |
| partial-citation-laundering | Failure Mode | The hook contains at least one valid citation marker but also includes claims that cannot be traced to any retrieved justification. One real cite passes the structural guard in src/outreach.py while fabricated claims ride alongside it. The groundedness label should be low (1-2). | Pitfall 1 (partial-citation laundering: one good cite, three fabricated claims) | 1 |
| generic-but-grounded | Failure Mode | The hook cites a real retrieval but the claim is generic and non-specific: a phrase like "fast-growing company in the sector" that is technically supported but provides no information a reader could not already assume. The groundedness label may be moderate (2-3) while personalization and specificity labels are low. | Pitfall 11 (generic LLM personalization: groundedness not sufficient) | 1 |
| judge-failed | Failure Mode | The judge call for this record failed to produce a parseable response, triggering the eval_failed sentinel. The record's eval_failed field is true. This cell tests that the harness distinguishes judge failure from writer failure and does not conflate the two. | Pitfall 5 (judge=1 sentinel collision: failed-judge looks like fully-hallucinated) | 1 |

## Size Rationale

The labeled set is sized to fill every coverage-matrix cell with at least one example and reserve
a roughly 30% holdout slice. With 18 cells each requiring at least one example, a set of 25 to 40
total records provides enough margin for the holdout to have representation across cells. This
follows Pitfall 4 guidance: twenty well-distributed examples beat fifty over-sampled from the easy
quadrant. The size is not a round number target; it is a consequence of the matrix.

The arithmetic is straightforward: 18 cells at minimum one example each implies at least 18 records
in the training slice. Adding a 30% holdout means the full set needs at least 26 records (ceiling of
18 / 0.70) to guarantee every cell appears at least once in the training slice. A set of 25 to 40
records satisfies this bound while remaining a manageable labeling commitment. If natural pipeline
output does not cover every failure-mode cell, known gaps are documented below rather than filled
with synthetic examples (per D-02: all-real provenance).

## Train/Holdout Split Policy

The split is recorded as a `split` field on every record in `evals/labeled.jsonl`, taking values
`"train"` or `"holdout"`. Assignment is deterministic and reproducible from the data alone: each
record's `id` is hashed with a seeded hash targeting a roughly 30% holdout fraction. The seed
value is `"poc-eval-v1"` (SPLIT_SALT). Any implementation that hashes `SPLIT_SALT + record_id`
and assigns holdout when `hash(value) % 10 < 3` reproduces the same split without any external
state.

Process commitment: the holdout slice is never inspected during prompt iteration. When iterating
on the writer or judge prompt, only records with `split == "train"` are examined. The headline
groundedness number reported in any artifact (Phase 4 REPORT.md, any README reference) is the
holdout-slice number only. This is a process commitment recorded here; there is no code assertion
that enforces it. Developer discipline is the only control (see threat register T-03-03-01).

Practically: before any prompt change is tested, the holdout records are set aside. After a
training-slice score stops improving, the holdout is scored exactly once to produce the headline
number. Re-scoring the holdout to chase a higher number defeats its purpose.

## Known Coverage Gaps

Real pipeline output may not naturally produce every failure-mode cell. Where a gap exists, it is
documented here rather than backfilled with synthetic data (D-02: all-real provenance; D-04: gaps
are recorded honestly). This honesty is itself part of the rigor claim: "Known gaps do not invalidate
the eval; they bound the claim. COVERAGE.md is the evidence that the claim is bounded, not hidden."

Outcome of the 2026-05-16 source run (10 domains, 25 labeled records). 17 of 18 cells are
covered by real-provenance records. The single remaining gap is recorded honestly below rather
than backfilled with synthetic data (D-02: all-real provenance; D-04: gaps recorded honestly).

- **empty-enrichment**: COVERED. The warbyparker source domain returned only an
  investor-relations page; enrichment was too thin to support any claim and all hooks were
  suppressed. The example09-vp-cx record (empty paragraph, no citations) anchors this cell as a
  real-provenance empty-enrichment example.

- **blocked-scrape**: KNOWN GAP (this run). No domain in `inputs/accounts.csv` triggered a
  Browserbase blocked or empty response during the 2026-05-16 source run, so no real-provenance
  record exists for this cell. Per D-02 it is not backfilled with synthetic data. The failure
  mode is covered by the integration test layer instead (Pitfall 9 mitigation): the pipeline
  logs the block and continues rather than failing the run. This gap bounds the eval claim (the
  judge's behavior on a blocked-scrape hook is not measured by the labeled set); it does not
  indicate the pipeline mishandles the path.

- **judge-failed**: COVERED. Natural pipeline runs rarely produce judge failures, and the
  2026-05-16 run produced none. Per the COVERAGE.md provision for a constructed sentinel, the
  example10-judge-failed record reuses the example10-cto grounded paragraph and justifications
  with `eval_failed: true` and all five axes at the sentinel floor. This record exists to verify
  the harness distinguishes judge failure from writer fabrication (Pitfall 5); it is the only
  constructed record in the set and it reuses real-provenance content.

## Cross-Family Calibration Note

Pitfall 2 (judge-writer collusion: same model family, similar blind spots) is addressed by a
separate cross-family calibration run, not by a coverage-matrix cell. The calibration run scores
all records in `evals/labeled.jsonl` with both the DeepSeek judge and a cross-family judge
(`moonshot-v1-32k`; the originally-intended `bytedance/seed-oss-36b-instruct` reasoning model
timed out repeatedly on the free endpoint and was substituted), then records Cohen's kappa and raw
percentage agreement per
axis (groundedness, icp_relevance, personalization, specificity, recency). Results are written to
`evals/CALIBRATION.md` as a Phase 3 output artifact. Phase 4's narrative consumes these numbers
verbatim when answering the cross-family question (NARR-02). If inter-judge agreement is low, that
finding is reported honestly in the narrative rather than suppressed; the purpose of the calibration
run is to surface the bound, not to validate a number.
