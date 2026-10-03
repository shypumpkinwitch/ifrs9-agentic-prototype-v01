# Hypothetical monthly cost scenario

This is a reproducible illustrative calculation for a small audit team, not a new experiment, a production forecast, or evidence of demonstrated time savings. Historical provider measurements and hypothetical usage/labour assumptions are separated below.

## Actual historical measurement

The single recorded Gate 5.1 live discovery run used `openai/gpt-4o-mini` through OpenRouter and recorded **13,345 input tokens**, **491 output tokens**, and **US$0.00229635 provider-reported API cost**. These existing measurements are copied unchanged; no model pricing or historical cost is recalculated. One run does not establish average production usage.

Original evidence:

- [Gate 5.1 results](../GATE51_RESULTS_v01.md), including efficiency and limitations.
- [Gate 5.1 live discovery audit](../GATE51_LIVE_DISCOVERY_AUDIT_v01.json), `planner_usage` fields `gate51_input_tokens`, `gate51_output_tokens`, and `gate51_provider_cost_usd`.
- [Preserved cost ledger](../../evaluations/final_improvement_v1/cost/cost_ledger_v1.json), Gate 5.1 row in `per_research_scenario.records`.
- [Historical cost/model summary](COST_MODEL_SUMMARY.md).

## Hypothetical assumptions

| Assumption | Illustrative value |
| --- | ---: |
| Research tasks per working day, across the team | 5 |
| Working days per month | 20 |
| Monthly research tasks | 100 |
| Model usage and provider cost per task | Same as the single recorded Gate 5.1 run |
| Auditor labour rate | S$35/hour |
| Manual research and review time per task | 45 minutes |
| AI-assisted research and professional review time per task | 30 minutes |

The assumed 15-minute difference is **not experimentally demonstrated**. Professional review is included in the assumed AI-assisted time, not eliminated. No team headcount or extra model calls are inferred.

## Formulas and monthly cost table

| Quantity | Formula | Illustrative monthly result |
| --- | --- | ---: |
| Research tasks | 5 tasks/day × 20 days/month | 100 tasks |
| Input tokens | 100 × 13,345 | 1,334,500 tokens |
| Output tokens | 100 × 491 | 49,100 tokens |
| Model API cost | 100 × US$0.00229635 | US$0.229635 (approximately US$0.23) |
| Manual labour hours | 100 × 45 ÷ 60 | 75 hours |
| Manual labour cost | 75 hours × S$35/hour | S$2,625 |
| AI-assisted labour hours | 100 × 30 ÷ 60 | 50 hours |
| AI-assisted labour cost | 50 hours × S$35/hour | S$1,750 |
| Hypothetical labour hours saved | 100 × (45 − 30) ÷ 60 | 25 hours |
| Hypothetical labour saving | S$2,625 − S$1,750 | S$875 |

USD API cost and SGD labour amounts are kept separate. No exchange rate is assumed and no cross-currency net saving is calculated. The S$875 figure is a labour-only hypothetical difference, not a measured monetary benefit or total net saving.

## Limitations

- Actual tasks may require different context sizes, steps, retries, model calls or unsuccessful research; Gate 5.1 is one bounded run, not a production average.
- Multiplying its recorded provider cost assumes identical per-task usage and charge. This is not a current tariff quotation or prediction of future prices.
- The 45- and 30-minute assumptions have not been validated by a timed auditor study; no causal productivity improvement is established.
- Freed labour time is not necessarily a cash saving or headcount reduction.
- Provider API cost is not total cost-to-serve. Local compute, hosting, engineering, storage, source licensing, governance, training and operational support are excluded.
- The illustrative labour assumptions do not establish that 30 minutes is adequate professional review for any particular engagement. Independent auditor judgement remains required.
- Historical evidence, frozen benchmark data, evaluation metrics and production behaviour are unchanged. Creating this document requires no live API or SEC calls.
