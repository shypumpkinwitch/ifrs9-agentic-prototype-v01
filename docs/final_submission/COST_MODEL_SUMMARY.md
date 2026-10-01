# Cost and model summary

Recorded model calls used `openai/gpt-4o-mini` through the OpenRouter-compatible planner.

| Stage | Input | Output | Provider API cost | Qualification |
|---|---:|---:|---:|---|
| Generation pilot | 311 | 149 | US$0.00013605 | Historical reported result using self-authored educational material, not private annual-report text; prompts/outputs unavailable |
| Gate 4.5 | 18,664 | 1,079 | US$0.00344700 | Three cases; partial failure preserved |
| Gate 4.6 | 11,987 | 1,342 | US$0.00251685 | Three hardened cases passed |
| Gate 5 | 39,538 | 1,284 | US$0.00670110 | One bounded live SEC run |
| Gate 5.1 | 13,345 | 491 | US$0.00229635 | One live run; later hardening offline only |

Gate 5.1 reduced Gate 5 input by 26,193 tokens (66.25%) and provider cost by US$0.00440475. API cost is not total cost-to-serve; it excludes local compute, engineering, storage, licensing, governance, and mandatory human review.
