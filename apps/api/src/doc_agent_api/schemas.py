"""Validate public API requests and responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HistoryQueryRequest(BaseModel):
    """Accept one stateless question and an optional admission filter."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=2, max_length=2000)
    admission_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


class Citation(BaseModel):
    """Expose provenance after the request has passed patient authorization."""

    chunk_id: str
    domain: Literal["encounter", "medication", "microbiology", "drg"]
    admission_ids: list[str]
    repeat_count: int


class RetrievalMetadata(BaseModel):
    """Report non-sensitive retrieval behavior for client diagnostics."""

    strategy: Literal["hybrid_mmr", "structured"]
    dense_candidates: int = 0
    keyword_candidates: int = 0
    context_chunks: int = 0
    truncated: bool = False
    embedding_model: str
    generation_model: str


class HistoryQueryResponse(BaseModel):
    """Return a guarded answer and only its cited provenance."""

    status: Literal["answered", "blocked", "no_history"]
    answer: str
    citations: list[Citation]
    request_id: str
    retrieval: RetrievalMetadata


class PatientListItem(BaseModel):
    """Describe one authorized patient without returning clinical text."""

    patient_id: str
    admission_ids: list[str]
    domain_fact_counts: dict[str, int]
    source_row_count: int
    last_selected_at: datetime | None


class PatientListResponse(BaseModel):
    """Provide a bounded page for the patient wheel."""

    items: list[PatientListItem]
    total: int
    next_offset: int | None
    recent_patient_ids: list[str]
