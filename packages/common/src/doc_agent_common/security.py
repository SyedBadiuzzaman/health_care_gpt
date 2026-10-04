"""Provide shared one-way identifiers and safe URL checks."""

import hashlib
import hmac


def doctor_storage_key(doctor_id: str, secret: str) -> str:
    """Create a stable storage key without persisting the JWT subject."""
    return hmac.new(secret.encode(), doctor_id.encode(), hashlib.sha256).hexdigest()
