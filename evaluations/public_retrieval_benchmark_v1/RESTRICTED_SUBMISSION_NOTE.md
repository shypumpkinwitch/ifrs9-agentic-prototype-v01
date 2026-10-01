# Restricted submission alternative — do not publish

No frozen question record is excluded from the public-safe export. All 50 question strings and all 58 accepted chunk mappings are available publicly in this directory.

The following supporting material remains restricted:

| Restricted file/material | Reason | Restricted-channel purpose |
| --- | --- | --- |
| `working_corpus_v01.json` | Contains copyrighted annual-report passages. | Required to reproduce BM25/semantic rankings and verify chunk contents. |
| `all_76_chunk_label_audit_frozen_v01.csv` | Contains the full 3,800-row adjudication record and source-review reasons. | Allows detailed review of all 58 Accept and 3,742 Exclude decisions. |
| `ground_truth_QA_report_frozen_v01.md` | Contains private provenance for the source-review/freeze process. | Documents pre-freeze revisions, review scope and structural checks. |
| Original development, holdout and combined question-bank JSON files | Frozen originals remain in the private runtime bundle even though their public-safe question/mapping content is exported. | Permits byte-for-byte comparison with the public derivative. |
| `freeze_manifest_v02.json` and `holdout_summary_v02.csv` | Historical provenance/metric files associated with the restricted source bundle. | Verifies hashes and historical results. |

If the instructor or TA requires exact metric reproduction or independent label adjudication, provide these files only through an authorised restricted course-submission channel. Do not add them to a public repository. Do not include API credentials, the identifying SEC User-Agent, local filesystem paths, or downloaded filing bodies.

The public `export_integrity_report_v1.json` records original hashes, counts and equality checks without exposing the restricted content. The public export is sufficient to inspect the questions, split and accepted source identifiers; it is not sufficient to rerun retrieval without the corpus.
