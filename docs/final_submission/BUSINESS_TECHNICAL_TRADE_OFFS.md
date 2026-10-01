# Business and technical trade-offs

| Decision | Benefit | Cost or risk | Control |
|---|---|---|---|
| Offline-first private corpus | Protects copyrighted material | Public reviewers cannot reproduce private text | Synthetic fixture, sanitized metadata, hashes |
| BM25 retrieval | Fast, transparent, dependency-light | Can miss semantic matches | Preserve historical semantic comparison; no holdout tuning |
| Optional planner | Flexible bounded action selection | Model can skip/repeat steps | Controller states, scope, duplicate checks, caps |
| SEC EDGAR first | Official filing metadata | Ranking may return weak/US-GAAP issuers | IFRS constraint and issuer-specific verification |
| Local filing processing | Raw report text stays out of model API | Local processing/pattern limits | Ignored storage, non-verbatim features, pending status |
| Authority classes | Reduces practice-as-requirement risk | Visible evidence gaps | Abstain and request official/professional material |
| Bounded discovery | Auditable requests and cost | Lower recall than crawling | Three candidates, rejection reasons, human follow-up |
| Recorded flagship | Stable and public-safe | Not a fresh live result | Recorded/offline labels and preserved caveat |

Business value is a structured, reviewable research handoff—not automated accounting advice. Professional review, source access, governance, and maintenance are more material than the small recorded API charges.
