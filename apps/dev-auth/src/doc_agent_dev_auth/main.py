"""Issue short-lived doctor JWTs for loopback development only."""

from datetime import UTC, datetime, timedelta

from doc_agent_common.config import DevAuthSettings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from doc_agent_dev_auth.keys import DevelopmentSigningKey
from doc_agent_dev_auth.schemas import (
    DevelopmentTokenRequest,
    DevelopmentTokenResponse,
)


class LoopbackOnlyMiddleware(BaseHTTPMiddleware):
    """Reject network clients because this server grants arbitrary test access."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse(status_code=403, content={"detail": "Loopback only."})
        return await call_next(request)


def create_app(settings: DevAuthSettings | None = None) -> FastAPI:
    configured = settings or DevAuthSettings.load()
    signing_key = DevelopmentSigningKey.generate()
    app = FastAPI(
        title="Doc Agent Local Development Auth",
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = configured
    app.state.signing_key = signing_key
    app.add_middleware(LoopbackOnlyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configured.allowed_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/.well-known/jwks.json", include_in_schema=False)
    async def jwks() -> dict[str, list[dict[str, str]]]:
        return signing_key.jwks()

    @app.post("/v1/token", response_model=DevelopmentTokenResponse)
    async def issue_token(body: DevelopmentTokenRequest) -> DevelopmentTokenResponse:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=configured.token_lifetime_seconds)
        token = signing_key.encode(
            {
                "sub": body.doctor_id,
                "patient_ids": body.patient_ids,
                "iss": configured.issuer,
                "aud": configured.audience,
                "iat": now,
                "exp": expires,
            }
        )
        return DevelopmentTokenResponse(
            access_token=token,
            expires_in=configured.token_lifetime_seconds,
        )

    return app
