from __future__ import annotations
import asyncio
import hashlib
import time
from dataclasses import dataclass
from app.providers.base import TTSProvider, Voice


@dataclass(frozen=True)
class Selection:
    id: str            # option_id
    label: str         # nom de voix affiché
    provider: str
    model: str
    voice: str
    language: str | None


def option_id(provider: str, model: str, voice: str) -> str:
    return hashlib.sha1(f"{provider}|{model}|{voice}".encode()).hexdigest()[:12]


def parse_token(token: str) -> tuple[str, str, str]:
    """'provider|model|voice' → (provider, model, voice). Lève ValueError si malformé."""
    provider, model, voice = token.split("|", 2)  # ValueError si < 3 parts
    return provider, model, voice


def voice_matches_language(voice: Voice, lang: str) -> bool:
    return voice.multilingual or voice.language == lang


_TTL_SECONDS = 3600.0
# clé (provider_name, model) → (timestamp, list[Voice])
_cache: dict[tuple[str, str], tuple[float, list[Voice]]] = {}


def clear_cache() -> None:
    _cache.clear()


async def _voices_for(name: str, provider: TTSProvider, model: str, *, refresh: bool) -> list[Voice]:
    key = (name, model)
    if not refresh:
        hit = _cache.get(key)
        if hit and (time.monotonic() - hit[0]) < _TTL_SECONDS:
            return hit[1]
    voices = await provider.list_voices(model)
    _cache[(name, model)] = (time.monotonic(), voices)
    return voices


async def fetch_all(
    providers: dict[str, TTSProvider], *, refresh: bool = False
) -> dict[str, dict[str, list[Voice]]]:
    """{provider_name: {model: [Voice]}} — parallélisé, caché (TTL 1 h)."""
    async def _one(name: str, provider: TTSProvider) -> tuple[str, dict[str, list[Voice]]]:
        models = provider.list_models()
        if not provider.voices_depend_on_model and models:
            shared = await _voices_for(name, provider, models[0], refresh=refresh)
            # Réutilise la même liste pour tous les modèles, mais peuple le cache par modèle.
            by_model = {}
            for m in models:
                _cache[(name, m)] = (time.monotonic(), shared)
                by_model[m] = shared
            return name, by_model
        results = await asyncio.gather(
            *(_voices_for(name, provider, m, refresh=refresh) for m in models)
        )
        return name, dict(zip(models, results))

    pairs = await asyncio.gather(*(_one(n, p) for n, p in providers.items()))
    return dict(pairs)
