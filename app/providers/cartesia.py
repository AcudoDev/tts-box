from __future__ import annotations
import httpx
from app.providers.base import TTSProvider, Voice

BASE = "https://api.cartesia.ai"
API_VERSION = "2024-11-13"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = ["sonic-2", "sonic", "sonic-turbo"]


class CartesiaProvider(TTSProvider):
    name = "cartesia"
    api_key_env = "CARTESIA_API_KEY"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "cartesia-version": API_VERSION,
            "content-type": "application/json",
        }

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{BASE}/voices", headers=self._headers())
            r.raise_for_status()
            data = r.json()
        out: list[Voice] = []
        for v in data:
            out.append(Voice(
                id=v["id"],
                name=v["name"],
                language=v.get("language"),
                gender=v.get("gender"),
            ))
        return out

    async def synthesize(
        self, text: str, model: str, voice_id: str
    ) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{BASE}/tts/bytes",
                headers=self._headers(),
                json={
                    "model_id": model,
                    "transcript": text,
                    "voice": {"mode": "id", "id": voice_id},
                    "output_format": {
                        "container": "mp3",
                        "sample_rate": 44100,
                        "bit_rate": 128000,
                    },
                },
            )
            r.raise_for_status()
            mime = r.headers.get("content-type", "audio/mpeg").split(";")[0]
            return (r.content, mime)
