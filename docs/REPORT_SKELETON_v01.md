# Project report skeleton v01

## User problem and persona

An auditor beginning with an unfamiliar client transaction needs to find and compare relevant issuer disclosures without confusing company practice with authoritative IFRS requirements.

## Design hypothesis

A bounded read-only research loop may broaden discovery beyond a known-company query while preserving source and authority controls. This prototype does not experimentally prove superiority over fixed-corpus RAG.

## Architecture and trade-offs

- Fixed-corpus BM25 versus bounded discovery workflow
- BM25 versus semantic retrieval historical comparison
- Privacy and copyright boundary
- Authority hierarchy and abstention
- Latency, model-token budget, and cost
- Optional OpenRouter planner versus the labelled deterministic fallback
- Controller-enforced allowlist, six-step cap, duplicate detection, and invalid-sequence stopping
- Planner/local data-plane separation and source-body prompt-injection boundary

## Historical fixed-corpus results

Insert the precomputed values from `historical_metrics_v01.json`, with their source-mapping and label limitations. Do not call them new agent results.

## New development scenarios

Report the five Gate 4 cases in `gate4_scenario_eval_v01.json` as development/control cases, not a blind holdout. Compare candidate selection, provenance validity, abstention, tool count, latency, and cost qualitatively. Do not claim numerical superiority.

## Generation grounding review

Populate `GENERATION_GROUNDING_REVIEW_v01.csv` only when the actual generated sentences and inspected sources are available. Independent human review remains pending until a named reviewer signs it.

## Limitations and future work

Record unavailable official guidance text, pending reporting-framework verification, non-authoritative company disclosures, and whether the run used the model planner or deterministic fallback. The acceptance run used the fallback because no OpenRouter key was available; model behavior is covered by an injected-transport test, not a fabricated live call.

## AI assistance disclosure

Document which implementation and review tasks used AI assistance and which evidence checks were completed by a human. Do not represent assistant review as auditor sign-off.
