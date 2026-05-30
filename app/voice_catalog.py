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


# Langues courantes curées (code ISO 639-1 → nom natif). Toujours proposées.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "fr": "Français", "es": "Español", "de": "Deutsch",
    "it": "Italiano", "pt": "Português", "nl": "Nederlands", "pl": "Polski",
    "ru": "Русский", "tr": "Türkçe", "ar": "العربية", "hi": "हिन्दी",
    "zh": "中文", "ja": "日本語", "ko": "한국어",
}
_CURATED = set(LANGUAGE_NAMES)


def available_languages(fetched: dict[str, dict[str, list[Voice]]]) -> list[str]:
    langs: set[str] = set(_CURATED)
    for by_model in fetched.values():
        for voices in by_model.values():
            for v in voices:
                if v.language:
                    langs.add(v.language)
    return sorted(langs)


def groups_for_language(
    fetched: dict[str, dict[str, list[Voice]]],
    provider_order: dict[str, str],
    lang: str,
) -> list[tuple[str, list[tuple[str, list[Voice]]]]]:
    """[(provider, [(model, [Voice filtrées])])] — modèles/providers vides omis."""
    out: list[tuple[str, list[tuple[str, list[Voice]]]]] = []
    ordered = [p for p in provider_order if p in fetched] + [
        p for p in fetched if p not in provider_order
    ]
    for prov in ordered:
        models: list[tuple[str, list[Voice]]] = []
        for model, voices in fetched[prov].items():
            kept = [v for v in voices if voice_matches_language(v, lang)]
            if kept:
                models.append((model, kept))
        if models:
            out.append((prov, models))
    return out


def resolve_voice(
    fetched: dict[str, dict[str, list[Voice]]], provider: str, model: str, voice_id: str
) -> Voice | None:
    for v in fetched.get(provider, {}).get(model, []):
        if v.id == voice_id:
            return v
    return None
