# Provider-cost consolidation v1

`cost_ledger_v1.json` consolidates actual provider-reported usage from the preserved generation pilot, Gate 4.5, Gate 4.6, Gate 5, Gate 5.1, and generation-grounding v2 records. It also records deterministic fallback as zero model calls, zero tokens and US$0 provider cost.

The ledger distinguishes:

- 36 model calls for which call-level token and cost records are preserved;
- per-scenario totals and whether the intended research workflow completed;
- Gate 5 and Gate 5.1 scenario aggregates, whose call-level allocation was not preserved and is therefore left unavailable; and
- deterministic fallback rows, which incur no model API charge.

Recorded comparisons identify avoidable context overhead without inventing pricing: Gate 4.6 used 6,677 fewer input tokens than Gate 4.5 (35.77%), while Gate 5.1 used 26,193 fewer input tokens than Gate 5 (66.25%) and US$0.00440475 less provider-reported cost. These are historical aggregate comparisons across changed workflows, not controlled savings estimates.

Regenerate offline:

```powershell
& '.\.venv\Scripts\python.exe' evaluations/final_improvement_v1/cost/build_cost_ledger.py
```

Provider API cost is not total cost-to-serve; local compute, engineering, storage, governance, source licensing and human review remain outside the ledger.

The preserved v1 ledger predates the single-case qualification retest and is not rewritten to include it. That additional call is recorded separately in [grounding v2.1](../grounding/live_results_v2_1.json): 306 input / 47 output tokens, US$0.00007410 provider-reported cost. Do not treat the ledger's 36 call-level records as an exhaustive count including the retest, or the grounding calls as completed auditor research scenarios.
