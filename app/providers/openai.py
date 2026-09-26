from __future__ import annotations

import httpx

from app.providers.base import TTSProvider, Voice

URL = "https://api.openai.com/v1/audio/speech"
TIMEOUT = httpx.Timeout(30.0)

# gpt-4o-mini-tts is served here since OpenRouter dropped it (2026-09).
_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]

# Per OpenAI docs: tts-1/tts-1-hd take 9 voices; gpt-4o-mini-tts adds ballad, verse,
# marin and cedar.
_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
_GPT4O_MINI_VOICES = _VOICES + ["ballad", "verse", "marin", "cedar"]


class OpenAIProvider(TTSProvider):
    name = "openai"
    api_key_env = "OPENAI_API_KEY"
    voices_depend_on_model = True

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        ids = _GPT4O_MINI_VOICES if model == "gpt-4o-mini-tts" else _VOICES
        return [Voice(id=v, name=v) for v in ids]

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
