# Gate 4.6 bounded agent-loop hardening results v01

## Result

Gate 4.6 passed. All three re-validation cases used the real OpenRouter planner with `openai/gpt-4o-mini`, completed their intended controller-governed workflow, and used no deterministic fallback. Gate 5 and external web discovery were not started.

The original Gate 4.5 partial-failure files remain byte-for-byte unchanged. The first Gate 4.6 re-validation attempt is also retained as intermediate evidence: its property case exposed a remaining candidate-scope weakness, after which the controller—not the model prompt—was hardened to bind inspection and comparability arguments to the complete candidate set.

## Controller hardening

- Explicit workflow states govern legal transitions from scenario analysis through stopping.
- Each planner request exposes only the tools legal in the current state.
- Scenario analysis is the only valid first action.
- Candidate inspection and comparability scope are controller-owned; the model cannot silently omit a serious candidate.
- Comparable-company paths must complete dimensional comparability and authority checks before a normal handoff.
- Authoritative-guidance paths must check authority and may record one structured evidence-gap signature before stopping.
- Exact duplicate calls and repeated unresolved evidence-gap signatures are blocked.
- Invalid planner output causes a safe emergency stop; only an actual transport failure may activate the existing deterministic fallback.
- Emergency stops cannot manufacture a normal sufficient-evidence handoff.
- The six-step maximum remains enforced.

## Live acceptance cases

| Case | Steps | Tool path | Result |
|---|---:|---|---|
| Property-development loan / ECL | 6 | analyse → search → inspect → compare → authority → stop | Passed. Allied_REIT was strong (0.96); Barrick was weak (0.26). No economic-comparability claim was based on ECL terminology alone. |
| General banking ECL | 6 | analyse → search → inspect → compare → authority → stop | Passed. Royal Bank of Canada was strong (0.88); Allied_REIT was weak for the banking business-model comparison. |
| Unsupported authoritative guidance | 5 | analyse → search → authority → evidence gap → stop | Passed. Company disclosures were rejected as authority, official IFRS evidence was requested, and no requirement was fabricated. |

All candidate reporting-framework statuses remained `pending`. The corpus contains company disclosures but no indexed official IFRS guidance, so the authority boundary remained explicit.

## Usage and token efficiency

| Case | Input tokens | Output tokens | Provider-reported cost |
|---|---:|---:|---:|
| Property-development loan / ECL | 4,719 | 478 | US$0.00099465 |
| General banking ECL | 4,556 | 468 | US$0.00087780 |
| Unsupported authoritative guidance | 2,712 | 396 | US$0.00064440 |
| **Total** | **11,987** | **1,342** | **US$0.00251685** |

Gate 4.5 used 18,664 input tokens. Gate 4.6 used 11,987, a reduction of 6,677 input tokens (35.77%). The reduction came from state-specific tool contracts, current-step observation compaction, and moving static sequencing rules into controller code.

## Privacy and evaluation boundary

Every outbound payload passed the permitted-envelope and source-body checks before transport. The model received scenario data, current legal tool contracts, structured metadata/state, retrieval ranks and scores, authority labels, and locally derived non-verbatim features. It received no annual-report chunk text. The saved evidence excludes the API key, authorization data, copyrighted source text, and hidden chain-of-thought; it retains only concise action/reason summaries and provider usage metadata.

These live development cases remained separate from the frozen 38-question retrieval holdout and the deterministic Gate 4 tests. No frozen holdout result was recomputed or used for tuning.

## Verification

The detailed sanitized live record is in `GATE46_LIVE_PLANNER_AUDIT_v01.json`. The first hardening attempt remains in `GATE46_LIVE_REVALIDATION_ATTEMPT1_v01.json`.

- Full regression: 57 passed; 0 failed; 0 errors; 0 skipped.
- Private corpus integrity: 76 records and 76 unique chunk IDs; raw byte SHA-256 `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d`; canonical JSON SHA-256 `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e`, matching the historical manifest.
- Frozen-artifact integrity: all five manifest-referenced files present and hash-matched; no missing or mismatched file.
- Gate 4.5 failure-artifact integrity: audit JSON SHA-256 `b598918f9bcf50ad091356d60ab6c91ab9fe82ce61c6e1a8c0bafddbcb8dad35`; results Markdown SHA-256 `ca3f57f3edaea6496e9adade4f129f28e146db2932147d988d6fa3eb51d12213`.
- Secret scan: the runtime environment key was available, and its exact value occurred in zero inspected source, test, and documentation artifacts.
- Source-text scan: the Gate 4.6 audit contains none of the 76 private annual-report source bodies.
