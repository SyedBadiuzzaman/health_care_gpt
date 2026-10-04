"""Serve authorized patient discovery and history queries."""

import time
from typing import Annotated

from doc_agent_common.config import AppSettings
from doc_agent_common.security import doctor_storage_key
from doc_agent_core.query_service import (
    GenerationFailure,
    HistoryQueryService,
    embedding_model_name,
)
from doc_agent_db.rag_repository import RagRepository
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response

from doc_agent_api.dependencies.authentication import (
    DoctorPrincipal,
    authenticated_principal,
    authorized_principal,
)
from doc_agent_api.dependencies.services import (
    get_history_service,
    get_rate_limiter,
    get_repository,
    get_settings,
)
from doc_agent_api.middleware import DoctorRateLimiter, logger
from doc_agent_api.schemas import (
    Citation,
    HistoryQueryRequest,
    HistoryQueryResponse,
    PatientListItem,
    PatientListResponse,
    RetrievalMetadata,
)

router = APIRouter(prefix="/v1/patients")


@router.get("", response_model=PatientListResponse)
async def list_patients(
    principal: Annotated[DoctorPrincipal, Depends(authenticated_principal)],
    repository: Annotated[RagRepository, Depends(get_repository)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    search: Annotated[str, Query(max_length=128)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientListResponse:
    """Return only indexed patients authorized by the current JWT."""
    secret = settings.recent_patient_hmac_key
    if secret is None:
        raise HTTPException(status_code=503, detail="Patient directory unavailable.")
    page = await repository.list_patients(
        sorted(principal.patient_ids),
        doctor_storage_key(principal.doctor_id, secret),
        search.strip(),
        limit,
        offset,
    )
    return PatientListResponse(
        items=[
            PatientListItem(
                patient_id=item.patient_id,
                admission_ids=list(item.admission_ids),
                domain_fact_counts=item.domain_fact_counts,
                source_row_count=item.source_row_count,
                last_selected_at=item.last_selected_at,
            )
            for item in page.items
        ],
        total=page.total,
        next_offset=page.next_offset,
        recent_patient_ids=list(page.recent_patient_ids),
    )


@router.post("/{patient_id}/selection", status_code=204)
async def record_patient_selection(
    principal: Annotated[DoctorPrincipal, Depends(authorized_principal)],
    repository: Annotated[RagRepository, Depends(get_repository)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    patient_id: Annotated[
        str,
        Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
    ],
) -> Response:
    """Persist a recent selection after patient authorization succeeds."""
    secret = settings.recent_patient_hmac_key
    if secret is None:
        raise HTTPException(status_code=503, detail="Patient directory unavailable.")
    await repository.record_patient_selection(
        doctor_storage_key(principal.doctor_id, secret), patient_id
    )
    return Response(status_code=204)


@router.post("/{patient_id}/history-query", response_model=HistoryQueryResponse)
async def history_query(
    request: Request,
    body: HistoryQueryRequest,
    principal: Annotated[DoctorPrincipal, Depends(authorized_principal)],
    service: Annotated[HistoryQueryService, Depends(get_history_service)],
    limiter: Annotated[DoctorRateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    patient_id: Annotated[
        str,
        Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
    ],
) -> HistoryQueryResponse:
    """Answer one guarded question about one authorized patient's history."""
    started = time.perf_counter()
    if not limiter.allow(principal.doctor_id):
        raise HTTPException(status_code=429, detail="Request rate limit exceeded.")
    try:
        outcome = await service.query(patient_id, body.question, body.admission_id)
    except GenerationFailure:
        raise HTTPException(
            status_code=502, detail="The history summary service failed safely."
        ) from None
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info(
        "history_query request=%s doctor=%s patient=%s status=%s latency_ms=%d "
        "dense=%d keyword=%d context=%d model=%s guardrail=%s",
        request.state.request_id,
        limiter.hash_identifier(principal.doctor_id),
        limiter.hash_identifier(patient_id),
        outcome.status,
        elapsed_ms,
        outcome.dense_candidates,
        outcome.keyword_candidates,
        outcome.context_chunks,
        settings.gemini_model,
        "blocked" if outcome.status == "blocked" else "passed",
    )
    return HistoryQueryResponse(
        status=outcome.status,
        answer=outcome.answer,
        citations=[
            Citation(
                chunk_id=chunk.chunk_id,
                domain=chunk.domain,
                admission_ids=list(chunk.admission_ids),
                repeat_count=chunk.repeat_count,
            )
            for chunk in outcome.cited_chunks
        ],
        request_id=request.state.request_id,
        retrieval=RetrievalMetadata(
            strategy=outcome.strategy,
            dense_candidates=outcome.dense_candidates,
            keyword_candidates=outcome.keyword_candidates,
            context_chunks=outcome.context_chunks,
            truncated=outcome.truncated,
            embedding_model=embedding_model_name(),
            generation_model=settings.gemini_model,
        ),
    )
