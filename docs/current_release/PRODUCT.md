# Product documentation — post-hardening release

## Persona

The primary persona is an external auditor or accounting researcher who has a client fact pattern but may not know a relevant comparable issuer. The user needs a defensible research starting point, visible source provenance and explicit evidence gaps—not an automated accounting conclusion. Secondary users are reviewers, instructors and developers who inspect the bounded trace and reproduce offline tests.

## Input

- A narrative audit scenario. Optional topic, industry, transaction and reporting-period hints may help search but cannot override an out-of-scope scenario.
- A required reporting-framework preference, currently IASB IFRS for the flagship workflow.
- An optional local `working_corpus_v01.json` containing 76 frozen annual-report chunks. It stays under `private_data/`, is read-only and is not required for the public fixture.
- Optional environment credentials for separately authorised OpenRouter or SEC experiments. Credentials are never user-facing output and are not stored.

The current router distinguishes development/project loans, banking loans, trade receivables, amortised-cost debt investments, lease receivables and guarantees/commitments. Unsupported or mixed accounting scopes request clarification or stop instead of being forced into a generic ECL path.

## Output

The UI returns:

1. scenario scope, business category, instrument and research topics;
2. concise official IFRS authority cards with official links and verified paragraph references where available;
3. local retrieval provenance and explicitly labelled BM25 retrieval scores;
4. comparator ratings across business, instrument, counterparty, collateral, construction/leasing and ECL dimensions;
5. reporting-framework status, including pending when issuer-specific evidence is insufficient;
6. evidence gaps and safe abstentions;
7. a separated handoff: **What official IFRS sources indicate**, **How comparable companies disclosed similar exposures**, **Evidence gaps / limitations**, and **Auditor judgement / further review required**;
8. a sanitized machine-readable trace that omits raw report and filing text.

## High-level architecture

The application is offline-first. `app.py` coordinates display. `schemas.py` validates records and requests. `scenario_routing.py` determines scope and instrument from the scenario itself. `authority_registry.py` retrieves structured, non-verbatim official-source cards. `retrieval.py` and `agent_tools.py` perform local BM25 search and feature extraction. `agent_loop_hardened.py` enforces legal state transitions, step limits, candidate scope, required authority/comparability checks and safe stopping. `agent_planner.py` optionally selects from controller-exposed tools using sanitized state only.

External discovery is a separate bounded lane in `external_discovery.py` and `external_discovery_ifrs.py`. It targets explicit SEC metadata/filing URLs, stores bodies only under `external_runtime/`, verifies issuer-specific framework evidence, and returns structured metadata to the controller. It is not unrestricted browsing and is not invoked by ordinary offline reproduction.

Authority and company practice stay separate. Company disclosure cannot establish an IFRS requirement. IFRS Foundation supporting or educational material is not labelled as Standard text. Professional interpretation is reported as unavailable. Raw annual-report, SEC filing and IFRS source text never enters planner payloads.

## Target metrics and acceptance criteria

No undocumented numerical target has been retroactively invented. The verified target measures are:

| Product objective | Target/acceptance measure |
| --- | --- |
| Retrieval relevance | Track Hit@1 and Hit@5 on the frozen 38-question holdout, separately for BM25 and the historical semantic baseline. |
| Frozen-data integrity | 76 records, 76 unique chunk IDs, canonical corpus hash matching the historical manifest, and all frozen reference files byte-matching their manifest. |
| Authority separation | Never promote company disclosure or educational material to IFRS Standard authority; never invent paragraph references. |
| Privacy | Zero raw annual-report, filing or IFRS source text in planner payloads or public-safe trace downloads. |
| Bounded agency | Controller-owned transitions, duplicate-call blocking, six-step local cap and ten-step external cap. |
| Scenario safety | Correctly stop unsupported scope, surface authority gaps, avoid comparator selection from generic ECL co-occurrence, and retain auditor review. |
| Release regression | All current-version functional/integrity tests pass; preserved historical snapshot differences remain explicit. |

## Achieved metrics and evidence

| Evidence layer | Verified result | Interpretation |
| --- | --- | --- |
| Frozen retrieval holdout | BM25 Hit@1 71.1% (27/38); Hit@5 97.4% (37/38). Semantic Hit@1 34.2% (13/38); Hit@5 73.7% (28/38). | Historical fixed-corpus retrieval only; not recomputed after agent hardening. |
| Corpus/freeze integrity | 76 records; 76 unique IDs; canonical hash matches; 88/88 protected post-hardening artifacts match. | Integrity/provenance result, not model quality. |
| Grounding pilot | Historical reported 4/4 using self-authored educational material; 311 input and 149 output tokens; provider cost USD 0.00013605. | Not private annual-report text; source prompts/outputs unavailable, so not reproduced or revalidated. |
| Gate 4.5 | Three live planner cases; partial failure preserved. | Exposed real loop/control weaknesses. |
| Gate 4.6 | Three live controller-governed cases completed with the real planner. | Small workflow validation, not a benchmark. |
| Gate 5 | One bounded live SEC/model flagship discovery. | Demonstrated discovery plus honest rejection/partial comparison. |
| Gate 5.1 | One IFRS-targeted live SEC/model flagship run. | Verified IASB-IFRS candidates; Logistic Properties retained only as partial. Post-live Shinhan hardening was offline only. |
| Eight-scenario post-fix regression | Focused routing/UI suite: 20/20 passed. | Diagnostic regression over known frozen cases; not independent unseen-holdout performance and not a manual accounting-quality score. |
| Current release verification | 127/127 current-version tests passed; 0 failed/errors/skipped. | Functional and integrity regression for the current version. Four separate legacy snapshot checks retain expected hash errors. |

The six v1.1 manual dimensions remain unscored/pending. Therefore the project does not claim an eight-scenario pass rate, a weighted agent score or statistical generalisation.

## Product limitations and review boundary

The authority registry is deliberately small. It does not contain complete IFRS Standards or professional commentary. Several instrument-specific questions remain unsupported. Candidate discovery may miss issuers, and framework phrase matching requires issuer-specific review. Comparable-company disclosures illustrate practice only. Auditor review of licensed IFRS material and original filings is mandatory before any accounting or audit conclusion.
