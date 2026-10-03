"""Development-only retrieval diagnostic; never evaluates the frozen holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval import BM25Index, tokenize  # noqa: E402
from src.schemas import EvidenceChunk  # noqa: E402


DEFAULT_PRIVATE_ROOT = (
    PROJECT_ROOT
    / "private_data"
    / "runtime_inputs_v01"
    / "PE6201_Codex_Private_Runtime_Inputs_v01"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "results_v1.json"
RRF_K = 60
TOP_N = 10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class LocalLSAIndex:
    """Small local latent-semantic diagnostic over TF-IDF; source text stays local."""

    def __init__(self, chunks: list[EvidenceChunk], dimensions: int = 16):
        self.chunks = list(chunks)
        documents = [tokenize(chunk.text) for chunk in chunks]
        document_frequency: Counter[str] = Counter()
        for document in documents:
            document_frequency.update(set(document))
        self.vocabulary = {
            token: index for index, token in enumerate(sorted(document_frequency))
        }
        total = len(documents)
        self.idf = {
            token: math.log((1 + total) / (1 + frequency)) + 1
            for token, frequency in document_frequency.items()
        }
        matrix = np.zeros((total, len(self.vocabulary)), dtype=float)
        for row, document in enumerate(documents):
            frequencies = Counter(document)
            for token, frequency in frequencies.items():
                matrix[row, self.vocabulary[token]] = (
                    1 + math.log(frequency)
                ) * self.idf[token]
        rank = max(1, min(dimensions, matrix.shape[0] - 1, matrix.shape[1] - 1))
        u, singular_values, vt = np.linalg.svd(matrix, full_matrices=False)
        self.components = vt[:rank]
        self.document_vectors = u[:, :rank] * singular_values[:rank]

    @staticmethod
    def _cosine(left: np.ndarray, right: np.ndarray) -> float:
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        return float(np.dot(left, right) / denominator) if denominator else 0.0

    def search(self, query: str, top_n: int = TOP_N) -> list[tuple[str, float]]:
        vector = np.zeros(len(self.vocabulary), dtype=float)
        frequencies = Counter(tokenize(query))
        for token, frequency in frequencies.items():
            index = self.vocabulary.get(token)
            if index is not None:
                vector[index] = (1 + math.log(frequency)) * self.idf[token]
        query_vector = vector @ self.components.T
        scored = [
            (chunk.chunk_id, self._cosine(query_vector, document_vector))
            for chunk, document_vector in zip(self.chunks, self.document_vectors)
        ]
        return sorted(scored, key=lambda item: (-item[1], item[0]))[:top_n]


def _rrf(
    bm25: list[tuple[str, float]], semantic: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in (bm25, semantic):
        for rank, (chunk_id, _) in enumerate(ranking, 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:TOP_N]


def _hit(ranking: list[tuple[str, float]], accepted: set[str], k: int) -> bool:
    return bool({chunk_id for chunk_id, _ in ranking[:k]} & accepted)


def run(private_root: Path = DEFAULT_PRIVATE_ROOT) -> dict[str, Any]:
    corpus_path = private_root / "working_corpus_v01.json"
    development_path = private_root / "development_ground_truth_frozen_v01.json"
    corpus_records = _load_json(corpus_path)
    questions = _load_json(development_path)
    if len(corpus_records) != 76:
        raise ValueError(f"Expected 76 corpus records, found {len(corpus_records)}.")
    if len(questions) != 12 or {item.get("split") for item in questions} != {"development"}:
        raise ValueError("Experiment requires exactly the 12 frozen development questions.")

    chunks = [EvidenceChunk.from_dict(record) for record in corpus_records]
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    bm25 = BM25Index(chunks)
    semantic = LocalLSAIndex(chunks)
    method_names = ("bm25", "local_lsa", "rrf_hybrid")
    counts = {method: {"hit_at_1": 0, "hit_at_5": 0} for method in method_names}
    observations = []

    for question in questions:
        accepted = set(question["relevant_chunk_ids"])
        if not accepted <= set(by_id):
            raise ValueError(f"Missing accepted chunk for {question['question_id']}.")
        bm25_ranking = [
            (hit.chunk.chunk_id, hit.score)
            for hit in bm25.search(question["question"], top_k=TOP_N)
        ]
        semantic_ranking = semantic.search(question["question"])
        hybrid_ranking = _rrf(bm25_ranking, semantic_ranking)
        rankings = {
            "bm25": bm25_ranking,
            "local_lsa": semantic_ranking,
            "rrf_hybrid": hybrid_ranking,
        }
        question_terms = set(tokenize(question["question"]))
        accepted_overlap = max(
            len(question_terms & set(tokenize(by_id[chunk_id].text)))
            / max(1, len(question_terms))
            for chunk_id in accepted
        )
        result = {
            "question_id": question["question_id"],
            "accepted_chunk_ids": sorted(accepted),
            "accepted_lexical_coverage": round(accepted_overlap, 6),
            "methods": {},
        }
        for method, ranking in rankings.items():
            hit_1 = _hit(ranking, accepted, 1)
            hit_5 = _hit(ranking, accepted, 5)
            counts[method]["hit_at_1"] += int(hit_1)
            counts[method]["hit_at_5"] += int(hit_5)
            result["methods"][method] = {
                "hit_at_1": hit_1,
                "hit_at_5": hit_5,
                "top_5_chunk_ids": [item[0] for item in ranking[:5]],
            }
        observations.append(result)

    summary = {
        method: {
            "questions": len(questions),
            "hit_at_1_count": values["hit_at_1"],
            "hit_at_1": round(values["hit_at_1"] / len(questions), 6),
            "hit_at_5_count": values["hit_at_5"],
            "hit_at_5": round(values["hit_at_5"] / len(questions), 6),
        }
        for method, values in counts.items()
    }
    hybrid_benefit = (
        summary["rrf_hybrid"]["hit_at_1_count"] > summary["bm25"]["hit_at_1_count"]
        or summary["rrf_hybrid"]["hit_at_5_count"] > summary["bm25"]["hit_at_5_count"]
    )
    return {
        "evaluation_id": "retrieval_hybrid_dev_v1",
        "status": "development-only diagnostic; not independent holdout performance",
        "frozen_holdout_accessed": False,
        "frozen_holdout_tuned": False,
        "production_retriever_changed": False,
        "inputs": {
            "corpus_records": len(chunks),
            "development_questions": len(questions),
            "corpus_sha256": _sha256(corpus_path),
            "development_labels_sha256": _sha256(development_path),
        },
        "methods": {
            "bm25": "Existing production BM25 with unchanged parameters.",
            "local_lsa": "Local TF-IDF latent semantic analysis with 16 dimensions; diagnostic only and not the historical semantic system.",
            "rrf_hybrid": f"Predeclared equal reciprocal-rank fusion of BM25 and local LSA top-{TOP_N} rankings with k={RRF_K}; no weight search.",
        },
        "summary": summary,
        "mean_accepted_lexical_coverage": round(
            sum(item["accepted_lexical_coverage"] for item in observations)
            / len(observations),
            6,
        ),
        "hybrid_has_development_benefit": hybrid_benefit,
        "decision_rule": "Retain BM25 unless the predeclared hybrid improves development Hit@1 or Hit@5; any development gain remains exploratory and cannot establish holdout improvement.",
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.private_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
