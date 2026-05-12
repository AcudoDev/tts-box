from __future__ import annotations
import httpx
from app.providers.base import TTSProvider, Voice

URL = "https://api.openai.com/v1/audio/speech"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = ["tts-1", "tts-1-hd"]

_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo",
    "fable", "nova", "onyx", "sage", "shimmer", "verse",
]


class OpenAIProvider(TTSProvider):
    name = "openai"
    api_key_env = "OPENAI_API_KEY"

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        return [Voice(id=v, name=v) for v in _VOICES]

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        # OpenAI /v1/audio/speech has no language parameter; auto-detected.
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                URL,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "input": text,
                    "voice": voice_id,
                    "response_format": "mp3",
                },
            )
            r.raise_for_status()
            mime = r.headers.get("content-type", "audio/mpeg").split(";")[0]
            return (r.content, mime)
