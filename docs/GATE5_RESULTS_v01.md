# Gate 5 bounded external comparable-company discovery results v01

## Outcome

Gate 5 completed one counted live flagship run with `openai/gpt-4o-mini` and official SEC EDGAR endpoints. The controller used all ten permitted tool steps, made seven successful SEC requests, inspected two annual filings locally, and did not fall back to the deterministic planner. The scenario named no comparable company.

The discovery lane found three external candidates: Tiptree, Toll Brothers, and the TIAA Real Estate Account. Toll Brothers was retained as a partial economic comparator with material limitations. Tiptree was rejected after inspection, and TIAA was rejected as uninspected when the stricter two-download live-run bound was reached. Allied_REIT remained the stronger, separate local-corpus comparator; no external document was added to its frozen corpus.

## Architecture

The new lane is an explicit ten-state controller rather than an unrestricted browser. It performs scenario analysis, two bounded SEC full-text queries, official submissions-metadata lookup, local downloads, issuer-specific reporting-framework verification, local non-verbatim feature extraction, dimensional comparability, a return to the existing local comparator logic, an authority check, and a human-review handoff.

Only `efts.sec.gov`, `data.sec.gov`, and `www.sec.gov` are permitted. Exact request deduplication, a minimum 0.25-second interval, three-candidate cap, local ignored storage, safe network failure, and the ten-step cap are enforced in code. IFRS Foundation jurisdiction-profile metadata is contextual only and cannot establish an issuer's framework.

## Live candidates and evidence

| Candidate | Filing inspected | Framework result | Outcome |
|---|---|---|---|
| Toll Brothers, Inc. | 2025 Form 10-K, accession `0000794170-25-000112` | US GAAP, verified from issuer-specific filing evidence | Partial, 0.69. Property-development, loans/receivables, borrower, collateral, and construction/leasing features were found; development-partner financing and ECL/SICR features were not. |
| Tiptree Inc. | 2025 Form 10-K, accession `0001393726-26-000009` | US GAAP, verified from issuer-specific filing evidence | Rejected, 0.59. Generic loans, borrower, collateral, construction/leasing, and credit-loss features were found, but property-development business and development-partner financing evidence were insufficient. |
| TIAA Real Estate Account | Discovery and submissions metadata only | Pending / insufficient evidence | Rejected uninspected after the bounded live-run download limit; no comparability claim was made. |

The framework verifier did not infer status from a Form 10-K, jurisdiction, issuer name, exchange, or IFRS terminology. It required a matching issuer-specific basis/auditor phrase and stored only a pattern identifier, offset, and evidence-window hash outside the raw local filing.

The retrieved external materials remain company disclosures. Official IFRS 9 guidance and professional commentary are still missing, and auditor review remains mandatory.

## Sources and trace

- SEC EDGAR full-text search: two explicit feature queries.
- SEC submissions JSON: three issuer metadata requests.
- Tiptree filing: `https://www.sec.gov/Archives/edgar/data/1393726/000139372626000009/tipt-20251231.htm`.
- Toll Brothers filing: `https://www.sec.gov/Archives/edgar/data/794170/000079417025000112/tol-20251031.htm`.

The complete sanitized ten-step trace, seven request records, hashes, identifiers, derived evidence locators, rejection reasons, and privacy assertions are in `GATE5_LIVE_DISCOVERY_AUDIT_v01.json`.

## Usage and failures

The model planner used 39,538 input tokens and 1,284 output tokens. OpenRouter reported a total cost of US$0.00670110.

Before network permission was granted, one sandbox preflight stopped safely after local scenario analysis: it completed no outbound request, received no SEC result, used zero model tokens, and promoted no evidence. It is not counted as the live run. The counted live run had no network or tool failures and no fallback.

## Privacy and evaluation boundaries

Full filing content is stored only under gitignored `external_runtime/`. Neither private annual-report chunks nor external filing text entered any planner payload or sanitized audit. The API key, authorization header, and identifying User-Agent value were not saved.

Gate 5 is a separate workflow evaluation. The frozen 76-chunk corpus and 38-question holdout were not modified, recomputed, or tuned. Gate 4.5 and Gate 4.6 artifacts remain protected. Gate 6 was not started.

## Post-live verification

- Full regression: 68 passed; 0 failed; 0 errors; 0 skipped. The suite ran with both live environment variables isolated, so it made no additional live calls.
- Private corpus integrity: 76 records and 76 unique chunk IDs. Raw byte SHA-256 remained `105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d`; canonical JSON SHA-256 remained `5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e` and matched the freeze manifest. All manifest files were present and hash-matched.
- Gate 4.5/4.6 artifact integrity: all five preserved artifacts retained their pre-Gate-5 SHA-256 values.
- Raw-text and secret scans: no private corpus body or complete downloaded filing body appeared in the Gate 5 audit. The exact configured OpenRouter key and SEC User-Agent values occurred in zero inspected source, test, and documentation files.

## Known limitations

- SEC full-text relevance ranking is term-based and returned two US-GAAP issuers before an uninspected real-estate account; discovery is useful but not yet sector-taxonomy-aware.
- Only primary HTML filing documents are supported in this gate; annual reports incorporated solely as PDF exhibits may remain pending.
- Phrase-pattern framework verification is auditable but does not yet classify every jurisdiction-specific accounting formulation.
- The live run intentionally used a stricter two-filing total download bound; it did not inspect the third candidate.
- External evidence is a research starting point, not an audit conclusion or substitute for authoritative IFRS guidance.
