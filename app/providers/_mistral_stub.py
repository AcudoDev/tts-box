from __future__ import annotations
from app.providers.base import TTSProvider, Voice


class MistralStubProvider(TTSProvider):
    """Placeholder. Mistral has no public TTS API yet (cutoff Jan 2026).

    When they release one, replace this with a real implementation.
    The file is `_mistral_stub.py` underscored so it's only auto-imported
    if explicitly enabled (the registry excludes underscore-prefixed modules
    by default, except those starting with `_mistral`).
    """
    name = "mistral"
    api_key_env = "MISTRAL_API_KEY"

    def list_models(self) -> list[str]:
        return ["voxtral-tts-placeholder"]

    async def list_voices(self, model: str) -> list[Voice]:
        return []

    async def synthesize(self, text: str, model: str, voice_id: str):
        raise NotImplementedError("Mistral TTS API is not publicly available yet.")
