"""Resolve request-scoped access to initialized application services."""

from typing import cast

from doc_agent_common.config import AppSettings
from doc_agent_core.query_service import HistoryQueryService
from doc_agent_db.rag_repository import RagRepository
from fastapi import Request

from doc_agent_api.middleware import DoctorRateLimiter


def get_settings(request: Request) -> AppSettings:
    return cast(AppSettings, request.app.state.settings)


def get_repository(request: Request) -> RagRepository:
    return cast(RagRepository, request.app.state.rag_repository)


def get_history_service(request: Request) -> HistoryQueryService:
    return cast(HistoryQueryService, request.app.state.history_service)


def get_rate_limiter(request: Request) -> DoctorRateLimiter:
    return cast(DoctorRateLimiter, request.app.state.rate_limiter)
