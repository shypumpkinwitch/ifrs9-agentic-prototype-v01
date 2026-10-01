# Evaluation-results summary

## Frozen retrieval baseline

The frozen company-report holdout contains 38 questions. These results are historical and display-only; Gate 6 did not recompute or tune them.

| Method | Hit@1 | Hit@5 |
|---|---:|---:|
| BM25 | 71.1% (27/38) | 97.4% (37/38) |
| Semantic | 34.2% (13/38) | 73.7% (28/38) |

## Separate workflow evaluations

- The generation grounding pilot used self-authored educational material, not private annual-report text. It is a separate historical pilot and its underlying prompts and outputs were unavailable for reproduction.
- Gate 4 deterministic tests exercised bounded local tools, privacy, authority handling, and safe stopping.
- Gate 4.5 used three real-model cases and produced a genuine partial failure: privacy held, but comparator cases omitted comparability and the model repeated an evidence request.
- Gate 4.6 enforced legal transitions and scope. Three fresh real-model cases completed their intended paths without fallback.
- Gate 5 ran one bounded live SEC discovery; inspected candidates were US GAAP or pending.
- Gate 5.1 ran one IFRS-targeted live discovery. Three issuers were verified as IASB IFRS; Logistic Properties remained a useful partial comparator after review.

## Gate 5.1 integrity caveat

The live output initially over-rated Shinhan using phrase aggregation across a large bank filing. The checkpoint remains preserved. The post-Gate-5.1 SIC-based filtering and generic-loan rating cap were regression-tested offline and did not receive a second live external-discovery run.

These groups answer different questions and must not be combined into one accuracy score.
