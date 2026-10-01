# Final report outline and PE6201 rubric evidence map

This document maps existing project evidence to the four supplied PE6201 assessment criteria. It does not add scoring subcriteria or predict marks.

| Official criterion | Existing project evidence to address |
|---|---|
| **Problem Statement & Significance (15%)** | Define the auditor's problem: researching an unfamiliar property-development-loan/ECL scenario without already knowing the comparable issuer. Explain the significance of finding relevant disclosures while preventing company practice from being mistaken for authoritative IFRS requirements. Use the flagship scenario, user journey, authority boundary, and mandatory human-review requirement. |
| **Business & Technical Trade-offs (25%)** | Discuss offline/private handling versus public reproducibility; BM25 transparency versus semantic recall; optional model flexibility versus controller enforcement; bounded SEC discovery versus broad-crawl recall; local filing processing versus operational overhead; and provider API cost versus total cost-to-serve. Use `BUSINESS_TECHNICAL_TRADE_OFFS.md`, `COST_MODEL_SUMMARY.md`, and `LIMITATIONS_RESPONSIBLE_AI.md`. Preserve the distinction between the frozen retrieval evaluation, the generation pilot, agent-workflow tests, and live discovery experiments. |
| **Implementation — code & repository (35%)** | Explain the Streamlit application, local retrieval, source registry, bounded state machines, allowlisted tools, external SEC lane, issuer-specific framework verification, outbound privacy guardrails, release audit, tests, and ignored runtime boundaries. Use the source modules, test suite, README, architecture summary, historical hash ledger, and Gate 6 results. Include Gate 4.5's partial failure and the resulting controller-enforced legal transitions. |
| **Demonstration & Communication (25%)** | Demonstrate the complete workflow from scenario to research handoff. Show Allied_REIT as a strong local comparator with framework status pending, Logistic Properties as a partial verified-IASB-IFRS comparator, rejected financial-institution candidates, source-authority distinctions, historical metrics, actual model/cost records, limitations, and human review. Use `DEMO_RECORDING_SCRIPT.md` and the final Streamlit UI. |

## Report outline using the official criteria

### Problem Statement & Significance (15%)

- Introduce the auditor persona, unfamiliar-transaction problem, and need for independent comparable-company discovery.
- Explain why provenance, economic comparability, reporting framework, and authority level matter to audit research.
- Define the prototype outcome as a structured research handoff rather than an accounting or audit conclusion.

### Business & Technical Trade-offs (25%)

- Evaluate the product and architecture choices documented in `BUSINESS_TECHNICAL_TRADE_OFFS.md`.
- Report actual model/token/API-cost evidence while distinguishing API charges from total cost-to-serve.
- Keep the frozen 38-question retrieval results separate from the generation pilot, deterministic and live agent-workflow tests, and Gate 5/5.1 discovery experiments.
- State the privacy, copyright, source-access, bounded-recall, and human-review implications.

### Implementation — code & repository (35%)

- Describe the local retrieval and optional private-data path, bounded planner/controller loops, explicit tool contracts, source-authority schema, and separate external-discovery lane.
- Explain the progression from fixed-corpus RAG through Gate 5.1, including Gate 4.5's genuine failure and the controller hardening that followed.
- Document tests, release/privacy scanning, ignored runtime paths, frozen-artifact hashes, and reproducible local-run instructions.
- State that the generation grounding pilot used self-authored educational material, not private annual-report text.
- State that post-Gate-5.1 Shinhan hardening was regression-tested offline and did not receive a second live external-discovery run.

### Demonstration & Communication (25%)

- Walk through the flagship scenario using the sequence in `DEMO_RECORDING_SCRIPT.md`.
- Clearly label current local execution versus sanitized recorded external results.
- Present evidence locators and derived metadata without displaying copyrighted source bodies or secrets.
- Close with authority gaps, limitations, the research handoff, and the requirement for independent auditor review.

Do not claim numerical superiority over fixed RAG: no controlled head-to-head outcome evaluation supports that. Do not convert company disclosure into an IFRS requirement conclusion.
