# Scenario-routing and comparability hardening: offline regression results

This is defect-correction regression evidence informed by the eight frozen v1.1 cases. It is **not unbiased unseen holdout performance**, not a new Gate and not a new live evaluation. No manual PASS/FAIL scenario score has been fabricated. Original v1/v1.1 cases, manifests, runners, observations and readiness ledgers remain unchanged.

## Confirmed root causes and corrections

1. `ResearchRequest.search_text()` included the selected ECL topic and optional hints. The former authority-topic identifier treated that combined text as scope evidence. Routing now derives exposure and business characteristics from the actual scenario only. UI topic selection defaults to automatic routing; an ECL topic or property hint cannot override a revenue-recognition question. Mixed accounting subjects/exposures request clarification.
2. The local analyzer grouped loans and receivables together and classified property-management lease receivables as development lending. The new shared router distinguishes development/project loans, trade receivables, banking portfolios, amortised-cost debt investments, lease receivables and guarantees/commitments. It uses no evaluation case labels or expected answers.
3. Company-wide feature aggregation and weighted dimensions could turn generic ECL/receivable terms into a selected comparator. Runtime assessment now requires instrument evidence within identifiable local chunks and matching business metadata. Unsuitable candidates are not selected even if the historic dimension formula produces a non-zero contextual score. A banking-policy partial rating in a property scenario remains contextual, not a suitable selected comparator. Other matched exposures are capped at partial pending instrument-specific applicability review.
4. Official-card lookup returned an overview even with no relevant topics, and the final builder/UI unconditionally attached the recorded flagship snapshot. Empty/out-of-scope routing now selects zero cards; the controller prevents irrelevant searches; the handoff independently filters scope leakage. Gate 5.1 metadata is shown only in an explicitly labelled historical flagship panel in Evaluation, never added to current handoffs.
5. The former separated handoff removed the generic missing-official-material flag without recording instrument-specific coverage gaps. Coverage now distinguishes existing curated cards, unanswered instrument-specific questions, unindexed full Standard text and unindexed professional interpretation. Missing coverage results in explicit abstention, without adding paragraph references or sources. Trade/lease routing does not present general-approach SICR/staging cards as instrument-specific requirements.

## Before/after S01–S08

Before results below come from the preserved original v1.1 observations. After results come from the separate post-fix deterministic runner using the unchanged frozen scenario text. Expected labels/topics are not inputs to execution. All scenarios retain auditor review.

| Case | Preserved before result | Post-fix diagnostic result | Steps |
| --- | --- | --- | ---: |
| S01 | Allied_REIT strong; flagship snapshot attached | Allied_REIT strong, pages 41/132/150 retained; seven curated cards; local framework pending; no historical snapshot in current handoff | 6 |
| S02 | Allied_REIT partial for e-commerce receivables | Trade-receivable route; four general cards; explicit simplified-approach/lifetime-ECL/provision-matrix authority gap; no suitable comparator | 6 |
| S03 | Allied_REIT partial for manufacturing receivables | Trade-receivable route; historical-loss, forward-looking and concentration/delinquency research needs; no required general-approach SICR tracking; specific authority gap; no suitable comparator | 6 |
| S04 | RBC strong, but property snapshot also attached | RBC strong; six applicable general cards; unrelated property comparators not strong or selected; no flagship snapshot | 6 |
| S05 | Allied_REIT partial for debt investments | Distinct amortised-cost debt-investment route; general cards plus explicit investment-scope authority gap; no ordinary-loan comparator | 6 |
| S06 | Allied_REIT strong from property/receivable overlap | Lease-receivable route; policy-election/applicability authority gap; Allied_REIT not strong or selected; no development-loan extrapolation | 6 |
| S07 | Allied_REIT partial for guarantees/commitments | Separate guarantee/commitment route; explicit scope/applicability authority gap; no generic-loan comparator | 6 |
| S08 | Local controller stopped, but six ECL cards and property snapshot leaked into handoff | Explicit different-standard scope handoff; zero authority cards; no comparator search, selection or snapshot; only different-standard scope requested | 3 |

There is no claim that a safe abstention is an accounting conclusion. For S02/S03/S05/S06/S07 the output explicitly abstains from an instrument-specific conclusion and reports **no verified suitable comparator within available evidence**. Applicable general cards remain research starting points, not evidence that their treatment applies automatically to the instrument.

## Tests and evaluation honesty

- Targeted routing/authority/controller checks: 28 passed.
- Focused new hardening plus UI tests: 20 passed, zero failed. This includes 15 new hardening checks, 12 independent wording variations within a routing test, UI scope-leak tests, source-feature false-match tests and mocked-model privacy checks. Mocked provider traffic is not live API activity.
- Final **full, unfiltered existing suite**: 126 run; 122 passed; zero assertion failures; **four errors**; zero skipped. The exact four test IDs and errors are saved in `full_suite_results_v1.json`.

The four errors are the original v1/v1.1 manifest/full-replay tests. Each raises `ValueError: Integrity mismatch: app.py` because those frozen readiness manifests include pre-fix mutable application source hashes as well as immutable evidence. This authorised task necessarily changes that source. The manifests and those tests were left unchanged; errors were neither hidden nor converted into passes. Exact replay of those checkpoints requires their original implementation environment. New artifact checks distinguish authorised implementation changes from protected frozen evidence.

The live-execution boundary is unchanged: **zero live OpenRouter calls, zero SEC calls, zero planner input/output tokens and USD 0 API cost in post-fix diagnostics**. The full suite also blocks real socket/URL access; model/network tests use mocks. The frozen retrieval holdout was not executed or tuned, and no historical BM25/semantic metric was recomputed.

## Protected evidence

`protected_artifacts_manifest.json` verifies 88 immutable files, including both evaluation versions' frozen inputs/observations/manifests, original runners/tests, the authority registry, historical Gate evidence, public historical metrics and private frozen inputs. All match. All 11 historical Gate preservation-ledger hashes match. The 76-record private corpus canonical JSON hash matches its historical manifest; no frozen private file mismatch exists. The 50-question retrieval benchmark remains 12 development / 38 holdout.

The five pre-existing runtime files changed are recorded separately with their before hashes. This does not amend the original freeze manifests or claim those source hashes are unchanged. Raw annual-report bodies and source text remain local; sanitized observations contain metadata, provenance, structured non-verbatim authority cards and concise action summaries only.

## Exact files changed

Modified:

- `app.py`
- `src/schemas.py`
- `src/agent_tools.py`
- `src/agent_loop_hardened.py`
- `src/authority_registry.py`
- `tests/test_streamlit_app.py`

Added:

- `src/scenario_routing.py`
- `tests/test_scenario_hardening_postfix.py`
- `evaluations/scenario_hardening_postfix_v1/run_postfix_offline.py`
- `evaluations/scenario_hardening_postfix_v1/run_all_tests_offline.py`
- `evaluations/scenario_hardening_postfix_v1/protected_artifacts_manifest.json`
- `evaluations/scenario_hardening_postfix_v1/postfix_observations_v1.json`
- `evaluations/scenario_hardening_postfix_v1/full_suite_results_v1.json`
- `evaluations/scenario_hardening_postfix_v1/RESULTS.md`
- `evaluations/scenario_hardening_postfix_v1/file_hashes_v1.json`

## Remaining limitations

Routing is conservative rule-based classification, not exhaustive financial-instrument interpretation. Unfamiliar or mixed scenarios may need clarification. Comparability still uses local feature checks and supplied issuer metadata; matches and rejections require human review, and missing business metadata may reject potentially useful disclosures. No new sources or authority cards were added, so the listed instrument-specific questions, full Standard text and professional interpretation remain unsupported. Allied_REIT's reporting framework remains pending. Historical model results are not current live planning or independent evidence of generalisation. The legacy frozen implementation hash checks remain intentionally incompatible with changed application source.

Commands (read-only offline diagnostics):

```powershell
& '.\.venv\Scripts\python.exe' evaluations/scenario_hardening_postfix_v1/run_postfix_offline.py
& '.\.venv\Scripts\python.exe' evaluations/scenario_hardening_postfix_v1/run_all_tests_offline.py
```

Stopped after correction and offline verification. No new Gate or live discovery was started.
