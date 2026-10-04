"""Add request correlation, secure headers, and a bounded per-doctor rate limit."""

import hashlib
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("doc_agent.api")


class RequestSecurityMiddleware(BaseHTTPMiddleware):
    """Set safe response headers and request IDs without logging URL paths."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id[:128]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        connect_sources = ["'self'"]
        dev_auth_url = getattr(request.app.state, "dev_auth_public_url", None)
        if isinstance(dev_auth_url, str) and dev_auth_url:
            connect_sources.append(dev_auth_url)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            f"connect-src {' '.join(connect_sources)}; "
            "img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response


class DoctorRateLimiter:
    """Apply a small in-process limit keyed by a one-way doctor identifier."""

    def __init__(self, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._salt = secrets.token_bytes(32)

    def hash_identifier(self, value: str) -> str:
        """Make identifiers useful for local correlation without recording them."""
        return hashlib.sha256(self._salt + value.encode()).hexdigest()[:20]

    def allow(self, doctor_id: str) -> bool:
        """Discard expired timestamps and admit requests within the minute window."""
        now = time.monotonic()
        key = self.hash_identifier(doctor_id)
        events = self._events[key]
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= self._limit:
            return False
        events.append(now)
        return True


def rate_limit_response(request_id: str) -> JSONResponse:
    """Return a cache-safe limit response without sensitive request data."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Request rate limit exceeded.", "request_id": request_id},
        headers={"Retry-After": "60"},
    )
