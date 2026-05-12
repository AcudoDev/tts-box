from __future__ import annotations
import re
import struct
import httpx
from app.providers.base import TTSProvider, Voice

URL = "https://openrouter.ai/api/v1/audio/speech"
TIMEOUT = httpx.Timeout(60.0)

# Models routed through OpenRouter. We keep only the ones not already
# covered by our direct provider integrations (openai/mistral are duplicates).
_MODELS = [
    "google/gemini-3.1-flash-tts-preview",
    "sesame/csm-1b",
    "hexgrad/kokoro-82m",
    "canopylabs/orpheus-3b-0.1-ft",
    "zyphra/zonos-v0.1-transformer",
    "zyphra/zonos-v0.1-hybrid",
]

# Gemini TTS only supports response_format=pcm. The rest accept mp3.
_PCM_ONLY_MODELS = {"google/gemini-3.1-flash-tts-preview"}

_PCM_RE = re.compile(r"rate=(\d+).*?channels=(\d+)", re.IGNORECASE)


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int, channels: int, bits: int = 16) -> bytes:
    """Wrap raw PCM (signed 16-bit LE by convention) in a 44-byte WAV header."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
    )
    return header + pcm


class OpenRouterProvider(TTSProvider):
    """OpenRouter TTS — routes to multiple underlying providers via one endpoint."""

    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        # Voice availability depends on the underlying model; configured per preset.
        return []

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        response_format = "pcm" if model in _PCM_ONLY_MODELS else "mp3"
        body = {
            "model": model,
            "input": text,
            "voice": voice_id,
            "response_format": response_format,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                URL,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            content_type = r.headers.get("content-type", "audio/mpeg")
            audio = r.content

        # If the server returned raw PCM, wrap it in a WAV container so browsers
        # can play the <audio src=...> directly without extra client-side decoding.
        if content_type.lower().startswith("audio/pcm"):
            m = _PCM_RE.search(content_type)
            sample_rate = int(m.group(1)) if m else 24000
            channels = int(m.group(2)) if m else 1
            audio = _wrap_pcm_as_wav(audio, sample_rate, channels)
            return (audio, "audio/wav")

        mime = content_type.split(";")[0].strip()
        return (audio, mime or "audio/mpeg")
