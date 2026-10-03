# PE6201 focused final improvement v1

This directory contains three new evaluation layers created after the frozen retrieval benchmark and historical Gate experiments. They do not modify the 50 questions, relevance labels, historical metrics, corpus, or prior experiment records.

## Results at a glance

| Layer | New result | Evaluation status |
| --- | --- | --- |
| Retrieval | On the 12 development questions, BM25 scored 9/12 Hit@1 and 11/12 Hit@5; local LSA scored 8/12 and 12/12; predeclared equal RRF scored 9/12 and 12/12. | Development-only diagnostic. The 38-question holdout was neither accessed nor tuned. |
| Generation grounding | Six live `openai/gpt-4o-mini` calls: four supported questions and two insufficient-evidence cases. All 6/6 passed automated citation/abstention structure checks. | Actual responses and usage saved; manual factual grounding review remains pending. |
| Qualification-retention v2.1 | One revised-prompt GRD-03 retest retained the previously omitted “without undue cost or effort” condition; 306 input / 47 output tokens, US$0.00007410 provider-reported cost. | Known-case retest, separate from the original six results; no general improvement or independent human-review claim. |
| Cost | 36 call-level records consolidated where preserved, plus scenario aggregates and two zero-cost fallback rows. | Actual provider-reported records only; no pricing assumptions or estimated savings. |

## Before and after

| Area | Before | After |
| --- | --- | --- |
| Retrieval evidence | Historical holdout showed BM25 ahead of the historical semantic baseline, but no small reproducible hybrid diagnostic was present. | A local development-only LSA/RRF experiment records rankings and hashes without source text. The production default remains BM25. |
| Grounding evidence | Historical 4/4 result lacked prompts, responses and source artifacts. | Six reproducible cases preserve approved self-authored notes, actual responses, citations, token/cost data, structural checks and a separate human-review checklist. |
| Cost evidence | Stage totals were distributed across historical audit files. | A derived ledger separates individual calls, completed/failed scenarios, scenario-only aggregates and deterministic fallback cost. |

## Integrity boundary

- The frozen 12/38 split and all 50 labels remain unchanged.
- The retrieval experiment reads only the 12 development labels and records `frozen_holdout_accessed = false`.
- Raw annual-report, SEC filing and IFRS source text never enters the grounding payload.
- Grounding sources are project-authored educational notes and are explicitly non-authoritative.
- Automated citation checks are not reported as human factual review.
- No application workflow or production retriever was changed.

See the retrieval, grounding and cost subdirectories for methods, artifacts and reproduction commands.

## Public evidence and reproduction

The [grounding guide](grounding/README.md) links the original six-case results and the separate v2.1 result. The [retrieval guide](retrieval_dev/README.md) explains the development-only experiment and private-input requirement. The [cost guide](cost/README.md) documents ledger coverage and exclusions. JSON results are preserved observations, not files to regenerate during ordinary release verification.

All four grounding notes are approved self-authored project educational material, not annual-report passages or IFRS Standard text. Retrieval outputs contain identifiers, hashes and derived metrics only; cost outputs contain sanitized usage metadata. These publication checks do not grant rights to third-party source bodies. Private corpus and downloaded filing bodies remain excluded. Offline regression tests are `tests/test_final_improvement_v1.py` and `tests/test_grounding_v2_1.py`; use the root README's version-aware release runner without executing live evaluation scripts.
