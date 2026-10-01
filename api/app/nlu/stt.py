"""Speech-to-text through Groq's Whisper (OpenAI-compatible transcription endpoint)."""

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.nlu.vocab import Vocabulary

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # ~5 min of opus; commands are a few seconds


class TranscriptionError(Exception):
    pass


def _prompt(vocab: Vocabulary) -> str:
    """Biases Whisper towards finance words and the user's own aliases (224-token limit)."""
    words = [alias for category in vocab.categories for alias in category.aliases]
    examples = "Paid 180 for auto. Chai 20 cash. Swiggy 450 on GPay. Salary credited 85,000."
    return f"{examples} {', '.join(dict.fromkeys(words))}"[:700]


@dataclass
class GroqTranscriber:
    api_key: str
    base_url: str
    model: str
    timeout: float
    transport: httpx.BaseTransport | None = None

    def transcribe(self, audio: bytes, filename: str, content_type: str, vocab: Vocabulary) -> str:
        try:
            with httpx.Client(timeout=self.timeout * 2, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (filename, audio, content_type)},
                    data={
                        "model": self.model,
                        "language": "en",
                        "temperature": "0",
                        "response_format": "json",
                        "prompt": _prompt(vocab),
                    },
                )
            response.raise_for_status()
            text = response.json()["text"]
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise TranscriptionError(type(exc).__name__) from exc
        return str(text).strip()


def transcriber_from_settings(settings: Settings) -> GroqTranscriber | None:
    if not settings.groq_api_key:
        return None
    return GroqTranscriber(
        settings.groq_api_key,
        settings.groq_base_url,
        settings.groq_stt_model,
        settings.ai_timeout_seconds,
    )
