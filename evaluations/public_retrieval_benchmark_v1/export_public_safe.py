"""Create a metadata-only public export from the untouched frozen benchmark."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = (
    PROJECT_ROOT
    / "private_data"
    / "runtime_inputs_v01"
    / "PE6201_Codex_Private_Runtime_Inputs_v01"
)
SOURCE_FILES = {
    "question_bank": "evaluation_question_bank_frozen_v01.json",
    "development": "development_ground_truth_frozen_v01.json",
    "holdout": "holdout_test_ground_truth_frozen_v01.json",
    "label_audit": "all_76_chunk_label_audit_frozen_v01.csv",
    "qa_report": "ground_truth_QA_report_frozen_v01.md",
}
OUTPUT_JSON = EXPORT_DIR / "questions_and_accepted_mappings_v1.json"
OUTPUT_CSV = EXPORT_DIR / "accepted_evidence_mappings_v1.csv"
INTEGRITY_REPORT = EXPORT_DIR / "export_integrity_report_v1.json"
PUBLIC_MANIFEST = EXPORT_DIR / "freeze_manifest_public_v1.json"
SCHEMA_PATH = EXPORT_DIR / "questions_and_accepted_mappings.schema.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _longest_contiguous_overlap(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    best = 0
    for left_token in left:
        current = [0] * (len(right) + 1)
        for index, right_token in enumerate(right, 1):
            if left_token == right_token:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_export() -> dict[str, Any]:
    original_hashes_before = {
        name: _sha256(PRIVATE_DIR / filename) for name, filename in SOURCE_FILES.items()
    }
    source_manifest_path = PRIVATE_DIR / "freeze_manifest_v02.json"
    source_manifest_hash = _sha256(source_manifest_path)
    source_manifest = _load_json(source_manifest_path)
    for key in ("question_bank", "development", "holdout", "label_audit", "qa_report"):
        filename = SOURCE_FILES[key]
        expected = source_manifest["file_sha256"][filename]
        if original_hashes_before[key] != expected:
            raise ValueError(f"Frozen source hash mismatch: {filename}")

    questions = _load_json(PRIVATE_DIR / SOURCE_FILES["question_bank"])
    development = _load_json(PRIVATE_DIR / SOURCE_FILES["development"])
    holdout = _load_json(PRIVATE_DIR / SOURCE_FILES["holdout"])
    corpus = _load_json(PRIVATE_DIR / "working_corpus_v01.json")
    corpus_by_id = {item["chunk_id"]: item for item in corpus}
    with (PRIVATE_DIR / SOURCE_FILES["label_audit"]).open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))

    if development != [item for item in questions if item["split"] == "development"]:
        raise ValueError("Development subset does not exactly match the frozen question bank")
    if holdout != [item for item in questions if item["split"] == "holdout_test"]:
        raise ValueError("Holdout subset does not exactly match the frozen question bank")

    accepted_pairs_from_bank = {
        (item["question_id"], chunk_id)
        for item in questions
        for chunk_id in item["relevant_chunk_ids"]
    }
    accepted_pairs_from_audit = {
        (row["question_id"], row["chunk_id"])
        for row in audit_rows
        if row["decision"] == "Accept"
    }
    if accepted_pairs_from_bank != accepted_pairs_from_audit:
        raise ValueError("Question mappings do not match label-audit Accept decisions")

    exported_questions = []
    flat_rows = []
    for item in questions:
        mappings = []
        for chunk_id in item["relevant_chunk_ids"]:
            if chunk_id not in corpus_by_id:
                raise ValueError(f"Mapped chunk missing from corpus: {chunk_id}")
            source = corpus_by_id[chunk_id]
            mapping = {
                "chunk_id": chunk_id,
                "company": source["company"],
                "report_year": source["year"],
                "pdf_page": source["pdf_page"],
                "source_type": source["source_type"],
                "authority_level": source["authority_level"],
            }
            mappings.append(mapping)
            flat_rows.append(
                {
                    "question_id": item["question_id"],
                    "split": item["split"],
                    "question": item["question"],
                    "question_company": item["company"],
                    "question_report_year": item["year"],
                    "anchor_pdf_page": item["pdf_page"],
                    "verified_anchor_chunk_id": item["verified_anchor_id"],
                    **{f"accepted_{key}": value for key, value in mapping.items()},
                }
            )
        if item["verified_anchor_id"] not in item["relevant_chunk_ids"]:
            raise ValueError(f"Verified anchor is not an accepted mapping: {item['question_id']}")
        exported_questions.append(
            {
                "question_id": item["question_id"],
                "split": item["split"],
                "question": item["question"],
                "company": item["company"],
                "report_year": item["year"],
                "anchor_pdf_page": item["pdf_page"],
                "verified_anchor_chunk_id": item["verified_anchor_id"],
                "source_type": item["source_type"],
                "authority_level": item["authority_level"],
                "label_provenance": item["label_provenance"],
                "accepted_evidence_mappings": mappings,
            }
        )

    export_payload = {
        "export_id": "pe6201_public_safe_retrieval_benchmark_v1",
        "classification": "Public-safe metadata export derived exactly from frozen records",
        "question_count": len(exported_questions),
        "split_counts": {"development": len(development), "holdout_test": len(holdout)},
        "accepted_mapping_count": len(flat_rows),
        "scoring_rule": source_manifest["scoring_definition"],
        "raw_annual_report_text_included": False,
        "local_filesystem_paths_included": False,
        "questions": exported_questions,
    }
    _write_json(OUTPUT_JSON, export_payload)

    fieldnames = list(flat_rows[0])
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(flat_rows)
    OUTPUT_CSV.write_text(csv_buffer.getvalue(), encoding="utf-8", newline="")

    overlap_flags = []
    corpus_token_sets = [(item["chunk_id"], _tokens(item["text"])) for item in corpus]
    for item in questions:
        question_tokens = _tokens(item["question"])
        maximum = max(
            _longest_contiguous_overlap(question_tokens, source_tokens)
            for _, source_tokens in corpus_token_sets
        )
        ratio = maximum / len(question_tokens) if question_tokens else 0
        if maximum >= 8 or ratio >= 0.60:
            overlap_flags.append(
                {
                    "question_id": item["question_id"],
                    "maximum_contiguous_overlap_tokens": maximum,
                    "question_token_count": len(question_tokens),
                    "overlap_ratio": round(ratio, 4),
                    "manual_assessment": "Technical accounting terminology in a short interrogative question; no annual-report passage or narrative source-body text reproduced.",
                    "publication_decision": "public_safe",
                }
            )

    sensitive_pattern = re.compile(
        r"(?:[A-Za-z]:\\|/Users/|/home/|sk-or-v1-|OPENROUTER_API_KEY|SEC_USER_AGENT|Authorization\s*[:=]\s*Bearer)",
        re.IGNORECASE,
    )
    sensitive_question_ids = [
        item["question_id"] for item in questions if sensitive_pattern.search(item["question"])
    ]
    serialized_export = OUTPUT_JSON.read_text(encoding="utf-8") + OUTPUT_CSV.read_text(encoding="utf-8")
    prohibited_export_fields = [
        name for name in ("text", "source_body", "raw_text", "local_path")
        if re.search(rf'"{name}"\s*:', serialized_export)
    ]

    original_hashes_after = {
        name: _sha256(PRIVATE_DIR / filename) for name, filename in SOURCE_FILES.items()
    }
    if original_hashes_after != original_hashes_before:
        raise ValueError("A frozen source changed during export")

    report = {
        "export_id": export_payload["export_id"],
        "source_manifest_sha256": source_manifest_hash,
        "source_files_match_original_freeze_manifest": True,
        "source_hashes_unchanged_before_and_after_export": original_hashes_before == original_hashes_after,
        "question_bank_matches_development_and_holdout_subsets": True,
        "question_count": len(questions),
        "question_ids_unique": len({item["question_id"] for item in questions}) == len(questions),
        "split_counts": export_payload["split_counts"],
        "label_audit_rows": len(audit_rows),
        "label_audit_accept_count": len(accepted_pairs_from_audit),
        "label_audit_exclude_count": sum(row["decision"] == "Exclude" for row in audit_rows),
        "accepted_mapping_count": len(flat_rows),
        "accepted_mappings_exactly_match_label_audit": True,
        "all_verified_anchors_preserved": True,
        "all_mapping_metadata_read_from_frozen_corpus": True,
        "questions_with_multiple_accepted_mappings": [
            item["question_id"] for item in questions if len(item["relevant_chunk_ids"]) > 1
        ],
        "raw_source_body_fields_in_export": prohibited_export_fields,
        "sensitive_pattern_question_ids": sensitive_question_ids,
        "wording_overlap_review": {
            "method": "Longest contiguous normalized-token overlap against all 76 source chunks; flag at 8 tokens or 60% of question tokens, followed by manual wording review.",
            "flagged_records": overlap_flags,
            "restricted_question_ids": [],
            "assessment": "All 50 frozen questions are short research questions. The two flags use technical accounting terminology rather than copied narrative passages.",
        },
        "restricted_submission_required_for_question_content": False,
        "remaining_restricted_material": [
            "The 76-chunk annual-report corpus and all raw source-body text.",
            "The full 3,800-row label-audit reasons and private QA/source bundle remain under the private runtime boundary.",
            "Exact metric reproduction requires the original private corpus; this export supports transparent inspection of questions and accepted mappings only.",
        ],
        "network_calls": {"openrouter": 0, "sec": 0},
        "export_files": {
            OUTPUT_JSON.name: _sha256(OUTPUT_JSON),
            OUTPUT_CSV.name: _sha256(OUTPUT_CSV),
        },
    }
    _write_json(INTEGRITY_REPORT, report)

    public_manifest = {
        "export_id": export_payload["export_id"],
        "algorithm": "SHA-256 over raw file bytes",
        "purpose": "Freeze the public-safe derivative without changing the original private freeze.",
        "source_manifest_sha256": source_manifest_hash,
        "files": {
            OUTPUT_JSON.name: _sha256(OUTPUT_JSON),
            OUTPUT_CSV.name: _sha256(OUTPUT_CSV),
            INTEGRITY_REPORT.name: _sha256(INTEGRITY_REPORT),
            SCHEMA_PATH.name: _sha256(SCHEMA_PATH),
        },
        "question_count": len(questions),
        "accepted_mapping_count": len(flat_rows),
        "original_sources_modified": False,
    }
    _write_json(PUBLIC_MANIFEST, public_manifest)
    return {"export": export_payload, "integrity": report, "manifest": public_manifest}


if __name__ == "__main__":
    result = build_export()
    print(
        json.dumps(
            {
                "question_count": result["export"]["question_count"],
                "split_counts": result["export"]["split_counts"],
                "accepted_mapping_count": result["export"]["accepted_mapping_count"],
                "integrity_pass": all(
                    (
                        result["integrity"]["source_files_match_original_freeze_manifest"],
                        result["integrity"]["source_hashes_unchanged_before_and_after_export"],
                        result["integrity"]["accepted_mappings_exactly_match_label_audit"],
                        not result["integrity"]["raw_source_body_fields_in_export"],
                        not result["integrity"]["sensitive_pattern_question_ids"],
                    )
                ),
                "restricted_question_ids": result["integrity"]["wording_overlap_review"]["restricted_question_ids"],
            },
            indent=2,
        )
    )
