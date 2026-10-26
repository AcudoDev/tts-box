from __future__ import annotations

import os

from app.providers.azure import AzureSpeechProvider
from app.providers.base import TTSProvider
from app.providers.cartesia import CartesiaProvider
from app.providers.elevenlabs import ElevenLabsProvider
from app.providers.murf import MurfProvider
from app.providers.openai import OpenAIProvider
from app.providers.openrouter import OpenRouterProvider

PROVIDER_CLASSES: tuple[type[TTSProvider], ...] = (
    ElevenLabsProvider,
    OpenAIProvider,
    CartesiaProvider,
    MurfProvider,
    AzureSpeechProvider,
    OpenRouterProvider,
)


def load_providers() -> dict[str, TTSProvider]:
    """Instantiate providers whose API key env var is set."""
    return {
        cls.name: cls(api_key=key)
        for cls in PROVIDER_CLASSES
        if (key := os.getenv(cls.api_key_env))
    }
