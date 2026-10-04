"""Verify bearer JWTs and enforce patient-level authorization."""

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from doc_agent_common.config import AppSettings
from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class DoctorPrincipal:
    """Keep only the identity and authorization needed for this request."""

    doctor_id: str
    patient_ids: frozenset[str]


class JwtVerifier:
    """Validate signatures and required claims against the configured JWKS."""

    def __init__(self, settings: AppSettings) -> None:
        if (
            not settings.jwt_jwks_url
            or not settings.jwt_issuer
            or not settings.jwt_audience
        ):
            raise ValueError("JWT verification settings are incomplete.")
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._algorithms = list(settings.jwt_algorithms)
        self._doctor_claim = settings.jwt_doctor_id_claim
        self._patient_claim = settings.jwt_patient_ids_claim
        self._jwks = jwt.PyJWKClient(settings.jwt_jwks_url, cache_keys=True)

    async def verify(self, token: str) -> DoctorPrincipal:
        """Resolve the signing key off-loop and validate all security claims."""
        try:
            key = await asyncio.to_thread(self._jwks.get_signing_key_from_jwt, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", self._doctor_claim]},
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        doctor_id = claims.get(self._doctor_claim)
        allowed = claims.get(self._patient_claim)
        if not isinstance(doctor_id, str) or not doctor_id.strip():
            raise HTTPException(status_code=401, detail="Invalid bearer token.")
        if not isinstance(allowed, list) or any(
            not isinstance(item, str) for item in allowed
        ):
            raise HTTPException(
                status_code=403, detail="Patient access is not granted."
            )
        return DoctorPrincipal(doctor_id=doctor_id, patient_ids=frozenset(allowed))


async def authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> DoctorPrincipal:
    """Verify the bearer token before any protected route reads application data."""
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    verifier: JwtVerifier = request.app.state.jwt_verifier
    return await verifier.verify(credentials.credentials)


async def authorized_principal(
    patient_id: Annotated[
        str,
        Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
    ],
    principal: Annotated[DoctorPrincipal, Depends(authenticated_principal)],
) -> DoctorPrincipal:
    """Reject a patient route before it reaches the database when access is absent."""
    if patient_id not in principal.patient_ids:
        raise HTTPException(status_code=403, detail="Patient access is not granted.")
    return principal
