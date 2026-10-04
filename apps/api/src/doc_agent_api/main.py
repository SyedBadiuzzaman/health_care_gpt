"""Assemble the stateless, JWT-protected medical-history API."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from doc_agent_common.config import AppSettings
from doc_agent_common.ssh_tunnel import SshTunnel
from doc_agent_core.embeddings import MiniLmEmbedder
from doc_agent_core.generation import GeminiHistoryGenerator
from doc_agent_core.guardrails import GuardrailEngine
from doc_agent_core.query_service import HistoryQueryService
from doc_agent_db.rag_repository import RagRepository
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from doc_agent_api.dependencies.authentication import JwtVerifier
from doc_agent_api.middleware import DoctorRateLimiter, RequestSecurityMiddleware
from doc_agent_api.routers import health, patients, runtime_config


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Construct the API and load model clients during application startup."""
    configured = settings or AppSettings.load()
    configured.validate_api()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with SshTunnel(configured):
            embedder = await asyncio.to_thread(
                MiniLmEmbedder, str(configured.project / "models")
            )
            repository = RagRepository(configured)
            app.state.jwt_verifier = JwtVerifier(configured)
            app.state.rate_limiter = DoctorRateLimiter(configured.rate_limit_per_minute)
            app.state.rag_repository = repository
            app.state.history_service = HistoryQueryService(
                configured,
                repository,
                embedder,
                GeminiHistoryGenerator(configured),
                GuardrailEngine(configured),
            )
            yield

    app = FastAPI(
        title="Patient Medical History RAG",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = configured
    app.state.dev_auth_public_url = (
        configured.dev_auth_public_url if configured.dev_auth_enabled else None
    )
    app.add_middleware(RequestSecurityMiddleware)
    if configured.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(configured.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    app.include_router(health.router)
    app.include_router(runtime_config.router)
    app.include_router(patients.router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/app", status_code=307)

    @app.get("/app", include_in_schema=False)
    async def frontend() -> FileResponse:
        return FileResponse(configured.web_root / "index.html")

    app.mount(
        "/assets",
        StaticFiles(directory=configured.web_root),
        name="frontend-assets",
    )
    return app
