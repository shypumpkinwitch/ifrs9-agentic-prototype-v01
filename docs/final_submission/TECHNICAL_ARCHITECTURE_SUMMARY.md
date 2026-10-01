# Technical architecture summary

| Layer | Responsibility | Boundary |
|---|---|---|
| Streamlit UI | Scenario intake, evidence display, recorded demo synthesis, handoff | No automatic external discovery in Gate 6 |
| Local retrieval | Dependency-free BM25 over public fixture or optional private corpus | Source bodies remain local |
| Planner | Optional OpenRouter-compatible next-action selection | Structured allowlisted payload only |
| Controller | Legal states/tools, scope, duplicates, step cap, safe stop | Overrides invalid planner sequencing |
| Local tools | Analysis, search, metadata, comparability, authority, handoff | Read-only |
| External lane | Bounded SEC metadata/download/local inspection | Separate from frozen corpus; not run in Gate 6 |
| Release audit | Public-tree, credentials, hashes, optional private integrity | Does not replace platform secret scanning |

## Data flow

1. The user supplies an audit scenario.
2. The controller exposes only the legal next tool.
3. Retrieval and source-body feature extraction happen locally.
4. If model planning is enabled, the outbound gate checks structured payloads against source bodies before transport.
5. The controller executes an allowlisted read-only tool and records a concise action/reason summary.
6. Comparability uses explicit dimensions, not keyword overlap alone.
7. Authority classes and missing evidence are reported before stopping.
8. The output is a research handoff requiring auditor review.

## Controller lesson

Gate 4.5 showed that instructions alone did not reliably produce the required order: the model skipped initial analysis and repeated an evidence request. Gate 4.6 moved workflow legality into a state machine, exposed only state-legal tools, and made candidate scope controller-owned. Three subsequent live cases completed their intended flows without fallback.

## External lane

Gate 5/5.1 permits only explicit SEC targets, caps candidates and steps, blocks duplicates, and stores full filings only under `external_runtime/`. Form 20-F is a discovery filter, not proof of IFRS. Issuer-specific evidence is required. The Gate 6 UI displays a sanitized recorded snapshot and makes no new discovery call.
