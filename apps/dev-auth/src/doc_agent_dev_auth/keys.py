"""Generate and expose the temporary RSA key used for local development JWTs."""

import base64
import secrets
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def _base64url(value: int) -> str:
    size = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


@dataclass(frozen=True)
class DevelopmentSigningKey:
    """Keep one process-local private key and publish only its public numbers."""

    private_key: rsa.RSAPrivateKey
    key_id: str

    @classmethod
    def generate(cls) -> "DevelopmentSigningKey":
        return cls(
            private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
            key_id=secrets.token_urlsafe(12),
        )

    def jwks(self) -> dict[str, list[dict[str, str]]]:
        numbers = self.private_key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.key_id,
                    "n": _base64url(numbers.n),
                    "e": _base64url(numbers.e),
                }
            ]
        }

    def encode(self, claims: dict[str, object]) -> str:
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.key_id, "typ": "JWT"},
        )
