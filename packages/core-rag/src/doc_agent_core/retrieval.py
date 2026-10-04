"""Fuse dense and lexical retrieval while preserving clinical diversity."""

import re
from collections.abc import Sequence

import numpy as np

from doc_agent_core.state import ClinicalDomain, FloatVector, RankedChunk, StoredChunk

RRF_K = 60
DENSE_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4
MMR_LAMBDA = 0.65

DOMAIN_TERMS: dict[ClinicalDomain, tuple[str, ...]] = {
    "encounter": ("encounter", "admission", "age", "event"),
    "medication": ("medication", "medicine", "drug", "dose", "route", "prescription"),
    "microbiology": (
        "microbiology",
        "culture",
        "specimen",
        "organism",
        "antibiotic",
        "test",
    ),
    "drg": ("drg", "diagnosis related group", "severity", "mortality"),
}


def requested_domains(question: str) -> tuple[ClinicalDomain, ...]:
    """Infer domains for a structured query and default to all domains."""
    lowered = question.casefold()
    found = tuple(
        domain
        for domain, terms in DOMAIN_TERMS.items()
        if any(term in lowered for term in terms)
    )
    return found or tuple(DOMAIN_TERMS)


def needs_structured_lookup(question: str) -> bool:
    """Detect count and exhaustive questions that approximate top-k can miss."""
    return bool(
        re.search(
            r"\b(how many|count|number of|all|every|complete list|entire history)\b",
            question,
            flags=re.IGNORECASE,
        )
    )


def reciprocal_rank_fusion(
    dense: Sequence[StoredChunk], keyword: Sequence[StoredChunk]
) -> list[RankedChunk]:
    """Combine two rankings without comparing incompatible raw scores."""
    chunks = {chunk.chunk_id: chunk for chunk in (*dense, *keyword)}
    scores: dict[str, float] = {chunk_id: 0.0 for chunk_id in chunks}
    for rank, chunk in enumerate(dense, start=1):
        scores[chunk.chunk_id] += DENSE_WEIGHT / (RRF_K + rank)
    for rank, chunk in enumerate(keyword, start=1):
        scores[chunk.chunk_id] += KEYWORD_WEIGHT / (RRF_K + rank)
    return sorted(
        (RankedChunk(chunks[key], score) for key, score in scores.items()),
        key=lambda item: (-item.relevance, item.chunk.chunk_id),
    )


def maximal_marginal_relevance(
    candidates: Sequence[RankedChunk],
    query_embedding: FloatVector,
    limit: int = 8,
) -> list[StoredChunk]:
    """Select relevant chunks while reducing near-duplicate clinical context."""
    remaining = list(candidates)
    selected: list[RankedChunk] = []
    maximum_relevance = max(
        (candidate.relevance for candidate in candidates), default=1.0
    )
    while remaining and len(selected) < limit:
        best: RankedChunk | None = None
        best_score = float("-inf")
        for candidate in remaining:
            # RRF is the relevance signal; cosine is used as a stable tiebreaker.
            fused_relevance = candidate.relevance / maximum_relevance
            query_similarity = float(np.dot(candidate.chunk.embedding, query_embedding))
            redundancy = max(
                (
                    float(np.dot(candidate.chunk.embedding, item.chunk.embedding))
                    for item in selected
                ),
                default=0.0,
            )
            score = MMR_LAMBDA * fused_relevance
            score -= (1.0 - MMR_LAMBDA) * redundancy
            score += query_similarity * 1e-6
            if score > best_score:
                best, best_score = candidate, score
        assert best is not None
        selected.append(best)
        remaining.remove(best)
    return [item.chunk for item in selected]


def hybrid_select(
    question: str,
    dense: Sequence[StoredChunk],
    keyword: Sequence[StoredChunk],
    query_embedding: FloatVector,
    limit: int = 8,
) -> list[StoredChunk]:
    """Apply domain-aware MMR after weighted reciprocal-rank fusion."""
    fused = reciprocal_rank_fusion(dense, keyword)
    domains = requested_domains(question)
    if len(domains) < len(DOMAIN_TERMS):
        domain_candidates = [item for item in fused if item.chunk.domain in domains]
        if domain_candidates:
            fused = domain_candidates
    return maximal_marginal_relevance(fused, query_embedding, limit)
