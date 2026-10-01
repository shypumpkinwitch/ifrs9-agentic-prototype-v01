# Gate 6.1 — Official IFRS Authority Layer

## Scope

Gate 6.1 adds a narrow, public-safe authority layer for the flagship property-development-loan/ECL scenario. It does not ingest the complete IFRS Accounting Standards, store IFRS source bodies, or run external comparable-company discovery.

The registry contains seven structured cards. Each card has an ID, standard, topic, paragraph reference or `pending`, source type, concise non-verbatim verified summary, official URL, authority level, and review status.

## Official IFRS Foundation sources used

- IFRS 9 Financial Instruments official page: `https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/`
- Official IFRS 9 issued-standard PDF used only to verify paragraph references: `https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2022/issued/part-a/ifrs-9-financial-instruments.pdf?bypass=on`
- IFRS 9 supporting-material index: `https://www.ifrs.org/supporting-implementation/supporting-materials-by-ifrs-standards/ifrs-9/`
- IASB educational material on IFRS 9 ECL under uncertainty: `https://www.ifrs.org/news-and-events/news/2020/03/application-of-ifrs-9-in-the-light-of-the-coronavirus-uncertainty/`
- IFRS Interpretations Committee credit-enhancement project/agenda-decision page: `https://www.ifrs.org/projects/completed-projects/2019/credit-enhancement-in-the-measurement-of-expected-credit-losses-ifrs-9/`

Sources were reviewed on 1 October 2026. The application links to the official material but does not reproduce it.

## Verified paragraph references

| Topic | Reference | Card |
|---|---|---|
| ECL recognition scope | IFRS 9 paragraph 5.5.1 | `IFRS9-AUTH-ECL-SCOPE-002` |
| Lifetime versus 12-month ECL | IFRS 9 paragraphs 5.5.3 and 5.5.5 | `IFRS9-AUTH-STAGING-003` |
| Significant increase in credit risk | IFRS 9 paragraph 5.5.9 | `IFRS9-AUTH-SICR-004` |
| ECL measurement and forward-looking inputs | IFRS 9 paragraph 5.5.17 | `IFRS9-AUTH-MEASUREMENT-005` |
| Collateral and credit enhancements | IFRS 9 paragraph B5.5.55 | `IFRS9-AUTH-COLLATERAL-007` |

The official overview and IASB educational-material cards retain `pending` paragraph references. No reference was inferred merely from topic similarity.

## UI and workflow

The flagship sequence is now scenario → IFRS 9 topics → official authority cards → comparable-company research → company disclosures → authority/practice boundary → separated handoff.

The handoff has two explicit sections:

1. `What official IFRS sources indicate`
2. `How comparable companies disclosed similar exposures`

It ends with `Auditor judgement / further review required`.

The UI separately labels IFRS Standard/official authority, IFRS Foundation supporting or educational material, unavailable professional interpretation, and company disclosure.

## Privacy and copyright controls

- Registry records contain non-verbatim summaries and metadata only.
- The loader rejects unexpected fields such as a raw source-text body.
- Supporting or educational material cannot be assigned the Standard-authority label.
- Every registry URL must use the official `ifrs.org` host.
- Planner-safe payloads contain only the nine allowlisted registry fields.
- Raw IFRS Foundation or Standard text is neither stored nor sent to OpenRouter.
- Users must open and review the official licensed source before relying on a card.

## Verification

- Gate 6.1 focused authority and Streamlit tests: 10 passed.
- Complete regression suite: 90 passed; 0 failed; 0 errors; 0 skipped.
- Compile and import checks passed.
- Updated Streamlit build returned a healthy HTTP 200 response in a temporary isolated smoke run.
- Public release/privacy audit passed with zero findings.
- The private corpus remained 76 records with 76 unique chunk IDs; its canonical hash still matched the frozen manifest.
- All 11 ledgered Gate 4 through Gate 5.1 historical artifacts remained hash-identical. Gate 6 historical documents were not edited.
- No SEC live-discovery or OpenRouter call was performed.

## Remaining authority questions

- The cards do not determine whether a particular property-development loan has experienced a significant increase in credit risk; that requires instrument-specific facts and auditor judgement.
- The layer does not determine the appropriate scenarios, weights, forecasts, collateral values, recovery timing, or effective-interest-rate inputs for a client calculation.
- The layer does not cover all scope exceptions, simplified-approach questions, modifications, write-offs, presentation, or IFRS 7 disclosures.
- Professional interpretation is not indexed.
