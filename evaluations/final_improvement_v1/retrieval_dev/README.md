# Development-only retrieval diagnostic

`run_experiment.py` compares the unchanged production BM25 ranking with a local TF-IDF latent semantic analysis (LSA) diagnostic and a predeclared equal reciprocal-rank fusion (RRF, `k=60`). It uses all 76 local chunks but evaluates only the 12 frozen **development** questions. No fusion weight or LSA dimension search was performed, and the frozen 38-question holdout was not loaded.

## Actual results

| Method | Hit@1 | Hit@5 |
| --- | ---: | ---: |
| Existing BM25 | 9/12 (75.0%) | 11/12 (91.7%) |
| Local LSA diagnostic | 8/12 (66.7%) | 12/12 (100.0%) |
| Equal RRF hybrid | 9/12 (75.0%) | 12/12 (100.0%) |

The mean fraction of question terms found in at least one accepted source chunk was 56.6%. This supports a bounded diagnosis: the small, technical corpus and questions contain substantial exact vocabulary, named-company and instrument overlap that BM25 can exploit. The LSA diagnostic broadened top-five recall but sometimes spread similarity across adjacent same-company chunks, reducing top-rank precision. The historical semantic implementation and its per-query rankings are unavailable, so this experiment does **not** claim to identify the exact causal failure of that historical system or reproduce its scores.

The hybrid recovered the one BM25 development miss at Hit@5 but did not improve Hit@1. With only 12 known development questions and a diagnostic semantic method that is not the historical semantic system, that is not sufficient evidence to change production behavior. BM25 remains the production default; the hybrid is a candidate for a separately frozen future evaluation.

Run locally:

```powershell
& '.\.venv\Scripts\python.exe' evaluations/final_improvement_v1/retrieval_dev/run_experiment.py
```

`results_v1.json` stores only hashes, identifiers, ranks, scores and aggregate metrics—not source text or local paths.
