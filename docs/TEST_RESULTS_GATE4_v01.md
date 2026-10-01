# Gate 4 test results v01

Gate 4 acceptance testing ran on 30 September 2026 with the detected private corpus enabled. No test was skipped.

## Outcome

| Check | Result |
|---|---|
| Full suite: `python -m unittest discover -s tests -v` | 47 passed; 0 failed; 0 errors; 0 skipped |
| Streamlit AppTest | Private flagship and public-fixture modes passed |
| Live headless Streamlit health endpoint | HTTP 200, body `ok` |
| Gate 4 evaluation artifact | Five unique development/control cases; separate from the frozen holdout |
| Recorded trace privacy | Metadata only; no retrieved source `text` field |

## Gate 4 controls exercised

- Exact seven-tool registry.
- Six-step maximum and final-step reservation for a structured stop.
- Exact duplicate-call blocking.
- Safe early stop for an unsupported scenario.
- Safe stop when a planner supplies an invalid tool sequence or argument set.
- OpenRouter planner adapter with injected test transport, including usage/cost capture.
- Raw source-body prompt injection absent from the planner payload.
- Safe trace export with every private evidence body removed.
- Company disclosure blocked from establishing a general IFRS requirement.
- Prohibited client/audit judgment absent from the handoff.
- Reporting-framework status retained as `pending`.

## Scenario acceptance results

The flagship property-development-loan run used the labelled `deterministic fallback workflow` because `OPENROUTER_API_KEY` was not present. It executed six actual local tool calls. Allied_REIT was rated strong (1.000) and selected with evidence from PDF pages 150, 41, and 132. Royal Bank of Canada was rated partial (0.525) because it supplied secondary lending/ECL features but did not match the property-development business model or construction/leasing dimension. Barrick was weak (0.250).

The banking scenario rated Royal Bank of Canada strong and Allied_REIT weak. The unsupported token-minting scenario requested clarification/evidence and stopped after three steps. The authority-confusion scenario did not convert company disclosure into an IFRS requirement or final audit judgment.

No live OpenRouter request was made, and the acceptance run recorded 0 input tokens, 0 output tokens, and US$0 provider cost. The model planner is covered by a mocked transport test; this report does not fabricate a live model action.

## Post-test private-input integrity

| Item | Result |
|---|---|
| Corpus records / unique chunk IDs | 76 / 76 |
| Raw transferred-file SHA-256 | `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d` |
| Canonical JSON content SHA-256 | `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e` |
| Historical manifest corpus SHA-256 | `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e` |
| Canonical hash matches manifest | Yes |
| Missing manifest-referenced frozen files | None |
| Mismatched manifest-referenced frozen files | None |
| Frozen label-audit CSV hash | `cbc1b2c7799a3cb368c61bfa8f045d89749047af0a5d939063eecebb8bb4ef0a` (match) |

The corpus, frozen labels, freeze manifest, historical metrics, and frozen holdout results were not modified or recomputed during Gate 4.
