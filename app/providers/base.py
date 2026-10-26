from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str | None = None
    gender: str | None = None


def locale_from_voice_id(voice_id: str) -> str | None:
    """'<lang>-<REGION>-<Name...>' (Azure, Murf) → '<lang>-<REGION>', else None."""
    parts = voice_id.split("-", 2)
    if len(parts) >= 2 and len(parts[0]) == 2 and len(parts[1]) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return None


def mime_of(r: httpx.Response) -> str:
    """Bare mime type of a response ('audio/mpeg; x=y' → 'audio/mpeg'), mp3 by default."""
    return r.headers.get("content-type", "").split(";")[0].strip() or "audio/mpeg"


class TTSProvider(ABC):
    name: str
    api_key_env: str
    voices_depend_on_model: bool = False  # True si list_voices dépend du modèle (OpenRouter)

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    async def list_voices(self, model: str) -> list[Voice]: ...

    @abstractmethod
    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        """Return (audio_bytes, mime_type).

        `language` is an ISO 639-1 code (e.g. "fr", "en"). Providers that
        accept a language override pass it through; others ignore it.
        Auto-detection is used when None.
        """
