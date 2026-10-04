"""Smoke-test each deployed retrieval branch without printing identifiers or facts."""

import asyncio
import json

from doc_agent_common.config import AppSettings
from doc_agent_common.runtime import configure_asyncio_for_psycopg
from doc_agent_common.ssh_tunnel import SshTunnel
from doc_agent_db.rag_repository import RagRepository
from psycopg.rows import dict_row


async def verify() -> dict[str, int]:
    """Exercise patient, admission, vector, text, and structured query filters."""
    settings = AppSettings.load()
    async with SshTunnel(settings):
        repository = RagRepository(settings)
        async with (
            repository.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                "SELECT patient_id, embedding FROM rag.patient_chunks ORDER BY chunk_id LIMIT 1"
            )
            seed = await cursor.fetchone()
        if seed is None:
            raise RuntimeError("The RAG index is empty.")
        patient_id = str(seed["patient_id"])
        vector = RagRepository._vector(seed["embedding"])
        dense = await repository.dense_search(patient_id, vector, None)
        keyword = await repository.keyword_search(patient_id, "drug medication", None)
        structured = await repository.structured_facts(
            patient_id, None, ("encounter", "medication", "microbiology", "drg")
        )
        summary = await repository.patient_summary(patient_id)
        if not dense or not keyword or not structured.chunks or summary is None:
            raise RuntimeError(
                "A deployed retrieval branch returned no expected history."
            )

        admission_id = dense[0].admission_ids[0]
        admission = await repository.dense_search(patient_id, vector, admission_id)
        if not admission or any(
            admission_id not in chunk.admission_ids for chunk in admission
        ):
            raise RuntimeError("Admission filtering failed.")

        injection = "patient' OR '1'='1"
        injection_admission = "admission' OR '1'='1"
        denied = await asyncio.gather(
            repository.dense_search(injection, vector, None),
            repository.keyword_search(injection, "drug", None),
            repository.structured_facts(
                injection, None, ("encounter", "medication", "microbiology", "drg")
            ),
            repository.dense_search(patient_id, vector, injection_admission),
        )
        if denied[0] or denied[1] or denied[2].chunks or denied[3]:
            raise RuntimeError("A parameterized isolation check failed.")
    return {
        "dense_candidates": len(dense),
        "keyword_candidates": len(keyword),
        "structured_facts": len(structured.chunks),
        "admission_candidates": len(admission),
        "isolation_failures": 0,
    }


def main() -> None:
    """Print only aggregate, non-identifying smoke-test values."""
    configure_asyncio_for_psycopg()
    print(json.dumps(asyncio.run(verify()), sort_keys=True))


if __name__ == "__main__":
    main()
