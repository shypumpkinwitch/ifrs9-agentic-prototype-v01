# Fixed-corpus RAG versus Gate 4 bounded agentic workflow

This is a qualitative development comparison, not a new blind evaluation and not evidence of numerical superiority.

| Dimension | Historical fixed-corpus RAG | Gate 4 bounded workflow |
|---|---|---|
| Starting point | A retrieval question over a known 76-chunk collection | An unfamiliar audit scenario plus optional industry, transaction type, and period |
| Planning | Fixed retrieval procedure | OpenRouter model may select the next read-only tool; a labelled deterministic fallback is used without a key |
| Controller | Not established by the supplied historical metrics | Seven-tool allowlist, six-step cap, duplicate blocking, bounded arguments, invalid-sequence stopping, and trace |
| Retrieval | Historical BM25 and semantic methods | Dependency-free local BM25; no source body enters the planner plane |
| Comparability | Hit against frozen relevance labels | Explicit business, instrument, borrower, collateral, construction/leasing, and ECL dimensions |
| Authority | Company-report retrieval results | Company disclosure is kept separate from official IFRS material and professional commentary |
| Failure mode | Not measured by the new workflow tests | Requests more evidence or stops early; always reserves final judgment for a human |
| Prompt injection | Not reported in the historical baseline | Source-body instructions are not placed in planner context; actions remain controller-governed |
| Cost | Historical generation pilot is separate from retrieval | Fallback acceptance run: 0 model tokens and US$0; model mode logs reported usage/cost |
| Evaluation | Frozen development/holdout artifacts | Five separate Gate 4 development/control cases, not used to tune or recompute the holdout |

The frozen BM25/Semantic figures remain historical baseline results only. Gate 4 demonstrates control flow, evidence handling, comparability discipline, and abstention; it does not claim better retrieval accuracy than the historical system.
