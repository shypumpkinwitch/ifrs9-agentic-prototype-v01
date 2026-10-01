# Gate 4 bounded agentic research architecture v01

## Status and scope

Gate 4 implements a genuine planner-controller loop over seven explicit, read-only research tools. The controller—not the planner—enforces the allowlist, a maximum of six executed steps, exact duplicate-call blocking, bounded result counts, structured traces, and a mandatory human-review handoff. This phase does not alter or tune against any frozen Gate 3 artifact.

When `OPENROUTER_API_KEY` is present, an OpenRouter model selects the next tool from structured state. When the key is absent, the application uses the separately labelled `deterministic fallback workflow`; it does not claim a model call or simulate token usage.

## Registered tools

1. `analyse_audit_scenario` — extracts accounting topics, business features, instrument types, and evidence needs.
2. `search_private_corpus` — runs local BM25 with `top_k` limited to 1–10 and returns provenance metadata, scores, and non-verbatim local feature flags.
3. `inspect_candidate_metadata` — aggregates candidate provenance and locally derived feature counts for up to five retrieved companies.
4. `assess_comparability` — rates each inspected candidate `strong`, `partial`, `weak`, or `insufficient` across explicit dimensions.
5. `check_authority` — reports present and missing authority classes and keeps company disclosure separate from authoritative IFRS material.
6. `request_more_evidence` — records up to five additional evidence types when the scenario or local evidence is insufficient.
7. `stop_and_summarise` — emits a structured research handoff, limitations, and the human-review requirement; it never issues an audit conclusion.

## Data boundary

The annual-report corpus is opened read-only from the gitignored `private_data/` tree. Raw chunk bodies are used only by local BM25, local feature extraction, and the intentionally collapsed local UI preview. The planner plane receives the user scenario, tool contracts, structured observations, chunk IDs, company/year/page provenance, rankings, scores, authority classes, and non-verbatim feature names/counts. It does not receive annual-report chunk text.

Before each OpenRouter transport call, the serialized payload is checked against the complete local chunk bodies; a detected body is blocked. Downloadable traces use `safe_export()`, which removes every `text` field from retrieved evidence. API keys are read only from the process environment and never written to traces or configuration files.

Source-body prompt injection is therefore outside the planner context. Even malformed or adversarial model decisions remain subject to the read-only allowlist, tool preconditions, duplicate detection, bounded arguments, and the six-step controller cap. Invalid sequences stop safely with a recorded guardrail.

## Comparability policy

The comparability dimensions are business model (25%), instrument type (25%), borrower/counterparty (15%), collateral (15%), construction/leasing (10%), and ECL treatment (10%). A shared mention of IFRS 9 or ECL does not establish economic comparability.

For the flagship property-development-loan scenario, the local run rates `Allied_REIT` strong (1.000), `Royal Bank of Canada` partial (0.525), and `Barrick` weak (0.250). Allied is selected, with actual local evidence on PDF pages 150, 41, and 132. RBC remains secondary because its banking business model and lack of construction/leasing features differ from the scenario. In the separate banking scenario, RBC is strong and Allied is weak.

All candidate reporting-framework statuses remain `pending` unless verified evidence establishes IASB IFRS. The corpus records are preserved unchanged, including absent `source_id` values; runtime provenance uses `chunk_id`, company, year, and PDF page.

## Authority and judgment boundary

The available annual-report evidence is classified as `COMPANY_DISCLOSURE`. It can support a statement about what an issuer reported, but cannot establish a general IFRS requirement. Because no official IFRS text is indexed, every run retains the message `Official IFRS 9 guidance not available in this prototype` and requests `IFRS_FOUNDATION_OFFICIAL` and `PROFESSIONAL_COMMENTARY` where relevant.

The controller removes prohibited audit-judgment wording from planner reasons and rejects any final handoff containing the terms `correct`, `compliant`, or `appropriate`. Every result says that human review is required and that no final audit judgment is provided.

## Evaluation boundary

`data/public_demo/gate4_scenario_eval_v01.json` contains five Gate 4 development/control cases. They are separate from the frozen retrieval holdout and are not used to recompute, tune, or replace the historical BM25/Semantic metrics. The model adapter is tested with an injected transport; no live model call was made because no OpenRouter key was available during acceptance testing.
