# Auditor Scenario Evaluation v1

This is a separate evaluation of the authority-first auditor research workflow. It must never be pooled with the existing 50-question retrieval bank, its 12 development / 38 frozen holdout split, or historical BM25/semantic metrics. It is also distinct from the generation pilot, Gate 4 deterministic tests and Gates 4.5–5.1 recorded live experiments.

## Frozen inputs and execution order

Exactly eight scenarios, S01–S08, are stored in `cases_frozen_v1.json`. Each has exactly the eight requested fields. `cases.schema.json` defines the structure and `protocol_v1.json` defines the six manual dimensions. `freeze_manifest_v1.json` records SHA-256 hashes over raw bytes for these three files and 71 pre-existing protected files. The freeze was created before any scenario was executed.

Frozen case-file SHA-256:

`33087678fadd578e70e3b6c65327bbf2e2d9dc5ceb2462c2b1d7a8cd844cf31c`

Schema SHA-256:

`c0a7b9ae2cd0931bfc305b4e7cbd372bbd4f5ffbac85a829b27f08d7bd199175`

Protocol SHA-256:

`a22f3d06d4d0843c4c46b08535d0c69cf81ef9cb3662844d58ba5d9c18104f65`

The protected files include application code, the authority registry, prior scenario tests/data, historical metrics, Gate artifacts and the private frozen bundle. Raw corpus byte hashing in this new preservation ledger is distinct from the sorted-key compact canonical JSON hashing used by the historical corpus manifest. Neither original manifest nor corpus was changed.

## Deterministic validation completed

Eight unit tests passed, zero failed. They cover case/schema validation, manifest integrity, tamper detection in temporary copies, pending-review handling, N/A denominators, all-applicable-dimensions scenario passing, and offline execution/privacy/preservation.

The runner exercises the current authority lookup, bounded deterministic company-research controller and separated handoff for every scenario. It uses the actual private corpus read-only when available, otherwise the self-authored public fixture. This recorded run used the private corpus. Socket creation, URL opening and OpenRouter planner activation/selection are blocked. An explicit deterministic planner is passed irrespective of environment credentials.

No OpenRouter or SEC calls were made. Input tokens: 0; output tokens: 0; provider API cost: USD 0. Historical recorded model results are not executions of these eight cases. The original benchmark counts were checked as 50/12/38, without running or tuning the holdout or recomputing any metrics. All 71 protected hashes matched before and after execution.

The requested scenario text is passed unchanged. The topic is the existing UI default, `expected credit losses`; optional industry, transaction and period hints are blank. Expected answers are never injected into the workflow. The runner tests workflow components together; it is not a browser UI evaluation or a live agent/discovery experiment. It reuses preserved recorded external metadata exactly as the application does and does not discover fresh comparators. Raw report/filing bodies are omitted from the observations, and authority cards are existing structured non-verbatim summaries. Timing values are excluded from the deterministic artifact.

## Per-case observations for manual review

These observations are not manual PASS/FAIL judgements. Relevant evidence, source identifiers and concise action traces are in `deterministic_observations_v1.json`.

| Case | Steps | Current local selection | Review issue / boundary |
| --- | ---: | --- | --- |
| S01 | 6 | Allied_REIT, strong | Seven official cards retrieved, including collateral support; issuer framework remains pending. Review the source evidence and applicability. |
| S02 | 6 | Allied_REIT, partial | General impairment cards are retrieved; simplified-approach authority is not curated and the integrated handoff does not explicitly preserve that specific authority gap. E-commerce exposure comparability needs review. |
| S03 | 6 | Allied_REIT, partial | General cards cover ECL/SICR/forward-looking research; manufacturing/customer-concentration comparability is not established by this selection. |
| S04 | 6 | Royal Bank of Canada, strong | Banking selection is appropriate to investigate. The application also attaches recorded flagship property comparables irrespective of scenario; review this distinction. |
| S05 | 6 | Allied_REIT, partial | The workflow uses generic loan/receivable features; debt-investment exposure equivalence and scope applicability require review. |
| S06 | 6 | Allied_REIT, strong | Property/receivable classification yields a strong rating without establishing lease-receivable equivalence. Simplified-approach authority coverage remains unresolved. |
| S07 | 6 | Allied_REIT, partial | Only generic impairment cards are retrieved; the handoff lacks an explicit guarantee/commitment-specific authority-coverage gap. No requirements conclusion is established. |
| S08 | 3 | None | The local controller requests scope clarification and does not search for ECL comparators. However, the UI-default topic still retrieves six general IFRS 9 cards, and the handoff still attaches recorded property comparables. A different-standard scope response is not established. |

All eight retain auditor review. The company-only lane's internal missing-official-material warning describes its frozen corpus, not the separate authority registry. The separated handoff removes that generic warning, but this removal does not establish exposure-specific authority sufficiency. Recorded external metadata attached to the handoff remains recorded evidence; it must not be graded as new discovery success for these scenarios.

## Manual review and reporting

`manual_review_template_v1.json` contains all eight cases and all six dimensions, with statuses `null`. No manual judgement has been fabricated. Copy the template for an actual review and preserve the original template, frozen cases and manifest. For each applicable dimension record PASS or FAIL, a concise reason and evidence identifiers; use N/A only with an explicit reason. A safe supported abstention or authority gap can pass where the frozen case expects it.

`summarise_manual_review` reports per-case results, each dimension's PASS / (PASS + FAIL) rate excluding N/A, and scenario pass count out of eight. All applicable dimensions must pass; no weighted aggregate score is created. Pending review is not N/A and produces no final pass rate or scenario pass count. At this checkpoint all 48 manual cells are pending, so scenario passes and dimension rates are **not yet reported as scores**. This is evaluation readiness, not a claim that eight scenarios passed.

Run from the project environment:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_auditor_scenario_evaluation_v1 -v
& '.\.venv\Scripts\python.exe' evaluations/auditor_scenario_v1/run_deterministic.py
```

The runner is read-only and prints sanitized observations. Future live runs require separate user authorisation and must record steps, model tokens and provider-reported cost separately. No application functionality, authority content, retrieval logic, historical evaluation or recorded live checkpoint was changed for this layer.
