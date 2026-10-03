# Data and evaluation guide

## Evaluation layers must remain separate

| Layer | Question answered | Status |
| --- | --- | --- |
| Frozen 50-question retrieval benchmark | Can a retriever rank a labelled relevant chunk at positions 1 or 5 in the fixed 76-chunk corpus? | Historical metrics only; not recomputed. |
| Generation grounding pilot | Were four generated statements grounded in the supplied self-authored educational notes? | Historical reported 4/4; underlying prompts/outputs unavailable. |
| Gate 4–5.1 agent experiments | Can a bounded planner/controller follow the research workflow and perform limited discovery? | Small development/live experiments with separate traces, usage and costs. |
| Auditor Scenario Evaluation v1.1 | Does the application route eight audit scenarios, separate authority/practice, assess comparators and hand off safely? | Frozen offline cases; manual dimensions remain pending. |
| Post-hardening regression | Did known routing/comparability defects stay fixed? | Diagnostic regression over known cases; not unseen-holdout performance. |

No metric from one layer is pooled with another.

## Final improvement evidence release

The separate [final-improvement evaluation directory](../../evaluations/final_improvement_v1/README.md) publishes methods, preserved results and offline tests without changing any frozen benchmark or historical experiment.

- **Retrieval diagnostic:** on the 12 development questions only, BM25 achieved Hit@1 9/12 and Hit@5 11/12; local LSA achieved 8/12 and 12/12; equal RRF achieved 9/12 and 12/12. The historical semantic implementation is unavailable, so LSA is not a reproduction of that baseline. No holdout was accessed or tuned, and production remains BM25.
- **Original grounding v2:** six actual calls (four supported, two insufficient-evidence) passed 6/6 automated citation/abstention structural checks. Usage was 1,317 input / 185 output tokens; provider-reported cost US$0.00030855. All sources are approved self-authored educational notes, not private annual reports or IFRS Standard text. Independent human factual review remains pending.
- **Separate grounding v2.1:** the original GRD-03 valid citation masked an omitted cost/effort qualification. One revised general-prompt call retained “without undue cost or effort,” with unchanged question/source; usage was 306 input / 47 output tokens and cost US$0.00007410. Automated structural/phrase checks and assistant comparison are not independent human review. A retest of one known case is not general grounding performance; original six results and checklist remain unchanged.
- **Cost evidence:** the preserved ledger consolidates 36 call-level records, separately qualified scenario aggregates and zero-cost fallback rows. It predates v2.1; the retest's usage is separately preserved, not silently added to historical totals. Provider cost excludes local compute, engineering, governance, licensing and human review.

The final-evidence release verifies 137 current-version tests (137 passed, zero failures/errors/skips) and 88 protected immutable artifacts. Four unchanged historical-snapshot tests still error on pre-hardening `app.py` hashes; these remain separately reported, not weakened or hidden. Ordinary verification uses the offline release runner and privacy audit below, not any live model or SEC script. Exact retrieval diagnostic reproduction requires the excluded private corpus; grounding prompts, approved educational notes and actual responses are public-safe. No new live calls are part of publication.

## Frozen 50-question retrieval bank

The locally supplied frozen bundle contains:

| Artifact | Purpose | Verified SHA-256 |
| --- | --- | --- |
| `evaluation_question_bank_frozen_v01.json` | All 50 questions and source mappings. | `3a3c22bdcb9e9cd9ca388d9299682ccb37dcb3f7ac2fea7e96226bdd52befd1c` |
| `development_ground_truth_frozen_v01.json` | 12 development questions. | `852578da74b1d91f1ef29874ab3a8e91b54f35ff9ed171280d26d51935c933e6` |
| `holdout_test_ground_truth_frozen_v01.json` | 38 frozen holdout questions. | `5f254597ab2d9b3c99a86271950da3a278763d385db1e2f0728829b530c56d90` |
| `all_76_chunk_label_audit_frozen_v01.csv` | Full 50 × 76 relevance-decision audit (3,800 rows). | `cbc1b2c7799a3cb368c61bfa8f045d89749047af0a5d939063eecebb8bb4ef0a` |
| `ground_truth_QA_report_frozen_v01.md` | Scope/provenance, question revisions, relevance review/scoring and structural checks. | `f9e6f1f41b8df50bf0db83b725e59d57b763d2c2e0ee90776668065807818bf9` |

Each question record has `question_id`, `question`, `company`, `year`, `source_type`, `authority_level`, `pdf_page`, `verified_anchor_id`, `relevant_chunk_ids`, `corpus_version`, `split`, `label_provenance` and `scoring_rule`. The `relevant_chunk_ids` list is the source mapping used for Hit@k. The frozen scoring definition is: any one listed relevant chunk is independently sufficient; labels are not conjunctive multi-chunk requirements.

The label-audit CSV records `question_id`, `chunk_id`, company, PDF page, decision, reason and reviewer provenance for every question–chunk pair. The QA report records pre-freeze question revisions, relevance/scoring review and structural checks. These artifacts are never used to tune the post-hardening router.

A separate [public-safe benchmark export](../../evaluations/public_retrieval_benchmark_v1/README.md) contains all 50 unchanged question strings and every accepted evidence mapping. The JSON preserves nested mappings; the flat CSV has 58 rows. Forty-three questions have one accepted chunk, six have two and one has three. The derivative manifest and integrity report prove equality with the original audit's `Accept` pairs without copying report passages or changing the private freeze.

### Historical retrieval results

| Method | Holdout n | Hit@1 | Hit@5 |
| --- | ---: | ---: | ---: |
| BM25 | 38 | 71.1% (27/38) | 97.4% (37/38) |
| Semantic | 38 | 34.2% (13/38) | 73.7% (28/38) |

The application reads the supplied `holdout_summary_v02.csv`; it does not recompute or tune against the 38-question holdout. The public-safe `data/public_demo/historical_metrics_v01.json` mirrors the numbers as display metadata. Its historical note that evaluation files were absent describes the earlier Gate 1 state; the files are now available only in the local private runtime bundle.

The transferred corpus has raw-byte SHA-256 `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d`. Canonical parsed JSON using sorted keys and compact serialization has SHA-256 `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e`, matching the historical freeze manifest. These are different hashing methods, not evidence of corpus mutation.

## Auditor Scenario Evaluation v1.1

The separate v1.1 evaluation has eight cases, S01–S08, and six manual dimensions:

- scope/topic routing;
- official authority;
- authority separation;
- comparator behaviour;
- framework and comparability;
- safe handoff.

Every applicable dimension must pass for a scenario pass, but all 48 manual cells remain pending. No pass rate or weighted aggregate score is claimed.

The original offline observations exposed deficiencies: the selected ECL topic could influence scope; loans and receivables were grouped too broadly; generic ECL co-occurrence could inflate comparator relevance; an authority overview and recorded property snapshot could leak into unrelated scenarios; and instrument-specific authority gaps were not sufficiently explicit.

The post-fix implementation routes from scenario wording, differentiates instruments, requires instrument evidence and matching business metadata for comparator selection, prevents out-of-scope authority/search leakage, and records instrument-specific gaps and abstentions. S01–S08 post-fix observations are stored in `evaluations/scenario_hardening_postfix_v1/postfix_observations_v1.json`, separate from the original v1 and v1.1 observations.

This regression set is known development evidence. It is **not** an independent unseen holdout, does not repair or re-score the frozen retrieval benchmark, and does not establish accounting correctness. The focused 20-test result establishes software regression behaviour only.

## Reproduction

### Current version-aware release verification

```powershell
& '.\.venv\Scripts\python.exe' evaluations/post_hardening_release_v1/run_release_verification.py
```

Expected current-version category: 127 passed, 0 failed, 0 errors, 0 skipped. Expected historical-baseline category: four executed and four explicit `Integrity mismatch: app.py` errors.

Those four tests remain unchanged and validate the pre-hardening source snapshot. Both legacy validators stop at `app.py`; the version-aware verifier enumerates all five authorised current-source differences and separately checks all 88 immutable artifacts. It does not skip or weaken the historical tests.

### Focused routing/UI regression

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_scenario_hardening_postfix tests.test_streamlit_app -v
```

Expected result: 20 passed.

### Privacy and release audit

```powershell
& '.\.venv\Scripts\python.exe' -m src.release_audit
```

This scans the release-eligible tree, checks required ignore rules, searches for credential patterns and raw-source filenames, verifies the historical Gate ledger, and validates the optional private bundle without emitting source text.

Do not rerun the frozen retrieval holdout, OpenRouter planner or SEC discovery as part of ordinary submission reproduction.

## Public-safe artifact inventory

Available and designed for public submission:

- `data/public_demo/*.json`: self-authored fixtures, historical display metrics, non-verbatim authority cards and sanitized recorded metadata;
- `evaluations/public_retrieval_benchmark_v1/`: all 50 frozen questions, all 58 accepted mappings, schema, integrity report and public derivative manifest, with no source bodies;
- `evaluations/auditor_scenario_v1/` and `evaluations/auditor_scenario_v1_1/`: schemas, cases, protocols, templates, sanitized observations, runners and manifests;
- `evaluations/scenario_hardening_postfix_v1/`: sanitized post-fix diagnostics, test summary and immutable-artifact ledger;
- `evaluations/post_hardening_release_v1/`: current manifest, verifier and explanation;
- `docs/GATE*.md/json` and `docs/final_submission/`: sanitized historical evidence and explanatory documents;
- source code and tests.

Locally available but excluded from the public repository by policy:

- `working_corpus_v01.json` and all annual-report chunk text;
- downloaded SEC filing bodies under `external_runtime/`;
- the original private copies of the retrieval bank, the full 3,800-row label-audit reasons and the private QA/source bundle;
- any raw trace/output containing private previews or paths;
- credentials or the identifying SEC User-Agent.

The public derivative exposes the actual frozen questions and accepted mappings. Exact retrieval reproduction still requires the restricted 76-chunk corpus. The full exclusion-reason audit remains restricted; its decision counts and the exact equality of all 58 accepted pairs are documented and machine-checked. The export's `RESTRICTED_SUBMISSION_NOTE.md` identifies the exact restricted-channel materials; no question record is omitted from the public derivative.
