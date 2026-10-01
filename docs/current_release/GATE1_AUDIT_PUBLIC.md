# Gate 1 workspace audit — public-safe derivative

This is a path-sanitized derivative of the protected historical Gate 1 audit. The original file remains unchanged and is excluded from the public repository because it records personal local filesystem paths.

The audit was performed on 30 September 2026 before implementation. The workspace was empty: no earlier notebook, corpus, frozen ground truth, manifest, holdout record, educational fixture or evaluation-result file was available to inspect. Implementation therefore began in a new application directory using self-authored public fixtures. Historical metrics shown by the application were display-only values from the development specification, not results recomputed at Gate 1.

## File/status matrix

| Item | Gate 1 status | Permitted treatment |
| --- | --- | --- |
| Development specification | Inspected from a local attachment; original local path omitted from this derivative. | Used as the specification; not copied into public fixtures. |
| Earlier MVP notebook | Missing. | Do not claim inspection; do not recreate or overwrite. |
| Earlier demo notebook | Missing. | Do not claim inspection; do not recreate or overwrite. |
| `working_corpus_v01.json` | Missing at Gate 1. | Optional read-only local input when later supplied; never package publicly. |
| Frozen v01 files | Missing at Gate 1. | Do not recompute, reconstruct or overwrite. |
| `freeze_manifest_v02.json` | Missing at Gate 1. | Do not reconstruct or overwrite. |
| Holdout v02 files | Missing at Gate 1. | Do not tune against or describe as newly evaluated. |
| Educational generation fixtures/results | Exact filenames were not supplied. | The reported 4/4 result remained historical; source sentences could not be reviewed at Gate 1. |
| Existing evaluation outputs | Exact filenames were not supplied. | Historical values remained display-only and attributed to the brief. |

## Schema known at Gate 1

The specification described `working_corpus_v01.json` as 76 records with `chunk_id`, `source_id`, `source_type`, `authority_level`, `company`, `year`, `pdf_page`, `topic` and `text`. Because the file was absent at Gate 1, its contents, ID uniqueness, pages and provenance were not inspected then. Later Gate 3 documentation records the separately supplied private bundle and its validation.

## Preservation action

No pre-existing workspace file was overwritten. The application treats the optional private corpus as read-only, hashes it before and after loading, and never writes to that path.
