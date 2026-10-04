"""Verify deployed pgvector storage without printing patient identifiers."""

import asyncio
import json

from doc_agent_common.config import CHUNK_VERSION, AppSettings
from doc_agent_common.runtime import configure_asyncio_for_psycopg
from doc_agent_common.ssh_tunnel import SshTunnel
from doc_agent_db.rag_repository import RagRepository
from psycopg.rows import dict_row


async def verify() -> dict[str, object]:
    """Check extension, vectors, indexes, uniqueness, and injection isolation."""
    settings = AppSettings.load()
    async with SshTunnel(settings):
        repository = RagRepository(settings)
        async with (
            repository.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """SELECT extversion FROM pg_extension WHERE extname = 'vector'"""
            )
            extension = await cursor.fetchone()
            await cursor.execute(
                """SELECT count(*)::integer AS chunks,
                              count(DISTINCT patient_id)::integer AS patients,
                              min(vector_dims(embedding))::integer AS min_dimensions,
                              max(vector_dims(embedding))::integer AS max_dimensions,
                              min(chunk_version)::integer AS min_chunk_version,
                              max(chunk_version)::integer AS max_chunk_version,
                              count(*) FILTER (WHERE content ~* %s)::integer
                                AS email_shaped_chunks,
                              count(*) - count(DISTINCT
                                (patient_id, content_hash, embedding_model,
                                 embedding_revision, chunk_version)) AS duplicates
                       FROM rag.patient_chunks""",
                (r"[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}",),
            )
            storage = await cursor.fetchone()
            await cursor.execute(
                """SELECT count(*)::integer AS required_indexes
                       FROM pg_indexes
                       WHERE schemaname = 'rag'
                         AND indexname = ANY(%s)""",
                (
                    [
                        "patient_chunks_patient_idx",
                        "patient_chunks_patient_domain_idx",
                        "patient_chunks_admissions_idx",
                        "patient_chunks_search_idx",
                        "patient_chunks_embedding_idx",
                    ],
                ),
            )
            indexes = await cursor.fetchone()
            injection = "patient' OR '1'='1"
            await cursor.execute(
                "SELECT count(*)::integer AS matches FROM rag.patient_chunks WHERE patient_id = %s",
                (injection,),
            )
            isolation = await cursor.fetchone()
    assert extension and storage and indexes and isolation
    result = {
        "pgvector_version": extension["extversion"],
        **storage,
        **indexes,
        "injection_payload_matches": isolation["matches"],
    }
    if (
        result["min_dimensions"] != 384
        or result["max_dimensions"] != 384
        or result["min_chunk_version"] != CHUNK_VERSION
        or result["max_chunk_version"] != CHUNK_VERSION
        or result["email_shaped_chunks"] != 0
        or result["duplicates"] != 0
        or result["required_indexes"] != 5
        or result["injection_payload_matches"] != 0
    ):
        raise RuntimeError("RAG storage verification failed.")
    return result


def main() -> None:
    """Print only aggregate, non-identifying verification values."""
    configure_asyncio_for_psycopg()
    print(json.dumps(asyncio.run(verify()), sort_keys=True))


if __name__ == "__main__":
    main()
