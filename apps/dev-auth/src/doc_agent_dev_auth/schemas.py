"""Validate local token requests without accepting arbitrary JWT claims."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

IDENTIFIER_PATTERN = r"^[A-Za-z0-9._:-]+$"


class DevelopmentTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doctor_id: str = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)
    patient_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("patient_ids")
    @classmethod
    def validate_patient_ids(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            candidate = value.strip()
            if not candidate or len(candidate) > 128:
                raise ValueError("Patient IDs must contain 1 to 128 characters.")
            if any(
                character
                not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
                for character in candidate
            ):
                raise ValueError("A patient ID contains unsupported characters.")
            if candidate not in cleaned:
                cleaned.append(candidate)
        return cleaned


class DevelopmentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
