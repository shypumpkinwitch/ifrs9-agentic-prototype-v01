from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .schemas import Candidate, EvidenceChunk


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "with",
    "company", "report", "reporting", "period", "other",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 1
    ]


@dataclass(frozen=True)
class RetrievalHit:
    score: float
    chunk: EvidenceChunk

    def to_dict(self, *, include_text: bool = True) -> dict:
        result = self.chunk.to_dict(include_text=include_text)
        result["score"] = round(self.score, 6)
        return result


class BM25Index:
    """Small dependency-free BM25 index for bounded local corpora."""

    def __init__(self, chunks: list[EvidenceChunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self.documents = [tokenize(chunk.text) for chunk in self.chunks]
        self.lengths = [len(document) for document in self.documents]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0
        self.term_frequencies = [Counter(document) for document in self.documents]
        self.document_frequency = Counter()
        for document in self.documents:
            self.document_frequency.update(set(document))

    def _idf(self, term: str) -> float:
        count = self.document_frequency.get(term, 0)
        total = len(self.documents)
        return math.log(1 + (total - count + 0.5) / (count + 0.5)) if total else 0

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        preferred_company: str | None = None,
        preferred_company_boost: float = 1.75,
    ) -> list[RetrievalHit]:
        if top_k < 1 or top_k > 10:
            raise ValueError("top_k must be between 1 and 10.")
        terms = tokenize(query)
        if not terms or not self.documents:
            return []
        scored: list[RetrievalHit] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            document_length = self.lengths[index]
            for term in terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * document_length / (self.average_length or 1)
                )
                score += self._idf(term) * frequency * (self.k1 + 1) / denominator
            if (
                score > 0
                and preferred_company
                and self.chunks[index].company.strip().casefold()
                == preferred_company.strip().casefold()
            ):
                score *= preferred_company_boost
            if score > 0:
                scored.append(RetrievalHit(score=score, chunk=self.chunks[index]))
        return sorted(scored, key=lambda item: (-item.score, item.chunk.chunk_id))[:top_k]


def search_candidates(
    candidates: list[Candidate], query: str, max_results: int = 5
) -> list[Candidate]:
    if max_results < 1 or max_results > 10:
        raise ValueError("max_results must be between 1 and 10.")
    query_terms = set(tokenize(query))
    ranked: list[tuple[int, Candidate]] = []
    for candidate in candidates:
        searchable = " ".join(
            [
                candidate.company_name,
                candidate.industry,
                candidate.business_relevance,
                *candidate.tags,
            ]
        )
        score = len(query_terms.intersection(tokenize(searchable)))
        if score:
            ranked.append((score, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1].candidate_id))
    return [candidate for _, candidate in ranked[:max_results]]
