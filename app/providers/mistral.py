from __future__ import annotations
import base64
import httpx
from app.providers.base import TTSProvider, Voice

URL = "https://api.mistral.ai/v1/audio/speech"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = ["voxtral-mini-tts-2603"]


class MistralProvider(TTSProvider):
    """Mistral Voxtral TTS (released 2026)."""

    name = "mistral"
    api_key_env = "MISTRAL_API_KEY"

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        # GET /v1/audio/voices is paginated (10 per page, ~30 voices total).
        # We don't dynamically enumerate; users configure voice UUIDs in presets.yaml.
        return []

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        # Mistral TTS auto-detects language from text; language hint is ignored.
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                URL,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json={
                    "input": text,
                    "model": model,
                    "voice_id": voice_id,
                    "response_format": "mp3",
                },
            )
            r.raise_for_status()
            data = r.json()

        encoded = data.get("audio_data")
        if not encoded:
            raise RuntimeError("Mistral response missing audio_data")
        return (base64.b64decode(encoded), "audio/mpeg")
