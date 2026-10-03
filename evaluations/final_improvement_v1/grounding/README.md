# Reproducible generation-grounding evaluation v2

This evaluation supplements, without replacing or altering, an unreproducible historical 4/4 observation with a new, separate six-case live evaluation. Its four source notes are self-authored, non-authoritative `PROJECT_EDUCATIONAL_NOTE` material approved for external API use. Four questions have sufficient evidence; two require exact abstention.

## Actual live result

- Model: `openai/gpt-4o-mini`
- Calls: 6, with no retries
- Automated structural checks: 6/6 passed
- Input tokens: 1,317
- Output tokens: 185
- Provider-reported API cost: US$0.00030855
- Manual factual grounding assessment: **pending human review**

`live_results_v1.json` preserves every model response, extracted citation, per-call token use, provider-reported cost, response metadata, and request hash. `manual_review_checklist_v1.json` keeps factual support, entailment, omission and abstention judgements blank for an independent human reviewer. Automated checks cover citation syntax, source-ID membership, citations outside supplied context, and exact abstention only.

The low-risk request design sends only the notes selected for each case, makes one call per case, uses temperature zero, and caps output at 220 tokens. No savings estimate is claimed because no counterfactual run was performed.

Run only with explicit live-call authorisation:

```powershell
& '.\.venv\Scripts\python.exe' evaluations/final_improvement_v1/grounding/run_grounding_evaluation.py
```

The key is read only from `OPENROUTER_API_KEY`. The script refuses to simulate a live result and checks outbound payloads against local private corpus bodies when available.

## Separate critical-qualification retest v2.1

The original [six-case results](live_results_v1.json) remain unchanged. GRD-03 cited `EDU-FWD-003` correctly but omitted the material condition “when that information is available without undue cost or effort.” Structural citation validity therefore did not establish complete factual grounding.

The [v2.1 result](live_results_v2_1.json) records exactly one new `openai/gpt-4o-mini` call using the unchanged GRD-03 question and `EDU-FWD-003` only. Prompt version `grounding-v2.1-critical-qualification-retention` adds a general instruction to preserve material qualifications, conditions, exceptions and limitations, including conditional language; it does not hardcode the missing phrase into the generation instruction. The other five cases were not rerun and production behavior was not changed.

Original answer:

> Historical experience should be supplemented with reasonable and supportable forward-looking information in an ECL estimate, especially when historical data alone does not reflect expected future conditions [EDU-FWD-003].

Revised answer:

> An ECL estimate should incorporate reasonable and supportable forward-looking information when available without undue cost or effort, and a documented adjustment may be needed when historical experience alone does not represent expected future conditions. [EDU-FWD-003]

The revised answer retains the cost/effort qualification and the source's conditional adjustment. Automated citation and literal phrase-retention checks passed. Assistant source comparison found no unsupported addition; independent human factual review remains pending. This known-case retest does not demonstrate independent general grounding improvement.

Actual usage was 306 input and 47 output tokens, with provider-reported cost US$0.00007410, one call and no retries. The artifact preserves prompt/version, responses, citations, validation scope, usage and before/after hashes of original inputs/results. The original checklist remains unfilled. Its hashes match; no source note, question or expected behavior was altered.

`run_qualification_retest.py` is the separate retest runner and refuses another call when the saved v2.1 artifact exists. Do not execute either live runner during offline reproduction. The sources are approved self-authored educational notes, not authoritative IFRS text; neither source-authority status nor automated checks constitute a professional accounting review.
