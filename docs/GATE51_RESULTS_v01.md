# Gate 5.1 IFRS-targeted discovery results v01

## Outcome

Gate 5.1 completed one real-model, live-SEC flagship run in ten steps with no fallback or network failure. All three discovered Form 20-F issuers were verified from issuer-specific filing evidence as using IFRS as issued by the IASB; Form 20-F itself was never treated as framework evidence.

The final accepted external result is **Logistic Properties of the Americas — partial comparator (0.89)**. It is a property/real-estate issuer with verified IASB IFRS and locally detected ECL, receivable, collateral, counterparty, and construction/leasing features. The rating is capped at partial because the filing yielded generic loan/receivable evidence rather than development-partner financing evidence.

Shinhan Financial Group and Inter & Co were rejected for the flagship property scenario because SEC SIC metadata identifies financial-institution business models. Their verified IFRS status and ECL disclosures do not make them economically comparable property issuers.

## Live integrity finding and hardening

The preserved live output initially scored Shinhan as a strong comparator because phrase aggregation found property-development and lending terms somewhere in a very large bank filing. This was a genuine post-live integrity failure in the business-model dimension. The live checkpoint was not overwritten and no second live run was performed.

The controller was hardened offline to reject financial-institution SIC candidates before deep property comparison and to cap generic-loan-only property matches at partial. The corrected assessment and its rationale are saved separately from the raw live checkpoint.

## Allied_REIT framework check

Allied_REIT remains `PENDING_INSUFFICIENT_EVIDENCE`. Three frozen chunks contain generic IFRS references, but none of the 11 Allied_REIT chunks provides exact issuer basis-of-preparation or auditor-report evidence establishing IFRS as issued by the IASB.

That result is stored in `external_runtime/gate51_live_v01/source_registry/allied_framework_verification_v01.json`. The frozen corpus was not modified.

## Efficiency

| Run | Input tokens | Output tokens | Provider-reported cost |
|---|---:|---:|---:|
| Gate 5 | 39,538 | 1,284 | US$0.00670110 |
| Gate 5.1 | 13,345 | 491 | US$0.00229635 |

Gate 5.1 reduced input tokens by 26,193, or 66.25%, and provider-reported cost by US$0.00440475. The changes were early framework/business filtering, state-specific one-tool contracts, compact current-step observations, and omission of repeated full history.

## Trace and sources

The exact ten-step flow was: scenario analysis → IFRS-targeted discovery → filing location → local framework-filing download → issuer framework verification/filter → local verified-IFRS search → comparability → separate Allied framework check → authority check → human-review handoff.

Eight official SEC requests completed: two bounded 20-F searches, three submissions-metadata requests, and one current 20-F download per candidate. Full filings remain only in gitignored `external_runtime/`.

## Authority and privacy

All retrieved evidence is company disclosure. Official IFRS 9 guidance and professional commentary remain missing; auditor review is mandatory. Neither private corpus text nor downloaded filing text entered planner payloads or public audit artifacts. Credentials and the identifying SEC User-Agent were not saved.

## Verification

- Deterministic/mock pre-live regression: 74 passed; 0 failed; 0 errors; 0 skipped.
- Post-live full regression: 76 passed; 0 failed; 0 errors; 0 skipped. Live environment variables were isolated, so the tests made no additional live calls.
- Protected-artifact integrity: both accepted Gate 5 artifacts retained their pre-Gate-5.1 hashes. The private corpus remained 76 records / 76 unique chunk IDs; its raw and canonical hashes remained `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d` and `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e`; all manifest files remained present and matched.
- Privacy integrity: no complete private or downloaded filing body appears in the Gate 5.1 audit. The exact configured OpenRouter key and SEC User-Agent values occurred in zero inspected source, test, and documentation artifacts.

## Known limitations

- SEC full-text search is term-based and can surface financial institutions with property-related lending passages.
- SIC classification is a coarse business gate; ambiguous or diversified issuers still require human review.
- Phrase-pattern framework verification is auditable but may leave uncommon basis formulations pending.
- Logistic Properties is only a partial comparator and did not establish development-partner financing.
- No result is an audit conclusion or substitute for authoritative IFRS guidance.

Gate 6 was not started.
