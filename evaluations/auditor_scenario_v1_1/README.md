# Auditor Scenario Evaluation v1.1

This pre-live QA revision supersedes v1 for future scenario evaluation. The original v1 directory, observations, manifest and tests are preserved unchanged. Exactly eight cases remain, with the same case IDs, schema fields and six manual dimensions. No application functionality or authority source content was changed.

## Corrections

- S03: the scenario now uses the supplied manufacturing trade-receivable wording. Expected topics cover trade-receivable ECL, simplified approach / lifetime ECL, historical loss experience or provision-matrix considerations, forward-looking adjustments, and customer concentration and delinquency. Expected authority behaviour explicitly avoids assuming general-approach SICR tracking and retains the official-authority coverage boundary.
- S04: only `since origination` changed to `since initial recognition` in the scenario; all expected behaviour is identical to v1.
- S06: only expected authority behaviour changed. The case now tests the lease-receivable simplified-approach / lifetime-ECL accounting-policy election, requires sufficient official authority before concluding applicability, and retains the gap instead of extrapolating development-loan treatment. It does not imply mandatory simplified-approach treatment for all lease receivables.

S01, S02, S05, S07 and S08 are byte-equivalent as parsed case records to v1. Tests compare every case field and reject unrelated changes.

## Freeze and integrity

`cases_frozen_v1_1.json`, `cases.schema.json` and `protocol_v1_1.json` were hashed into `freeze_manifest_v1_1.json` before any v1.1 execution. The manifest includes parent case/manifest hashes and preserves 82 existing files, including all original v1 files and the pre-existing application/historical inputs.

Case-set SHA-256 (raw bytes):

`a7abb8e51471e4e292fdde3e0a6edb8088bb7b8ec1b95119e82ec1b2ce28482f`

Original v1 case hash remains:

`33087678fadd578e70e3b6c65327bbf2e2d9dc5ceb2462c2b1d7a8cd844cf31c`

`readiness_hashes_v1_1.json` records all new evaluation and test file hashes. Raw byte hashes in this ledger are distinct from the historical corpus manifest's canonical JSON content hash; neither private corpus nor historical manifest was modified.

## Offline validation

All 16 tests passed (8 existing v1 tests and 8 v1.1 tests), zero failed. Tests verify schema, precise corrections, freeze integrity, tamper detection on temporary copies, privacy, deterministic replay and manual-score handling. All eight v1.1 scenarios ran using the existing deterministic planner and read-only private corpus; S01–S07 used six bounded steps and S08 used three.

OpenRouter calls: 0. SEC calls: 0. Model input/output tokens: 0/0. Provider API cost: USD 0. Socket/URL access and OpenRouter planner activation/selection are blocked by the offline runner. Preserved Gate 5.1 metadata is reused as recorded metadata, never claimed as newly discovered evidence.

The historical 50-question retrieval bank, 12 development / 38 frozen holdout split, historical BM25/semantic metrics and all 82 protected file hashes remain unchanged. The retrieval holdout was not executed or tuned. The runner validates protected bytes before and after execution.

`deterministic_observations_v1_1.json` contains sanitized observations and traces only. The runner uses the existing UI-default ECL topic with optional metadata hints blank; expected answers are not fed into it. Evaluation-case correction does not repair application authority coverage or comparability behaviour. The earlier diagnostic concerns remain for manual review: generic cards do not establish exposure-specific simplified-approach coverage, and recorded property-comparator metadata is attached across scenarios. No manual scenario PASS/FAIL judgement is assigned. All 48 dimension cells in `manual_review_template_v1_1.json` remain pending, so there is no claimed scenario pass rate.

Re-run from the project directory:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_auditor_scenario_evaluation_v1 tests.test_auditor_scenario_evaluation_v1_1 -v
& '.\.venv\Scripts\python.exe' evaluations/auditor_scenario_v1_1/run_deterministic.py
```

The runner prints sanitized observations and performs no file writes. This checkpoint stops before any live scenario execution. Any later live run requires separate user authorisation and separate steps, token and provider-cost reporting.
