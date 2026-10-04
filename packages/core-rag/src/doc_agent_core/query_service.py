"""Coordinate authorization-independent retrieval, generation, and output checks."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from doc_agent_common.config import EMBEDDING_MODEL, AppSettings

from doc_agent_core.embeddings import MiniLmEmbedder
from doc_agent_core.generation import (
    GeminiHistoryGenerator,
    redact_question_identifiers,
)
from doc_agent_core.guardrails import SAFETY_RESPONSE, GuardrailEngine
from doc_agent_core.retrieval import (
    hybrid_select,
    needs_structured_lookup,
    requested_domains,
)
from doc_agent_core.state import (
    ClinicalDomain,
    FloatVector,
    StoredChunk,
    StructuredFacts,
)


class GenerationFailure(RuntimeError):
    """Hide upstream model and malformed-output details from API clients."""


class HistoryRepository(Protocol):
    """Describe the patient-scoped reads required by the query pipeline."""

    async def structured_facts(
        self,
        patient_id: str,
        admission_id: str | None,
        domains: Sequence[ClinicalDomain],
        limit: int = 100,
    ) -> StructuredFacts: ...

    async def dense_search(
        self,
        patient_id: str,
        query_embedding: FloatVector,
        admission_id: str | None,
        limit: int = 30,
    ) -> list[StoredChunk]: ...

    async def keyword_search(
        self,
        patient_id: str,
        question: str,
        admission_id: str | None,
        limit: int = 30,
    ) -> list[StoredChunk]: ...


@dataclass(frozen=True)
class QueryOutcome:
    """Carry one service decision into the HTTP response layer."""

    status: Literal["answered", "blocked", "no_history"]
    answer: str
    cited_chunks: tuple[StoredChunk, ...]
    strategy: Literal["hybrid_mmr", "structured"]
    dense_candidates: int
    keyword_candidates: int
    context_chunks: int
    truncated: bool


class HistoryQueryService:
    """Answer one question without retaining cross-request state."""

    def __init__(
        self,
        settings: AppSettings,
        repository: HistoryRepository,
        embedder: MiniLmEmbedder,
        generator: GeminiHistoryGenerator,
        guardrails: GuardrailEngine,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.embedder = embedder
        self.generator = generator
        self.guardrails = guardrails

    async def query(
        self, patient_id: str, question: str, admission_id: str | None
    ) -> QueryOutcome:
        """Run both safety layers and keep every lookup scoped to one patient."""
        if not await self.guardrails.check_input(question):
            return self._blocked("hybrid_mmr")

        if needs_structured_lookup(question):
            facts = await self.repository.structured_facts(
                patient_id, admission_id, requested_domains(question)
            )
            chunks = list(facts.chunks)
            strategy: Literal["hybrid_mmr", "structured"] = "structured"
            dense_count = keyword_count = 0
            truncated = facts.truncated
        else:
            vector = (await asyncio.to_thread(self.embedder.encode, [question]))[0]
            dense, keyword = await asyncio.gather(
                self.repository.dense_search(patient_id, vector, admission_id),
                self.repository.keyword_search(patient_id, question, admission_id),
            )
            chunks = hybrid_select(question, dense, keyword, vector, limit=8)
            strategy = "hybrid_mmr"
            dense_count, keyword_count = len(dense), len(keyword)
            truncated = False

        if not chunks:
            return QueryOutcome(
                "no_history",
                "No recorded history was found for this selection.",
                (),
                strategy,
                dense_count,
                keyword_count,
                0,
                truncated,
            )
        try:
            safe_question = redact_question_identifiers(
                question, patient_id, admission_id
            )
            generated = await self.generator.generate(safe_question, chunks)
        except Exception as error:
            raise GenerationFailure(
                "The history summary could not be validated."
            ) from error
        if not await self.guardrails.check_output(generated.answer):
            return self._blocked(strategy)
        answer = generated.answer
        if truncated:
            answer += "\nThe result reached 100 facts; narrow the question for a complete answer."
        return QueryOutcome(
            "answered",
            answer,
            generated.chunks,
            strategy,
            dense_count,
            keyword_count,
            len(chunks),
            truncated,
        )

    @staticmethod
    def _blocked(strategy: Literal["hybrid_mmr", "structured"]) -> QueryOutcome:
        return QueryOutcome("blocked", SAFETY_RESPONSE, (), strategy, 0, 0, 0, False)


def embedding_model_name() -> str:
    """Expose a stable metadata value without constructing a model instance."""
    return EMBEDDING_MODEL
