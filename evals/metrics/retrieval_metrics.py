"""Score labeled retrieval results for dense, keyword, and hybrid strategies."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    """Report the acceptance metrics for one retrieval strategy."""

    precision_at_5: float
    recall_at_5: float
    ndcg_at_5: float


def score_query(relevant: set[str], ranked: Sequence[str]) -> RetrievalMetrics:
    """Calculate binary relevance metrics at five documents."""
    top = list(ranked[:5])
    hits = [1 if item in relevant else 0 for item in top]
    precision = sum(hits) / 5
    recall = sum(hits) / len(relevant) if relevant else 1.0
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal_hits = [1] * min(5, len(relevant))
    ideal = sum(hit / math.log2(index + 2) for index, hit in enumerate(ideal_hits))
    return RetrievalMetrics(precision, recall, dcg / ideal if ideal else 1.0)


def average_metrics(
    labels: Mapping[str, set[str]], results: Mapping[str, Sequence[str]]
) -> RetrievalMetrics:
    """Average all labeled queries while requiring a result for every label."""
    scores = [
        score_query(relevant, results[query]) for query, relevant in labels.items()
    ]
    count = len(scores)
    if count == 0:
        raise ValueError("The benchmark requires at least one labeled question.")
    return RetrievalMetrics(
        sum(item.precision_at_5 for item in scores) / count,
        sum(item.recall_at_5 for item in scores) / count,
        sum(item.ndcg_at_5 for item in scores) / count,
    )
