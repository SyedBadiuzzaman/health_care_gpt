"""Shared typed values for ingestion and retrieval."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np
from numpy.typing import NDArray

ClinicalDomain = Literal["encounter", "medication", "microbiology", "drg"]
type FloatVector = NDArray[np.float32]


@dataclass(frozen=True)
class AggregatedFact:
    """Represent one SQL-aggregated fact within one admission."""

    patient_id: str
    admission_id: str
    domain: ClinicalDomain
    facts: dict[str, str]
    repeat_count: int


@dataclass(frozen=True)
class ChunkDraft:
    """Represent a patient-level unique chunk before vectorization."""

    chunk_id: str
    patient_id: str
    admission_ids: tuple[str, ...]
    domain: ClinicalDomain
    facts: dict[str, str]
    content: str
    content_hash: str
    repeat_count: int


@dataclass(frozen=True)
class StoredChunk:
    """Represent a searchable chunk returned from PostgreSQL."""

    chunk_id: str
    admission_ids: tuple[str, ...]
    domain: ClinicalDomain
    facts: dict[str, str]
    content: str
    repeat_count: int
    embedding: FloatVector


@dataclass(frozen=True)
class RankedChunk:
    """Keep a fused relevance score beside a stored chunk."""

    chunk: StoredChunk
    relevance: float


@dataclass(frozen=True)
class PatientSummary:
    """Provide deterministic patient-level counts without clinical text."""

    admission_count: int
    source_row_count: int
    domain_fact_counts: dict[str, int]


@dataclass(frozen=True)
class PatientDirectoryEntry:
    """Expose selector metadata without loading clinical text."""

    patient_id: str
    admission_ids: tuple[str, ...]
    domain_fact_counts: dict[str, int]
    source_row_count: int
    last_selected_at: datetime | None


@dataclass(frozen=True)
class PatientDirectoryPage:
    """Return one authorized selector page and its recent ordering."""

    items: tuple[PatientDirectoryEntry, ...]
    total: int
    next_offset: int | None
    recent_patient_ids: tuple[str, ...]


@dataclass(frozen=True)
class StructuredFacts:
    """Hold a bounded deterministic result for exhaustive questions."""

    chunks: tuple[StoredChunk, ...]
    truncated: bool


@dataclass(frozen=True)
class IngestionSummary:
    """Report non-identifying counts from one completed ingestion."""

    source_rows: int
    patients: int
    chunks: int
    reused_embeddings: int
    generated_embeddings: int
