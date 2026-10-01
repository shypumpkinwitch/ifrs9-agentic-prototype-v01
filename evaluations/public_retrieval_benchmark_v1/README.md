# PE6201 public-safe retrieval benchmark export v1

This directory is a separate, metadata-only derivative of the untouched frozen 50-question benchmark. It makes the questions and every accepted evidence mapping inspectable without publishing annual-report passages, API credentials or local paths.

## Files

- `questions_and_accepted_mappings_v1.json` — all 50 frozen questions with split, question text, company/year, anchor page and every accepted chunk mapping.
- `accepted_evidence_mappings_v1.csv` — flat 58-row view; questions with multiple valid chunks have multiple rows.
- `questions_and_accepted_mappings.schema.json` — public export schema.
- `export_integrity_report_v1.json` — source-hash, split, mapping, metadata, privacy and wording-review checks.
- `freeze_manifest_public_v1.json` — hashes the public derivative; it does not replace the original private manifest.
- `export_public_safe.py` — deterministic offline exporter/verifier. It requires the original private bundle for regeneration.
- `RESTRICTED_SUBMISSION_NOTE.md` — explicitly labelled restricted-channel alternative for exact reproduction and detailed adjudication material.

## Creation and review provenance

The original frozen set was derived from the earlier development ground truth and evaluation question bank. The 12 development anchors had been user-confirmed in the earlier review; independently sufficient alternative development mappings were assistant-reviewed against source text. The 38 holdout questions and their labels were assistant source-text reviewed and were not individually user-confirmed.

Before freezing, four holdout questions were narrowed to ensure that a single chunk could answer the whole question. The full audit considered every one of the 50 questions against all 76 corpus chunks. It contains 3,800 decisions: 58 `Accept` and 3,742 `Exclude`. A chunk was accepted only when it independently answered the whole narrowed question. A keyword-related, adjacent or partial-answer chunk was excluded. A later independent adjudicator could disagree with these judgements.

The export preserves all 58 accepted mappings. Forty-three questions have one mapping, six have two, and one has three. It never selects only the first mapping. The full exclusion-reason audit remains in the private bundle; this public derivative reports its counts and proves that its accepted pairs exactly equal the frozen `Accept` pairs.

## Split and frozen protocol

- Development: 12 questions. Used for development diagnostics only.
- Holdout test: 38 questions. Used for final historical retrieval reporting.
- Scoring: Hit@k equals 1 for a question when at least one independently sufficient accepted `chunk_id` appears in the top k results. No question requires a conjunction of chunks.
- Hit@1 and Hit@5 are the sums of per-question hits divided by the number of evaluated questions.

Final results are reported on the 38-question holdout because development questions informed development and cannot provide an unbiased final estimate. Historical holdout results are BM25 Hit@1 71.1% (27/38), BM25 Hit@5 97.4% (37/38), Semantic Hit@1 34.2% (13/38) and Semantic Hit@5 73.7% (28/38). They are preserved results, not recomputed by this export.

Exact metric reproduction requires the private 76-chunk corpus because retrieval must rank the original source bodies. This public export permits inspection of questions, accepted identifiers and provenance, but contains no retrievable document text.

## Publication review

All 50 question strings were checked for secret/path patterns and compared with all 76 source chunks using a conservative contiguous-token overlap screen. RBC003 and GLEN003 crossed the automated eight-token threshold. Manual review found short interrogative questions using necessary technical accounting terminology, not reproduced narrative passages. No question was restricted or rewritten.

The restricted material that remains outside this directory is the annual-report corpus, the full 3,800-row audit reasons and the private QA/source bundle. If a reviewer requires those materials, they must be submitted through an authorised restricted course channel; they must not be added to a public repository.

No question record is restricted. See `RESTRICTED_SUBMISSION_NOTE.md` for the supporting files that remain private and why.

## Regeneration

From the project directory, with the original private bundle installed:

```powershell
& '.\.venv\Scripts\python.exe' evaluations/public_retrieval_benchmark_v1/export_public_safe.py
```

The exporter verifies all original frozen hashes before reading, writes only approved metadata, verifies that accepted pairs exactly match the label audit, and confirms that original hashes are unchanged afterward. It makes no network calls.
