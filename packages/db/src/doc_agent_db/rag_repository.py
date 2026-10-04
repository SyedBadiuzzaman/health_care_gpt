"""Persist and retrieve patient-scoped RAG data with parameterized SQL."""

import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast

import numpy as np
from doc_agent_common.config import (
    CHUNK_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    AppSettings,
)
from doc_agent_core.state import (
    ChunkDraft,
    ClinicalDomain,
    FloatVector,
    PatientDirectoryEntry,
    PatientDirectoryPage,
    PatientSummary,
    StoredChunk,
    StructuredFacts,
)
from pgvector import Vector
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from doc_agent_db.connection import DatabaseConnectionFactory

FTS_STOP_WORDS = [
    "all",
    "came",
    "does",
    "every",
    "from",
    "history",
    "list",
    "present",
    "record",
    "recorded",
    "show",
    "summarize",
    "this",
    "value",
    "was",
    "were",
    "what",
    "which",
]


class RagRepository:
    """Provide the only PostgreSQL access used by indexing and querying."""

    def __init__(self, settings: AppSettings) -> None:
        self._connections = DatabaseConnectionFactory(settings)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[object]]:
        """Open a pgvector-aware connection for one bounded operation."""
        async with self._connections.connection() as connection:
            yield connection

    async def start_run(self, run_id: uuid.UUID) -> None:
        """Create an audit row before the replace transaction starts."""
        async with self.connection() as connection:
            await connection.execute(
                """INSERT INTO rag.ingestion_runs
                   (run_id, status, embedding_model, embedding_revision, chunk_version)
                   VALUES (%s, 'running', %s, %s, %s)""",
                (run_id, EMBEDDING_MODEL, EMBEDDING_REVISION, CHUNK_VERSION),
            )
            await connection.commit()

    async def mark_run_failed(self, run_id: uuid.UUID, error_code: str) -> None:
        """Record only a stable error code so audit rows cannot leak source data."""
        async with self.connection() as connection:
            await connection.execute(
                """UPDATE rag.ingestion_runs
                   SET status = 'failed', error_code = %s, finished_at = now()
                   WHERE run_id = %s""",
                (error_code[:64], run_id),
            )
            await connection.commit()

    async def existing_embeddings(
        self,
        connection: AsyncConnection[object],
        patient_ids: Sequence[str],
    ) -> dict[tuple[str, str], FloatVector]:
        """Load reusable vectors only from the exact model and schema version."""
        if not patient_ids:
            return {}
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """SELECT patient_id, content_hash, embedding
                   FROM rag.patient_chunks
                   WHERE patient_id = ANY(%s)
                     AND embedding_model = %s
                     AND embedding_revision = %s
                     AND chunk_version = %s""",
                (list(patient_ids), EMBEDDING_MODEL, EMBEDDING_REVISION, CHUNK_VERSION),
            )
            rows = await cursor.fetchall()
        return {
            (str(row["patient_id"]), str(row["content_hash"])): self._vector(
                row["embedding"]
            )
            for row in rows
        }

    async def replace_index(
        self,
        run_id: uuid.UUID,
        drafts: Sequence[ChunkDraft],
        vectors: Mapping[str, FloatVector],
        source_rows: int,
        patient_source_counts: Mapping[str, int],
        reused_embeddings: int,
    ) -> None:
        """Atomically upsert the new snapshot and remove its stale predecessors."""
        async with self.connection() as connection, connection.transaction():
            rows = [
                (
                    draft.chunk_id,
                    draft.patient_id,
                    list(draft.admission_ids),
                    draft.domain,
                    Jsonb(draft.facts),
                    draft.content,
                    draft.content_hash,
                    draft.repeat_count,
                    vectors[draft.chunk_id],
                    EMBEDDING_MODEL,
                    EMBEDDING_REVISION,
                    CHUNK_VERSION,
                    run_id,
                )
                for draft in drafts
            ]
            if rows:
                async with connection.cursor() as cursor:
                    await cursor.executemany(
                        """INSERT INTO rag.patient_chunks
                           (chunk_id, patient_id, admission_ids, domain, facts,
                            content, content_hash, repeat_count, embedding,
                            embedding_model, embedding_revision, chunk_version,
                            ingestion_run_id)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                   %s, %s, %s)
                           ON CONFLICT (chunk_id) DO UPDATE SET
                             admission_ids = EXCLUDED.admission_ids,
                             facts = EXCLUDED.facts,
                             content = EXCLUDED.content,
                             repeat_count = EXCLUDED.repeat_count,
                             ingestion_run_id = EXCLUDED.ingestion_run_id,
                             indexed_at = now()""",
                        rows,
                    )

            grouped: dict[str, list[ChunkDraft]] = {}
            for draft in drafts:
                grouped.setdefault(draft.patient_id, []).append(draft)
            for patient_id, patient_drafts in grouped.items():
                admissions = sorted(
                    {item for draft in patient_drafts for item in draft.admission_ids}
                )
                counts: dict[str, int] = {}
                for draft in patient_drafts:
                    counts[draft.domain] = counts.get(draft.domain, 0) + 1
                await connection.execute(
                    """INSERT INTO rag.patient_summaries
                       (patient_id, admission_ids, source_row_count,
                        domain_fact_counts, ingestion_run_id)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (patient_id) DO UPDATE SET
                         admission_ids = EXCLUDED.admission_ids,
                         source_row_count = EXCLUDED.source_row_count,
                         domain_fact_counts = EXCLUDED.domain_fact_counts,
                         ingestion_run_id = EXCLUDED.ingestion_run_id,
                         updated_at = now()""",
                    (
                        patient_id,
                        admissions,
                        patient_source_counts.get(patient_id, 0),
                        Jsonb(counts),
                        run_id,
                    ),
                )

            # Rows untouched by this complete snapshot are stale, including old schemas.
            await connection.execute(
                "DELETE FROM rag.patient_chunks WHERE ingestion_run_id <> %s",
                (run_id,),
            )
            await connection.execute(
                "DELETE FROM rag.patient_summaries WHERE ingestion_run_id <> %s",
                (run_id,),
            )
            await connection.execute(
                """UPDATE rag.ingestion_runs SET status = 'complete',
                     source_rows = %s, chunk_count = %s,
                     reused_embedding_count = %s, finished_at = now()
                   WHERE run_id = %s""",
                (source_rows, len(drafts), reused_embeddings, run_id),
            )

    async def dense_search(
        self,
        patient_id: str,
        query_embedding: FloatVector,
        admission_id: str | None,
        limit: int = 30,
    ) -> list[StoredChunk]:
        """Run filtered HNSW cosine retrieval for one authorized patient."""
        async with self.connection() as connection, connection.transaction():
            await connection.execute("SET LOCAL hnsw.iterative_scan = strict_order")
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """SELECT chunk_id, admission_ids, domain, facts, content,
                              repeat_count, embedding
                       FROM rag.patient_chunks
                       WHERE patient_id = %s
                         AND (%s::text IS NULL OR %s = ANY(admission_ids))
                       ORDER BY embedding <=> %s
                       LIMIT %s""",
                    (patient_id, admission_id, admission_id, query_embedding, limit),
                )
                return [self._stored(row) for row in await cursor.fetchall()]

    async def keyword_search(
        self,
        patient_id: str,
        question: str,
        admission_id: str | None,
        limit: int = 30,
    ) -> list[StoredChunk]:
        """Run filtered simple-dictionary full-text retrieval."""
        async with (
            self.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """WITH terms AS (
                         SELECT DISTINCT token
                         FROM regexp_split_to_table(lower(%s), '[^[:alnum:]_]+') token
                         WHERE length(token) >= 3
                           AND token <> ALL(%s)
                       ),
                       query AS (
                         SELECT to_tsquery(
                           'simple', COALESCE(string_agg(token || ':*', ' | '), '')
                         ) AS value
                         FROM terms
                       )
                       SELECT chunk_id, admission_ids, domain, facts, content,
                              repeat_count, embedding
                       FROM rag.patient_chunks, query
                       WHERE patient_id = %s
                         AND (%s::text IS NULL OR %s = ANY(admission_ids))
                         AND search_vector @@ query.value
                       ORDER BY ts_rank_cd(search_vector, query.value) DESC, chunk_id
                       LIMIT %s""",
                (
                    question,
                    FTS_STOP_WORDS,
                    patient_id,
                    admission_id,
                    admission_id,
                    limit,
                ),
            )
            return [self._stored(row) for row in await cursor.fetchall()]

    async def patient_summary(self, patient_id: str) -> PatientSummary | None:
        """Read deterministic counts for one patient."""
        async with (
            self.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """SELECT cardinality(admission_ids) AS admission_count,
                              source_row_count, domain_fact_counts
                       FROM rag.patient_summaries WHERE patient_id = %s""",
                (patient_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return PatientSummary(
            admission_count=int(row["admission_count"]),
            source_row_count=int(row["source_row_count"]),
            domain_fact_counts={
                str(key): int(value) for key, value in row["domain_fact_counts"].items()
            },
        )

    async def list_patients(
        self,
        authorized_patient_ids: Sequence[str],
        doctor_hash: str,
        search: str,
        limit: int,
        offset: int,
    ) -> PatientDirectoryPage:
        """List indexed patients inside the JWT claim and never outside it."""
        if not authorized_patient_ids:
            return PatientDirectoryPage((), 0, None, ())
        allowed = list(authorized_patient_ids)
        # Escaping keeps percent and underscore characters literal during ID search.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        async with (
            self.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """SELECT count(*) AS total
                   FROM rag.patient_summaries
                   WHERE patient_id = ANY(%s)
                     AND (%s = '' OR patient_id ILIKE %s ESCAPE '\\')""",
                (allowed, search, pattern),
            )
            count_row = await cursor.fetchone()
            total = int(count_row["total"]) if count_row is not None else 0
            await cursor.execute(
                """SELECT s.patient_id, s.admission_ids, s.domain_fact_counts,
                          s.source_row_count, r.last_selected_at
                   FROM rag.patient_summaries AS s
                   LEFT JOIN rag.doctor_recent_patients AS r
                     ON r.patient_id = s.patient_id AND r.doctor_hash = %s
                   WHERE s.patient_id = ANY(%s)
                     AND (%s = '' OR s.patient_id ILIKE %s ESCAPE '\\')
                   ORDER BY r.last_selected_at DESC NULLS LAST, s.patient_id
                   LIMIT %s OFFSET %s""",
                (doctor_hash, allowed, search, pattern, limit, offset),
            )
            rows = await cursor.fetchall()
            await cursor.execute(
                """SELECT r.patient_id
                   FROM rag.doctor_recent_patients AS r
                   JOIN rag.patient_summaries AS s ON s.patient_id = r.patient_id
                   WHERE r.doctor_hash = %s AND r.patient_id = ANY(%s)
                   ORDER BY r.last_selected_at DESC, r.patient_id
                   LIMIT 8""",
                (doctor_hash, allowed),
            )
            recent_rows = await cursor.fetchall()
        items = tuple(
            PatientDirectoryEntry(
                patient_id=str(row["patient_id"]),
                admission_ids=tuple(
                    str(item) for item in cast(Sequence[object], row["admission_ids"])
                ),
                domain_fact_counts={
                    str(key): int(str(value))
                    for key, value in cast(
                        Mapping[object, object], row["domain_fact_counts"]
                    ).items()
                },
                source_row_count=int(cast(int, row["source_row_count"])),
                last_selected_at=cast(datetime | None, row["last_selected_at"]),
            )
            for row in rows
        )
        next_offset = offset + len(items) if offset + len(items) < total else None
        return PatientDirectoryPage(
            items,
            total,
            next_offset,
            tuple(str(row["patient_id"]) for row in recent_rows),
        )

    async def record_patient_selection(self, doctor_hash: str, patient_id: str) -> None:
        """Record one authorized selection and retain only the latest eight."""
        async with self.connection() as connection, connection.transaction():
            await connection.execute(
                """INSERT INTO rag.doctor_recent_patients
                     (doctor_hash, patient_id, last_selected_at)
                   VALUES (%s, %s, now())
                   ON CONFLICT (doctor_hash, patient_id) DO UPDATE
                   SET last_selected_at = EXCLUDED.last_selected_at""",
                (doctor_hash, patient_id),
            )
            await connection.execute(
                """DELETE FROM rag.doctor_recent_patients
                   WHERE doctor_hash = %s
                     AND patient_id NOT IN (
                       SELECT patient_id FROM rag.doctor_recent_patients
                       WHERE doctor_hash = %s
                       ORDER BY last_selected_at DESC, patient_id
                       LIMIT 8
                     )""",
                (doctor_hash, doctor_hash),
            )

    async def structured_facts(
        self,
        patient_id: str,
        admission_id: str | None,
        domains: Sequence[ClinicalDomain],
        limit: int = 100,
    ) -> StructuredFacts:
        """Fetch bounded facts directly for exhaustive history requests."""
        async with (
            self.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """SELECT chunk_id, admission_ids, domain, facts, content,
                              repeat_count, embedding
                       FROM rag.patient_chunks
                       WHERE patient_id = %s
                         AND (%s::text IS NULL OR %s = ANY(admission_ids))
                         AND domain = ANY(%s)
                       ORDER BY domain, chunk_id LIMIT %s""",
                (patient_id, admission_id, admission_id, list(domains), limit + 1),
            )
            chunks = [self._stored(row) for row in await cursor.fetchall()]
        return StructuredFacts(tuple(chunks[:limit]), len(chunks) > limit)

    @staticmethod
    def _stored(row: Mapping[str, object]) -> StoredChunk:
        """Convert a database row without returning the patient identifier."""
        return StoredChunk(
            chunk_id=str(row["chunk_id"]),
            admission_ids=tuple(
                str(item) for item in cast(Sequence[object], row["admission_ids"])
            ),
            domain=cast(ClinicalDomain, row["domain"]),
            facts={
                str(key): str(value)
                for key, value in cast(Mapping[object, object], row["facts"]).items()
            },
            content=str(row["content"]),
            repeat_count=int(cast(int, row["repeat_count"])),
            embedding=RagRepository._vector(row["embedding"]),
        )

    @staticmethod
    def _vector(value: object) -> FloatVector:
        """Convert pgvector's wrapper to the array used by MMR and embedding reuse."""
        if isinstance(value, Vector):
            return value.to_numpy().astype(np.float32, copy=False)
        return np.asarray(value, dtype=np.float32)
