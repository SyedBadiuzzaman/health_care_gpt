"""Load application settings without exposing secret values."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from psycopg.conninfo import make_conninfo

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBEDDING_DIMENSION = 384
CHUNK_VERSION = 3


def _load_values(project: Path) -> dict[str, str]:
    """Merge the private .env file with process-level overrides."""
    file_values = dotenv_values(
        project / ".env", interpolate=False, encoding="utf-8-sig"
    )
    merged = {key: value for key, value in file_values.items() if value is not None}
    merged.update(os.environ)
    return merged


def _required(values: dict[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing setting: {name}")
    return value


def _boolean(values: dict[str, str], name: str, default: bool) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


@dataclass(frozen=True)
class AppSettings:
    """Hold database, model, and authorization settings for one process."""

    project: Path
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str = field(repr=False)
    use_ssh_tunnel: bool = True
    tunnel_local_port: int = 55432
    ssh_user: str = "ubuntu"
    ssh_key_path: Path = Path("Keys/health.pem")
    ssh_known_hosts_path: Path = Path("Keys/known_hosts")
    gemini_api_key: str | None = field(default=None, repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_jwks_url: str | None = None
    jwt_patient_ids_claim: str = "patient_ids"
    jwt_doctor_id_claim: str = "sub"
    jwt_algorithms: tuple[str, ...] = ("RS256", "ES256")
    recent_patient_hmac_key: str | None = field(default=None, repr=False)
    cors_origins: tuple[str, ...] = ()
    rate_limit_per_minute: int = 60
    guardrails_path: Path = Path("packages/core-rag/guardrails")
    web_root: Path = Path("apps/web/src")
    dev_auth_enabled: bool = False
    dev_auth_public_url: str = "http://127.0.0.1:8001"

    @classmethod
    def load(cls, project: Path | None = None) -> "AppSettings":
        """Load settings relative to the project root."""
        root = (project or Path.cwd()).resolve()
        values = _load_values(root)
        port = int(_required(values, "DATABASE_PORT"))
        tunnel_port = int(values.get("DATABASE_TUNNEL_LOCAL_PORT", "55432"))
        rate_limit = int(values.get("API_RATE_LIMIT_PER_MINUTE", "60"))
        for name, value in (
            ("DATABASE_PORT", port),
            ("DATABASE_TUNNEL_LOCAL_PORT", tunnel_port),
        ):
            if not 1 <= value <= 65535:
                raise ValueError(f"{name} must be between 1 and 65535.")
        if not 1 <= rate_limit <= 10_000:
            raise ValueError("API_RATE_LIMIT_PER_MINUTE is outside the allowed range.")

        key_path = Path(values.get("SSH_KEY_PATH", "Keys/health.pem"))
        known_hosts = Path(values.get("SSH_KNOWN_HOSTS_PATH", "Keys/known_hosts"))
        if not key_path.is_absolute():
            key_path = root / key_path
        if not known_hosts.is_absolute():
            known_hosts = root / known_hosts
        guardrails_path = Path(
            values.get("GUARDRAILS_PATH", "packages/core-rag/guardrails")
        )
        if not guardrails_path.is_absolute():
            guardrails_path = root / guardrails_path
        web_root = Path(values.get("WEB_ROOT", "apps/web/src"))
        if not web_root.is_absolute():
            web_root = root / web_root
        dev_auth_enabled = _boolean(values, "DEV_AUTH_ENABLED", False)
        dev_auth_public_url = values.get(
            "DEV_AUTH_PUBLIC_URL", "http://127.0.0.1:8001"
        ).rstrip("/")
        parsed_dev_url = urlparse(dev_auth_public_url)
        if dev_auth_enabled and (
            parsed_dev_url.scheme != "http"
            or parsed_dev_url.hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError("DEV_AUTH_PUBLIC_URL must use a loopback HTTP address.")
        algorithms = tuple(
            part.strip()
            for part in values.get("JWT_ALGORITHMS", "RS256,ES256").split(",")
            if part.strip()
        )
        if not algorithms or not set(algorithms) <= {
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
        }:
            raise ValueError("JWT_ALGORITHMS contains an unsupported algorithm.")

        jwt_issuer = values.get("JWT_ISSUER") or None
        jwt_audience = values.get("JWT_AUDIENCE") or None
        jwt_jwks_url = values.get("JWT_JWKS_URL") or None
        if dev_auth_enabled:
            jwt_issuer = values.get("DEV_AUTH_ISSUER", dev_auth_public_url)
            jwt_audience = values.get("DEV_AUTH_AUDIENCE", "doc-agent")
            jwt_jwks_url = values.get(
                "DEV_AUTH_JWKS_URL", f"{dev_auth_public_url}/.well-known/jwks.json"
            )

        return cls(
            project=root,
            database_host=_required(values, "DATABASE_HOST"),
            database_port=port,
            database_name=_required(values, "DATABASE_NAME"),
            database_user=_required(values, "DATABASE_USER"),
            database_password=_required(values, "DATABASE_PASSWORD"),
            use_ssh_tunnel=_boolean(values, "DATABASE_USE_SSH_TUNNEL", True),
            tunnel_local_port=tunnel_port,
            ssh_user=values.get("SSH_USER", "ubuntu"),
            ssh_key_path=key_path,
            ssh_known_hosts_path=known_hosts,
            gemini_api_key=values.get("GEMINI_API_KEY") or None,
            gemini_model=values.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            jwt_jwks_url=jwt_jwks_url,
            jwt_patient_ids_claim=values.get("JWT_PATIENT_IDS_CLAIM", "patient_ids"),
            jwt_doctor_id_claim=values.get("JWT_DOCTOR_ID_CLAIM", "sub"),
            jwt_algorithms=algorithms,
            recent_patient_hmac_key=values.get("RECENT_PATIENT_HMAC_KEY") or None,
            cors_origins=tuple(
                origin.strip()
                for origin in values.get("CORS_ORIGINS", "").split(",")
                if origin.strip()
            ),
            rate_limit_per_minute=rate_limit,
            guardrails_path=guardrails_path,
            web_root=web_root,
            dev_auth_enabled=dev_auth_enabled,
            dev_auth_public_url=dev_auth_public_url,
        )

    def database_conninfo(self) -> str:
        """Build a libpq connection string for the active network path."""
        host = "127.0.0.1" if self.use_ssh_tunnel else self.database_host
        port = self.tunnel_local_port if self.use_ssh_tunnel else self.database_port
        return make_conninfo(
            host=host,
            port=port,
            dbname=self.database_name,
            user=self.database_user,
            password=self.database_password,
            connect_timeout=10,
            application_name="doc-agent-rag",
        )

    def validate_api(self) -> None:
        """Require security and model settings before serving requests."""
        missing = [
            name
            for name, value in (
                ("GEMINI_API_KEY", self.gemini_api_key),
                ("JWT_ISSUER", self.jwt_issuer),
                ("JWT_AUDIENCE", self.jwt_audience),
                ("JWT_JWKS_URL", self.jwt_jwks_url),
                ("RECENT_PATIENT_HMAC_KEY", self.recent_patient_hmac_key),
            )
            if not value
        ]
        if missing:
            raise ValueError("Missing API settings: " + ", ".join(missing))


@dataclass(frozen=True)
class DevAuthSettings:
    """Hold the loopback-only token service configuration."""

    issuer: str = "http://127.0.0.1:8001"
    audience: str = "doc-agent"
    allowed_origin: str = "http://127.0.0.1:8000"
    token_lifetime_seconds: int = 3600

    @classmethod
    def load(cls, project: Path | None = None) -> "DevAuthSettings":
        root = (project or Path.cwd()).resolve()
        values = _load_values(root)
        lifetime = int(values.get("DEV_AUTH_TOKEN_LIFETIME_SECONDS", "3600"))
        if not 60 <= lifetime <= 3600:
            raise ValueError("DEV_AUTH_TOKEN_LIFETIME_SECONDS must be 60 to 3600.")
        issuer = values.get("DEV_AUTH_ISSUER", "http://127.0.0.1:8001").rstrip("/")
        parsed = urlparse(issuer)
        if parsed.scheme != "http" or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("DEV_AUTH_ISSUER must use a loopback HTTP address.")
        return cls(
            issuer=issuer,
            audience=values.get("DEV_AUTH_AUDIENCE", "doc-agent"),
            allowed_origin=values.get(
                "DEV_AUTH_ALLOWED_ORIGIN", "http://127.0.0.1:8000"
            ).rstrip("/"),
            token_lifetime_seconds=lifetime,
        )
