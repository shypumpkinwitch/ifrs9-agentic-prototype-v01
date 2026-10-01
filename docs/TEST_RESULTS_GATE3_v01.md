# Gate 3 test results v01

Final Gate 3 verification ran on 30 September 2026 with the supplied private corpus path enabled by the application's detected local bundle.

## Final results

| Check | Actual result |
|---|---|
| Full unit and Streamlit harness suite | `Ran 34 tests in 1.276s` — `OK` |
| Private Gate 3 tests | All passed; none skipped |
| In-memory syntax compile | `Compiled 17 project Python files in memory: OK` |
| Dependency consistency | `No broken requirements found.` |
| Live Streamlit server | Health endpoint returned HTTP `200` with body `ok`; server then stopped |
| Post-test private artifact audit | 76 records, 76 unique chunk IDs, no supplied frozen-file hash mismatches |
| Public-code secret-pattern scan | No matches outside `.venv`, `private_data`, and test fixtures |

The Streamlit harness emitted its expected bare-mode `missing ScriptRunContext` warning. Both UI tests passed: one with the detected private corpus enabled and one with private mode disabled.

## Audit-closure recheck

After installing the separately supplied label-audit CSV and correcting the hash-method distinction, only the relevant integrity checks were rerun, as requested:

| Check | Actual result |
|---|---|
| Focused private integrity plus private-mode UI suite | `Ran 8 tests in 1.105s` — `OK` |
| Changed-file syntax compile | `Compiled 4 changed Python files in memory: OK` |
| Corpus structure | 76 records; 76 unique chunk IDs |
| Canonical content versus manifest | Exact SHA-256 match |
| Manifest-referenced frozen files | Five present; five hash matches; none missing or mismatched |

## Private-path assertions that passed

- The actual corpus contains 76 records with 76 unique `chunk_id` values.
- Raw source metadata is retained: `Company Annual Report` and `Company disclosure` are not rewritten in the private file.
- The canonical `COMPANY_DISCLOSURE` class is derived only in memory for guardrails.
- Missing `source_id` fields on 48 records are preserved as missing rather than reconstructed.
- Raw file-byte and canonical parsed-JSON content hashes are computed and labelled separately.
- The canonical content hash reproduces the historical manifest exactly.
- All five manifest-referenced frozen files match their recorded byte hashes.
- Historical BM25/Semantic values are read directly from `holdout_summary_v02.csv` and are not recomputed.
- The flagship top five are Allied_REIT chunks and contain loan-related local evidence; RBC is candidate-only in that run.
- A separate banking-policy scenario retrieves Royal Bank of Canada chunks and marks RBC inspected.
- Allied_REIT and RBC framework statuses remain pending.
- Downloadable traces contain evidence metadata but no annual-report `text` fields.
- Draft generation abstains, model token count is zero, and provider cost is US$0.
- Hash snapshots before and after the private tests are identical for every supplied bundle file.

## Closed audit issues

- Raw corpus file-byte SHA-256: `105EEFBDFF84FDCA8F7B0AD82F8F3756352B6C4394F73EDED983CF0E578BE76D`.
- Canonical parsed-JSON content SHA-256: `5510608D47202AFE75F875EAA8FBAF28933C92D84D9AED2DAB18912C8410768E`.
- Historical manifest corpus SHA-256: `5510608D47202AFE75F875EAA8FBAF28933C92D84D9AED2DAB18912C8410768E`.
- Installed `all_76_chunk_label_audit_frozen_v01.csv` SHA-256: `CBC1B2C7799A3CB368C61BFA8F045D89749047AF0A5D939063EECEBB8BB4EF0A`, matching the manifest.

The corpus, frozen labels, manifest, and historical metrics were not altered.

## Gate status

Gate 3 closed with these results before Gate 4 began. The later Gate 4 work did not modify the frozen inputs; see `TEST_RESULTS_GATE4_v01.md` for current acceptance evidence.
