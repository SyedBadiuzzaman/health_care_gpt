"""Expose non-sensitive browser bootstrap configuration."""

from typing import Annotated

from doc_agent_common.config import AppSettings
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from doc_agent_api.dependencies.services import get_settings

router = APIRouter(prefix="/v1")


class RuntimeConfigResponse(BaseModel):
    development_auth_enabled: bool
    development_auth_url: str | None


@router.get("/runtime-config", response_model=RuntimeConfigResponse)
async def runtime_configuration(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> RuntimeConfigResponse:
    return RuntimeConfigResponse(
        development_auth_enabled=settings.dev_auth_enabled,
        development_auth_url=(
            settings.dev_auth_public_url if settings.dev_auth_enabled else None
        ),
    )
