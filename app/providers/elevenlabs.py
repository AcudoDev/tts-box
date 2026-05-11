from __future__ import annotations
import httpx
from app.providers.base import TTSProvider, Voice

BASE = "https://api.elevenlabs.io/v1"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = [
    "eleven_v3",
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_turbo_v2",
    "eleven_flash_v2_5",
    "eleven_flash_v2",
]


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    api_key_env = "ELEVENLABS_API_KEY"

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                f"{BASE}/voices",
                headers={"xi-api-key": self.api_key},
            )
            r.raise_for_status()
            data = r.json()
        out: list[Voice] = []
        for v in data.get("voices", []):
            labels = v.get("labels") or {}
            out.append(Voice(
                id=v["voice_id"],
                name=v["name"],
                language=labels.get("language"),
                gender=labels.get("gender"),
            ))
        return out

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        body: dict = {"text": text, "model_id": model}
        if language:
            body["language_code"] = language
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{BASE}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self.api_key,
                    "accept": "audio/mpeg",
                },
                json=body,
            )
            r.raise_for_status()
            mime = r.headers.get("content-type", "audio/mpeg").split(";")[0]
            return (r.content, mime)
