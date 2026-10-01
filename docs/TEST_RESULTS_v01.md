# Test results v01

Final verification was run locally on 30 September 2026 with Python 3.12.14 and Streamlit 1.50.0 in the project-local `.venv`.

## Passed

| Check | Actual result |
|---|---|
| Standard-library unit and UI suite | `Ran 26 tests in 1.095s` — `OK` |
| Streamlit test harness | App loaded, flagship form submitted, no exception, and all five result tabs rendered |
| Live Streamlit server | `GET http://localhost:8501/_stcore/health` returned HTTP `200` with body `ok`; server was then stopped |
| In-memory Python syntax compilation | `Compiled 15 project Python files in memory: OK` |
| Installed dependency consistency | `No broken requirements found.` |
| Non-test secret-pattern scan | No matches outside `.venv`; `.env.example` contains only a placeholder comment |
| Private/output directory inspection | Only the two `.gitkeep` marker files are present |

The 26 tests cover registry and corpus validation, duplicate IDs, the required 76-record private-corpus count, read-only private-corpus hashing, BM25 behavior, pending/excluded framework handling, unsupported-case abstention, safe starting links, source-ID validation, authority confusion, outbound payload capture, unapproved/unverified card rejection, possible path/secret rejection, four-step cap, argument-size ceiling, duplicate tool calls, prompt-injection isolation, historical-metric immutability, scenario labels, the pending grounding-review sheet, and the Streamlit flagship form.

The Streamlit harness emitted its documented bare-mode `missing ScriptRunContext` warning; the test itself passed and the separate live-server health check also passed.

## Failed setup check and resolution

An initial `compileall` attempt using a minimal Python 3.13 runtime failed because that runtime could not create `__pycache__` directories. It did not report a source syntax error. The final verification used an in-memory compile over the 15 project Python files, which passed, and the complete test suite executed those modules successfully.

## Explicitly unimplemented or unverified

- Dynamic model-selected tool planning is not implemented. The app truthfully labels the deterministic path `offline workflow`.
- No model API call is implemented; token use and provider cost are zero for the public workflow.
- External issuer discovery and bulk report retrieval are not implemented.
- The real `working_corpus_v01.json` was missing, so its 76 records, uniqueness, page mapping, and retrieval behavior remain unverified. Only the loader was tested with a temporary schema-valid file.
- Official IFRS guidance text is not indexed; only a verified official landing-page link is stored.
- Allied_REIT and RBC reports were not supplied or inspected. Both remain candidate-only with framework status pending.
- Frozen notebooks, ground truth, manifest, holdout files, and prior evaluation outputs were missing and were not recomputed.
- The earlier 4/4 educational-note grounding pilot could not be reproduced because its sentences and source artifacts were missing. Independent human review remains pending.
- The workspace is not a Git repository, so the brief's requested small commits could not be created.
