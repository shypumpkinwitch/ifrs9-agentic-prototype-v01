# Gate 4.5 live model planner validation v01

## Result

Gate 4.5 is recorded as a **partial failure**. All three cases used the real OpenRouter planner with `openai/gpt-4o-mini`, and none silently fell back to the deterministic planner. The privacy controls passed. The authoritative-guidance behavior met its core expectation, but the two comparability cases did not reach `assess_comparability` and therefore did not satisfy their expected research direction.

The live model skipped `analyse_audit_scenario` in every case despite the planner instruction to begin there. In every case it later repeated an identical `request_more_evidence` call. The controller blocked the duplicate and produced a safe human-review handoff. This demonstrates that the controller protections work with real model decisions, while also showing that the current live planner policy is not yet reliable enough for comparator selection.

## Cases

| Case | Steps | Outcome |
|---|---:|---|
| Property-development loan / ECL | 5 | Allied_REIT and Barrick were inspected; RBC was not in the top five. No comparability assessment was made, so Allied was not formally preferred over RBC. Failed expected direction. |
| General banking ECL | 5 | RBC was the first retrieved and inspected candidate, with Allied also inspected. No comparability assessment was made. Failed expected direction. |
| Unsupported authoritative guidance | 3 | Requested official IFRS guidance and IASB publications, did not fabricate authority, then stopped after duplicate-call blocking. Passed core authority behavior with a guardrail intervention. |

All reporting-framework statuses remained `pending`. Company disclosure was never promoted to authoritative IFRS evidence, and no final audit judgment was provided.

## Usage

| Case | Input tokens | Output tokens | Provider-reported cost |
|---|---:|---:|---:|
| Property-development loan / ECL | 7,591 | 404 | US$0.00138105 |
| General banking ECL | 7,866 | 433 | US$0.00143970 |
| Unsupported authoritative guidance | 3,207 | 242 | US$0.00062625 |
| **Total** | **18,664** | **1,079** | **US$0.00344700** |

The provider supplied a cost value for every counted planner call.

## Privacy and evaluation boundary

Before transport, every payload was checked against a strict permitted envelope and against all local source bodies. The planner received the scenario, tool contracts, structured state, provenance metadata, retrieval ranks/scores, authority labels, and locally derived non-verbatim feature counts. It did not receive annual-report chunk text. The saved audit contains neither the API key nor authorization headers, copyrighted source text, or hidden chain-of-thought.

These three live cases are development validations. They are separate from the frozen 38-question retrieval holdout and the deterministic Gate 4 tests. No frozen data was used for planner tuning or recomputed, and no external web discovery was performed.

The detailed sanitized request/response record is in `GATE45_LIVE_PLANNER_AUDIT_v01.json`.

## Post-live regression and integrity

The full regression suite ran after the three live cases with the Streamlit tests explicitly isolated from `OPENROUTER_API_KEY`, preventing additional live calls: **48 passed, 0 failed, 0 errors, 0 skipped**.

The post-test integrity audit again found 76 records and 76 unique chunk IDs. The raw corpus hash remained `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d`; the canonical JSON hash remained `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e` and matched the historical manifest. No manifest-referenced frozen file was missing or mismatched. The environment key was absent from the inspected source and audit artifacts.

Gate 5 and external web discovery were not started.
