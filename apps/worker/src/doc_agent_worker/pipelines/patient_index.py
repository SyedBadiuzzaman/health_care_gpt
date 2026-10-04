"""Build the patient-scoped pgvector index from PostgreSQL source rows."""

import asyncio
import sys
import uuid

from doc_agent_common.config import AppSettings
from doc_agent_common.runtime import configure_asyncio_for_psycopg
from doc_agent_common.ssh_tunnel import SshTunnel
from doc_agent_core.chunking import build_chunk_drafts
from doc_agent_core.embeddings import MiniLmEmbedder
from doc_agent_core.state import FloatVector, IngestionSummary
from doc_agent_db.rag_repository import RagRepository
from doc_agent_db.source_queries import read_aggregated_facts


async def build_index(settings: AppSettings) -> IngestionSummary:
    """Run an idempotent full refresh while reusing byte-identical content vectors."""
    run_id = uuid.uuid4()
    embedder = await asyncio.to_thread(MiniLmEmbedder, str(settings.project / "models"))
    repository = RagRepository(settings)
    await repository.start_run(run_id)
    try:
        async with repository.connection() as source_connection:
            facts, source_rows, patient_counts = await read_aggregated_facts(
                source_connection
            )
        drafts = build_chunk_drafts(facts, embedder.tokenizer)
        patient_ids = sorted({draft.patient_id for draft in drafts})
        async with repository.connection() as connection:
            existing = await repository.existing_embeddings(connection, patient_ids)

        vectors: dict[str, FloatVector] = {}
        missing = []
        for draft in drafts:
            saved = existing.get((draft.patient_id, draft.content_hash))
            if saved is None:
                missing.append(draft)
            else:
                vectors[draft.chunk_id] = saved
        generated = await asyncio.to_thread(
            embedder.encode, [draft.content for draft in missing]
        )
        vectors.update(
            {
                draft.chunk_id: vector
                for draft, vector in zip(missing, generated, strict=True)
            }
        )
        await repository.replace_index(
            run_id,
            drafts,
            vectors,
            source_rows,
            patient_counts,
            len(drafts) - len(missing),
        )
        return IngestionSummary(
            source_rows=source_rows,
            patients=len(patient_ids),
            chunks=len(drafts),
            reused_embeddings=len(drafts) - len(missing),
            generated_embeddings=len(missing),
        )
    except Exception as error:
        await repository.mark_run_failed(run_id, type(error).__name__)
        raise


async def _run() -> None:
    settings = AppSettings.load()
    async with SshTunnel(settings):
        summary = await build_index(settings)
    print(
        "Index complete: "
        f"{summary.patients} patients, {summary.chunks} chunks, "
        f"{summary.generated_embeddings} generated and "
        f"{summary.reused_embeddings} reused embeddings."
    )


def main() -> None:
    """Run the index command and return a nonzero status on safe failures."""
    configure_asyncio_for_psycopg()
    try:
        asyncio.run(_run())
    except Exception as error:  # noqa: BLE001 - this is the CLI process boundary.
        print(f"Index failed ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
