# Fixed-corpus RAG versus bounded offline workflow

This is a qualitative development comparison, not a new blind evaluation and not evidence of numerical superiority.

| Dimension | Historical fixed-corpus RAG | Bounded offline workflow v01 |
|---|---|---|
| Starting point | A question about a known company in the fixed 76-chunk collection | An unfamiliar transaction/scenario plus optional industry, transaction type, and period |
| Research-step coverage | Retrieval over the existing collection | Candidate metadata search, leading-candidate metadata inspection, local BM25 retrieval, and official-link metadata |
| Evidence collection | Historical company annual-report chunks only | Public mode has only self-authored fixtures; an optional private corpus can be loaded read-only |
| Authority handling | Historical results concern company-report retrieval | Four authority classes are explicit; official link metadata is separate from company disclosure and project notes |
| Citation validity | Historical source mapping supplied by the brief; source files unavailable in this workspace | Draft facts require IDs from evidence retrieved in the same request; invented IDs and company-only general IFRS claims are rejected |
| Candidate/framework control | Not evidenced by the files available here | Candidates show `confirmed`, `pending`, or `excluded`; public real-company candidates remain pending and candidate-only |
| Failure/abstention | No new claim because underlying artifacts are missing | Unsupported cases stop safely; absent verified cards produce `Insufficient approved generation context—human review needed` |
| Tool count | Not available from historical artifacts | Maximum four actual read-only tool calls, recorded in a downloadable trace |
| Latency | Not available from historical artifacts | Measured locally for each run and shown as approximate workflow latency |
| Model cost | Earlier generation pilot cost is historical and separate from retrieval | Zero tokens and US$0 provider cost in offline v01 |
| Privacy boundary | Private corpus status could not be inspected | Raw chunks stay local; outbound payload construction accepts only verified and explicitly approved project-authored cards |

The historical retrieval results remain useful evidence that BM25 was stronger than semantic retrieval on that fixed evaluation. They do not establish how either system performs on the new scenario-level research cases. A future numerical comparison would require a separately designed and frozen evaluation with real inspected sources and independent human review.
