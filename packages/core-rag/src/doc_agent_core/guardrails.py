"""Apply deterministic and NeMo checks around medical-history generation."""

import re
from typing import Any, Literal

from doc_agent_common.config import AppSettings

SAFETY_RESPONSE = (
    "I can only summarize the patient’s recorded history. I can’t recommend "
    "medications, dosages, diagnoses, or treatment actions."
)

_PROSPECTIVE_TREATMENT = re.compile(
    r"\b(you|doctor|clinician|we|i)\s+(?:should|must|need to|ought to)\s+"
    r"(?:prescribe|administer|start|stop|increase|decrease|change|adjust|diagnose|treat)\b"
    r"|\b(?:recommend|suggest|advise)\s+(?:a\s+)?(?:medication|drug|dose|dosage|treatment)\b"
    r"|\bwhat\s+(?:should|would)\s+(?:i|we|the doctor)\s+"
    r"(?:prescribe|administer|diagnose|do|change)\b"
    r"|\bwhat\s+(?:should|would)\s+you\s+"
    r"(?:prescribe|administer|diagnose|do|change)\b"
    r"|\bwhat\s+diagnosis\s+should\s+(?:i|we|the doctor)\s+(?:make|give)\b"
    r"|\b(?:write|create|give)\s+(?:me\s+)?(?:a\s+)?(?:fictional\s+)?"
    r"(?:prescription|treatment plan|dosing schedule)\b"
    r"|\b(?:optimal|best|appropriate)\s+(?:dose|dosage|drug|treatment)\b"
    r"|\b(?:decide|make|give)\s+(?:the\s+)?diagnosis\b",
    flags=re.IGNORECASE,
)

_DIRECTIVE_OUTPUT = re.compile(
    r"\b(?:you|the doctor|the clinician)\s+(?:should|must|need to|ought to)\b"
    r"|\b(?:prescribe|administer|start|stop|increase|decrease|adjust)\s+"
    r"(?:the\s+)?(?:dose|dosage|medication|drug|treatment)\b"
    r"|(?:^|[.!?]\s)(?:please\s+)?"
    r"(?:take|give|use|continue|discontinue|switch|consider|monitor|order)\b"
    r"|\b(?:recommended|optimal|best)\s+(?:dose|dosage|treatment)\s+is\b"
    r"|\b(?:diagnose|treat)\s+(?:the patient|this|with)\b"
    r"|\bi (?:recommend|suggest|advise)\b",
    flags=re.IGNORECASE,
)


def deterministic_input_allowed(text: str) -> bool:
    """Block prospective treatment requests while allowing recorded-history questions."""
    return _PROSPECTIVE_TREATMENT.search(text) is None


def deterministic_output_allowed(text: str) -> bool:
    """Catch directive phrasing even when the model-level rail misses it."""
    return _DIRECTIVE_OUTPUT.search(text) is None


class GuardrailEngine:
    """Use NeMo with its official LangChain Google GenAI provider."""

    def __init__(self, settings: AppSettings) -> None:
        if settings.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY is required for guardrails.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        from nemoguardrails import LLMRails, RailsConfig

        class NeMoGoogleGenAI(ChatGoogleGenerativeAI):
            """Translate NeMo's generic token limit to Google's provider field."""

            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)

            def bind(self, **kwargs: Any) -> Any:
                if "max_tokens" in kwargs:
                    kwargs["max_output_tokens"] = kwargs.pop("max_tokens")
                return super().bind(**kwargs)

        config = RailsConfig.from_path(str(settings.guardrails_path))
        llm = NeMoGoogleGenAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
        self._rails: Any = LLMRails(config=config, llm=llm)

    async def check_input(self, text: str) -> bool:
        """Fail closed when either deterministic or NeMo input checks reject."""
        if not deterministic_input_allowed(text):
            return False
        return await self._nemo_check("INPUT", text)

    async def check_output(self, text: str) -> bool:
        """Fail closed when either deterministic or NeMo output checks reject."""
        if not deterministic_output_allowed(text):
            return False
        try:
            result = await self._rails.generate_async(
                messages=[
                    {
                        "role": "user",
                        "content": "Review the generated history summary.",
                    },
                    {"role": "assistant", "content": text},
                ],
                options={
                    "rails": {
                        "input": False,
                        "dialog": False,
                        "retrieval": False,
                        "output": True,
                    }
                },
            )
        except Exception:  # noqa: BLE001 - any rail failure must deny the response.
            return False
        return self._content(result).strip() == text.strip()

    async def _nemo_check(self, stage: Literal["INPUT", "OUTPUT"], text: str) -> bool:
        prompt = (
            f"POLICY_{stage}: Classify the following text. Return only ALLOW or BLOCK.\n"
            f"<text>{text}</text>"
        )
        try:
            result = await self._rails.generate_async(
                messages=[{"role": "user", "content": prompt}],
                options={
                    "rails": {
                        "input": True,
                        "dialog": False,
                        "retrieval": False,
                        "output": False,
                    }
                },
            )
        except Exception:  # noqa: BLE001 - any rail failure must deny the response.
            return False
        content = self._content(result).strip()
        # NeMo versions return either the classifier decision or allowed input unchanged.
        return content.upper() == "ALLOW" or content == prompt.strip()

    @staticmethod
    def _content(result: object) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            value = result.get("content", "")
            return value if isinstance(value, str) else ""
        response = getattr(result, "response", None)
        if isinstance(response, list) and response:
            message = response[-1]
            if isinstance(message, dict):
                value = message.get("content", "")
                return value if isinstance(value, str) else ""
        return ""
