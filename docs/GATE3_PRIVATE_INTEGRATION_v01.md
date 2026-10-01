# Gate 3 private-runtime integration audit v01

Audit and integration performed on 30 September 2026. Annual-report chunk bodies are intentionally not reproduced in this document.

## Transfer and extraction

- Supplied ZIP: `PE6201_Codex_Private_Runtime_Inputs_v01.zip`
- ZIP SHA-256: `56F660E6CE4C300DDC66B65BFADF74FC01AA8092BD0211F75D384DC226482132`
- Nine archive entries were checked for rooted paths and `..` traversal before extraction.
- Eight files were extracted beneath the gitignored `private_data/runtime_inputs_v01/PE6201_Codex_Private_Runtime_Inputs_v01/` directory.
- No existing notebook, frozen artifact, evaluation result, or public fixture was overwritten.

The archive's `README_PRIVATE_INPUTS.md` was inspected as reference material. Its content was not treated as a replacement for the user's request.

## Actual corpus structure

`working_corpus_v01.json` was parsed as supplied and was not rewritten.

| Check | Actual result |
|---|---|
| Records | 76 |
| Unique `chunk_id` values | 76 |
| Companies | Royal Bank of Canada 28; Barrick 22; Glencore 15; Allied_REIT 11 |
| `source_type` | `Company Annual Report` for all 76 records |
| Raw `authority_level` | `Company disclosure` for all 76 records |
| Canonical policy class | `COMPANY_DISCLOSURE` derived in memory; raw metadata remains unchanged |
| `source_id` presence | Present on 28 records and absent on 48 records |
| Other supplied fields | `chunk_id`, `source_type`, `authority_level`, `company`, `year`, `pdf_page`, `topic`, and `text` are present on all 76 records |

The earlier specification described `source_id` as present on every record, but the supplied corpus omits it on 48 records, including Allied_REIT. The runtime does not invent replacements. It uses the unique `chunk_id` plus company, year, and page metadata for those records.

## Corpus hash methods

| Value | SHA-256 |
|---|---|
| Raw supplied ZIP-entry bytes | `105EEFBDFF84FDCA8F7B0AD82F8F3756352B6C4394F73EDED983CF0E578BE76D` |
| Raw extracted local file bytes | `105EEFBDFF84FDCA8F7B0AD82F8F3756352B6C4394F73EDED983CF0E578BE76D` |
| Canonical parsed-JSON content | `5510608D47202AFE75F875EAA8FBAF28933C92D84D9AED2DAB18912C8410768E` |
| Frozen manifest's `corpus_sha256` | `5510608D47202AFE75F875EAA8FBAF28933C92D84D9AED2DAB18912C8410768E` |

The two values answer different questions. The raw hash verifies the exact transferred file bytes. The historical manifest uses a parsed-JSON content hash produced with sorted object keys, preserved Unicode, and non-indented Python JSON serialization: `json.dumps(payload, sort_keys=True, ensure_ascii=False)`, encoded as UTF-8 before hashing. That canonical hash reproduces the manifest exactly. Explicitly forcing comma/colon separators produces a different serialization and is therefore not the historical method. No corpus or manifest byte was changed.

## Frozen/reference artifacts

The supplied manifest itself has SHA-256 `5992123739D3008C2D6B2F44BB16495657BE6519714081A830617B851F8F24E8`.

| Manifest-referenced file | Supplied | Hash result |
|---|---:|---|
| `evaluation_question_bank_frozen_v01.json` | Yes | Matches manifest |
| `development_ground_truth_frozen_v01.json` | Yes | Matches manifest |
| `holdout_test_ground_truth_frozen_v01.json` | Yes | Matches manifest |
| `ground_truth_QA_report_frozen_v01.md` | Yes | Matches manifest |
| `all_76_chunk_label_audit_frozen_v01.csv` | Yes, supplied separately | Matches manifest (`CBC1B2C7…EF0A`) |

The bundle also supplies `holdout_summary_v02.csv` (SHA-256 `CE4AA7CCF8B272D714040FD3EC2E06EAA3430F05CAD738796C9AA13A97116645`). The application reads its BM25 and Semantic rows directly and displays them only as the historical fixed-corpus baseline. It does not recompute the metrics or tune against the 38-question holdout.

## Flagship retrieval

Private mode replaces the synthetic public retrieval fixture with the local 76-record corpus. Candidate search identifies Allied_REIT first, and BM25 applies a transparent 1.75 score multiplier to that scenario-matched company while retaining lexical scoring. This scenario-level boost was not selected or adjusted against the frozen holdout. The actual top five in the tested flagship run were:

| Rank | Chunk ID | Company | PDF page |
|---:|---|---|---:|
| 1 | `ALLIED_REIT2025_P150_C04` | Allied_REIT | 150 |
| 2 | `ALLIED_REIT2025_P150_C03` | Allied_REIT | 150 |
| 3 | `ALLIED_REIT2025_P132_C01` | Allied_REIT | 132 |
| 4 | `ALLIED_REIT2025_P41_C01` | Allied_REIT | 41 |
| 5 | `ALLIED_REIT2025_P150_C02` | Allied_REIT | 150 |

Allied_REIT is therefore shown as `indexed and inspected` for that run, while its reporting-framework status remains `pending`. RBC remains a candidate-only banking reference and is explicitly not presumed economically comparable. No RBC chunk is included in the tested flagship top five.

A separate banking-policy scenario ranks RBC first and retrieves Royal Bank of Canada chunks, demonstrating that RBC is used when the scenario is genuinely banking-relevant rather than merely because the flagship query mentions ECL.

## Privacy boundary

- Raw annual-report text is used only for local BM25 and a collapsed local preview.
- Downloadable trace JSON removes every evidence `text` field.
- No private corpus path or raw chunk enters the outbound evidence-card payload.
- No model API is enabled or called; model tokens and provider cost remain zero.
- Draft generation still abstains because no source-verified, externally approved project-authored card supports the retrieved private chunks.

Both Gate 3 audit issues were closed before Gate 4 began: the canonical corpus content hash matches the manifest, and all five manifest-referenced frozen files are present with matching byte hashes. Gate 4 was implemented later without changing these artifacts; see `GATE4_ARCHITECTURE_v01.md`.
