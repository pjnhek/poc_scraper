# Phase 3: Cross-Family Calibration

**Run date:** 2026-05-16
**DeepSeek judge:** deepseek-v4-flash (thinking enabled, reasoning_effort=medium)
**NVIDIA judge:** moonshot-v1-32k
**Records scored:** 25 (all, including train + holdout; eval_failed excluded from kappa)

## Inter-Judge Agreement (NVIDIA vs DeepSeek)

| Axis | Kappa (linear-weighted) | % Exact Agreement |
|------|------------------------|-------------------|
| groundedness | 0.176 | 16.7% |
| icp_relevance | 0.200 | 29.2% |
| personalization | 0.155 | 37.5% |
| specificity | 0.232 | 33.3% |
| recency | 0.478 | 41.7% |

## Judge Accuracy vs Human Labels

| Axis | DeepSeek kappa vs human (% agree) | NVIDIA kappa vs human (% agree) |
|------|----------------------------------|--------------------------------|
| groundedness | 0.277 (16.7%) | 0.198 (16.7%) |
| icp_relevance | 0.462 (58.3%) | 0.206 (20.8%) |
| personalization | 0.358 (41.7%) | 0.386 (54.2%) |
| specificity | 0.432 (33.3%) | 0.321 (33.3%) |
| recency | 0.450 (33.3%) | 0.505 (45.8%) |

## Notes

- Records scored: 25 (train + holdout combined; D-08 full-set requirement).
- Records excluded from kappa: 1 (expected_eval_failed=True or judge failure).
- DeepSeek judge failures: 0.
- NVIDIA judge failures: 0.
