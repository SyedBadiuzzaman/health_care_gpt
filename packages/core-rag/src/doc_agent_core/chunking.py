"""Create short, domain-specific chunks from aggregated clinical facts."""

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Protocol

from doc_agent_common.config import (
    CHUNK_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
)

from doc_agent_core.state import AggregatedFact, ChunkDraft, ClinicalDomain

MAX_CHUNK_TOKENS = 220
TOKEN_OVERLAP = 20
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")

FIELD_LABELS = {
    "anchor_age": "Anchor age",
    "eventtype": "Clinical event",
    "drug": "Drug",
    "formulary_drug_cd": "Formulary code",
    "prod_strength": "Product strength",
    "dose_val_rx": "Recorded dose",
    "dose_unit_rx": "Dose unit",
    "form_unit_disp": "Dispensing unit",
    "route": "Route",
    "order_type": "Order type",
    "order_subtype": "Order subtype",
    "transaction_type": "Transaction type",
    "spec_type_desc": "Specimen",
    "test_name": "Test",
    "org_name": "Organism",
    "ab_name": "Antibiotic",
    "comments": "Recorded comments",
    "drg_type": "DRG type",
    "description": "DRG description",
    "drg_severity": "DRG severity",
    "drg_mortality": "DRG mortality",
}


class Tokenizer(Protocol):
    """Describe the tokenizer operations needed by the chunker."""

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]: ...

    def decode(
        self, token_ids: Sequence[int], *, skip_special_tokens: bool = True
    ) -> str: ...


def _clean_facts(facts: Mapping[str, object]) -> dict[str, str]:
    """Drop empty values and normalize remaining values to text."""
    cleaned: dict[str, str] = {}
    for key, value in facts.items():
        if value is None:
            continue
        text = EMAIL_PATTERN.sub("[email removed]", str(value)).strip()
        if text:
            cleaned[key] = text
    return cleaned


def render_fact(domain: ClinicalDomain, facts: dict[str, str]) -> str:
    """Render one fact with stable labels for lexical and semantic search."""
    lines = [f"Clinical domain: {domain}"]
    lines.extend(
        f"{FIELD_LABELS.get(key, key.replace('_', ' ').title())}: {value}"
        for key, value in facts.items()
    )
    return "\n".join(lines)


def _split_tokens(text: str, tokenizer: Tokenizer) -> list[str]:
    """Prefer field or sentence boundaries, then fall back to exact token windows."""
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if len(token_ids) <= MAX_CHUNK_TOKENS:
        return [text]
    boundary_tokens = {
        len(tokenizer.encode(text[: match.end()], add_special_tokens=False))
        for match in re.finditer(r"(?:[.!?](?=\s|$)|\n)", text)
    }
    parts: list[str] = []
    start = 0
    while start < len(token_ids):
        maximum_end = min(start + MAX_CHUNK_TOKENS, len(token_ids))
        usable_boundaries = [
            boundary
            for boundary in boundary_tokens
            if start + TOKEN_OVERLAP < boundary <= maximum_end
        ]
        end = max(usable_boundaries, default=maximum_end)
        window = token_ids[start:end]
        part = tokenizer.decode(window, skip_special_tokens=True).strip()
        if part:
            parts.append(part)
        if end >= len(token_ids):
            break
        start = end - TOKEN_OVERLAP
    return parts


def _content_hash(
    domain: ClinicalDomain, facts: dict[str, str], content: str, rendered: str
) -> str:
    """Hash canonical facts, adding split text only when one fact needs many chunks."""
    payload: dict[str, object] = {"domain": domain, "facts": facts}
    if content != rendered:
        payload["chunk_content"] = content
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _chunk_id(patient_id: str, content_hash: str) -> str:
    identity = "\0".join(
        (
            patient_id,
            content_hash,
            EMBEDDING_MODEL,
            EMBEDDING_REVISION,
            str(CHUNK_VERSION),
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def build_chunk_drafts(
    rows: Sequence[AggregatedFact], tokenizer: Tokenizer
) -> list[ChunkDraft]:
    """Merge duplicate facts per patient while retaining admission provenance."""
    merged: dict[
        tuple[str, str],
        tuple[ClinicalDomain, dict[str, str], str, set[str], int],
    ] = {}

    for row in rows:
        if not row.patient_id.strip() or not row.admission_id.strip():
            raise ValueError(
                "Every aggregated fact requires patient and admission IDs."
            )
        if row.repeat_count < 1:
            raise ValueError("Aggregated repeat counts must be positive.")
        facts = _clean_facts(row.facts)
        if not facts:
            continue
        rendered = render_fact(row.domain, facts)
        for content in _split_tokens(rendered, tokenizer):
            digest = _content_hash(row.domain, facts, content, rendered)
            key = (row.patient_id, digest)
            existing = merged.get(key)
            if existing is None:
                merged[key] = (
                    row.domain,
                    facts,
                    content,
                    {row.admission_id},
                    row.repeat_count,
                )
                continue
            domain, saved_facts, saved_content, admissions, count = existing
            admissions.add(row.admission_id)
            merged[key] = (
                domain,
                saved_facts,
                saved_content,
                admissions,
                count + row.repeat_count,
            )

    drafts = [
        ChunkDraft(
            chunk_id=_chunk_id(patient_id, digest),
            patient_id=patient_id,
            admission_ids=tuple(sorted(admissions)),
            domain=domain,
            facts=facts,
            content=content,
            content_hash=digest,
            repeat_count=repeat_count,
        )
        for (patient_id, digest), (
            domain,
            facts,
            content,
            admissions,
            repeat_count,
        ) in merged.items()
    ]
    return sorted(
        drafts, key=lambda item: (item.patient_id, item.domain, item.chunk_id)
    )


def count_domains(drafts: Sequence[ChunkDraft]) -> dict[str, dict[str, int]]:
    """Count unique chunks by patient and clinical domain."""
    counts: defaultdict[str, defaultdict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for draft in drafts:
        counts[draft.patient_id][draft.domain] += 1
    return {patient: dict(domains) for patient, domains in counts.items()}
