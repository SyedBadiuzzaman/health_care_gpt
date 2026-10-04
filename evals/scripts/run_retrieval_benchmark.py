"""Run the labeled dense, keyword, and hybrid retrieval comparison."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict, cast

from doc_agent_common.config import AppSettings
from doc_agent_common.runtime import configure_asyncio_for_psycopg
from doc_agent_common.ssh_tunnel import SshTunnel
from doc_agent_core.embeddings import MiniLmEmbedder
from doc_agent_core.retrieval import hybrid_select
from doc_agent_core.state import ClinicalDomain, FloatVector, StoredChunk
from doc_agent_db.rag_repository import RagRepository
from psycopg.rows import dict_row

from evals.metrics.retrieval_metrics import RetrievalMetrics


class EvaluationLabel(TypedDict):
    id: str
    question: str
    domain: ClinicalDomain
    keywords: list[str]


def _load_labels(project: Path) -> list[EvaluationLabel]:
    raw = json.loads(
        (project / "evals" / "datasets" / "retrieval_evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    return cast(list[EvaluationLabel], raw)


def _relevant(chunk: StoredChunk, label: EvaluationLabel) -> bool:
    """Apply the fixture's domain and clinical-concept relevance judgment."""
    if chunk.domain != label["domain"]:
        return False
    lowered = chunk.content.casefold()
    return any(keyword.casefold() in lowered for keyword in label["keywords"])


def _score(
    labels: list[EvaluationLabel],
    corpus: list[StoredChunk],
    results: list[list[StoredChunk]],
) -> RetrievalMetrics:
    """Score category recall against at most five possible relevant positions."""
    precisions: list[float] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    for label, ranked in zip(labels, results, strict=True):
        corpus_relevant = sum(_relevant(chunk, label) for chunk in corpus)
        hits = [1 if _relevant(chunk, label) else 0 for chunk in ranked[:5]]
        while len(hits) < 5:
            hits.append(0)
        precisions.append(sum(hits) / 5)
        recalls.append(sum(hits) / min(5, corpus_relevant) if corpus_relevant else 0.0)
        discounts = [1.0, 0.6309297536, 0.5, 0.4306765581, 0.3868528072]
        dcg = sum(hit * discount for hit, discount in zip(hits, discounts, strict=True))
        ideal = sum(discounts[: min(5, corpus_relevant)])
        ndcgs.append(dcg / ideal if ideal else 0.0)
    count = len(labels)
    return RetrievalMetrics(
        sum(precisions) / count,
        sum(recalls) / count,
        sum(ndcgs) / count,
    )


async def run() -> dict[str, object]:
    """Evaluate all strategies under the same patient and question set."""
    settings = AppSettings.load()
    labels = _load_labels(settings.project)
    embedder = await asyncio.to_thread(MiniLmEmbedder, str(settings.project / "models"))
    vectors = await asyncio.to_thread(
        embedder.encode, [label["question"] for label in labels]
    )
    dense_results: list[list[StoredChunk]] = []
    keyword_results: list[list[StoredChunk]] = []
    hybrid_results: list[list[StoredChunk]] = []
    async with SshTunnel(settings):
        repository = RagRepository(settings)
        async with (
            repository.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                "SELECT patient_id FROM rag.patient_chunks ORDER BY chunk_id LIMIT 1"
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("The benchmark requires an indexed patient.")
        patient_id = str(row["patient_id"])
        corpus_result = await repository.structured_facts(
            patient_id, None, ("encounter", "medication", "microbiology", "drg")
        )
        corpus = list(corpus_result.chunks)
        # The SSH tunnel and application role use a deliberately small connection budget.
        semaphore = asyncio.Semaphore(1)

        async def retrieve(
            label: EvaluationLabel, vector: FloatVector
        ) -> tuple[list[StoredChunk], list[StoredChunk], list[StoredChunk]]:
            async with semaphore:
                dense, keyword = await asyncio.gather(
                    repository.dense_search(patient_id, vector, None),
                    repository.keyword_search(patient_id, label["question"], None),
                )
            hybrid = hybrid_select(label["question"], dense, keyword, vector, limit=5)
            return dense[:5], keyword[:5], hybrid

        retrieved = await asyncio.gather(
            *(
                retrieve(label, vector)
                for label, vector in zip(labels, vectors, strict=True)
            )
        )
        for dense, keyword, hybrid in retrieved:
            dense_results.append(dense[:5])
            keyword_results.append(keyword[:5])
            hybrid_results.append(hybrid)
        isolated = await repository.dense_search("patient' OR '1'='1", vectors[0], None)
    metrics: dict[str, object] = {
        "dense": asdict(_score(labels, corpus, dense_results)),
        "keyword": asdict(_score(labels, corpus, keyword_results)),
        "hybrid_mmr": asdict(_score(labels, corpus, hybrid_results)),
        "patient_isolation_percent": 100 if not isolated else 0,
        "question_count": len(labels),
    }
    return metrics


def meets_acceptance(metrics: dict[str, object]) -> bool:
    """Apply the approved isolation and hybrid quality thresholds."""
    hybrid = metrics["hybrid_mmr"]
    assert isinstance(hybrid, dict)
    return bool(
        metrics["patient_isolation_percent"] == 100
        and hybrid["precision_at_5"] >= 0.70
        and hybrid["recall_at_5"] >= 0.80
        and hybrid["ndcg_at_5"] >= 0.70
    )


def main() -> None:
    """Print aggregate benchmark metrics without clinical text or identifiers."""
    configure_asyncio_for_psycopg()
    metrics = asyncio.run(run())
    report = Path.cwd() / "evals/reports/retrieval_benchmark.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, sort_keys=True))
    if not meets_acceptance(metrics):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
