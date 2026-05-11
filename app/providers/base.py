from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str | None = None
    gender: str | None = None


_REGISTRY: dict[str, type["TTSProvider"]] = {}


class TTSProvider(ABC):
    name: str
    api_key_env: str

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "name", None) or not getattr(cls, "api_key_env", None):
            raise TypeError(
                f"{cls.__name__} must define class attrs `name` and `api_key_env`"
            )
        _REGISTRY[cls.name] = cls

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
