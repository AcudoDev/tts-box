from __future__ import annotations

import asyncio
import hashlib
import sys
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
        try:
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
        except Exception as e:
            # A broken provider (bad key, rate-limit, network outage) must not break
            # the whole catalog — skip it and let the healthy providers render.
            print(f"[voice_catalog] listing voices for '{name}' failed: {e}", file=sys.stderr)
            return name, {}

    pairs = await asyncio.gather(*(_one(n, p) for n, p in providers.items()))
    return dict(pairs)


# Single source of truth: ISO 639-1 code → (English name, representative ISO 3166-1
# country for the flag, or None). Covers every code our providers report (incl. a few
# Azure non-standard truncations like "wu"/"yu"). The flag's country is *representative*
# of the language, not authoritative (e.g. "en" → GB, "pt" → PT, "ar" → SA).
_LANGUAGES: dict[str, tuple[str, str | None]] = {
    "af": ("Afrikaans", "ZA"), "am": ("Amharic", "ET"), "ar": ("Arabic", "SA"),
    "as": ("Assamese", "IN"), "az": ("Azerbaijani", "AZ"), "ba": ("Bashkir", "RU"),
    "be": ("Belarusian", "BY"), "bg": ("Bulgarian", "BG"), "bn": ("Bengali", "BD"),
    "bo": ("Tibetan", "CN"), "bs": ("Bosnian", "BA"), "ca": ("Catalan", "ES"),
    "cs": ("Czech", "CZ"), "cy": ("Welsh", "GB"), "da": ("Danish", "DK"),
    "de": ("German", "DE"), "dv": ("Divehi", "MV"), "el": ("Greek", "GR"),
    "en": ("English", "GB"), "eo": ("Esperanto", None), "es": ("Spanish", "ES"),
    "et": ("Estonian", "EE"), "eu": ("Basque", "ES"), "fa": ("Persian", "IR"),
    "fi": ("Finnish", "FI"), "fil": ("Filipino", "PH"), "fo": ("Faroese", "FO"),
    "fr": ("French", "FR"), "ga": ("Irish", "IE"), "gl": ("Galician", "ES"),
    "gu": ("Gujarati", "IN"), "ha": ("Hausa", "NG"), "he": ("Hebrew", "IL"),
    "hi": ("Hindi", "IN"), "hr": ("Croatian", "HR"), "hu": ("Hungarian", "HU"),
    "hy": ("Armenian", "AM"), "id": ("Indonesian", "ID"), "is": ("Icelandic", "IS"),
    "it": ("Italian", "IT"), "iu": ("Inuktitut", "CA"), "ja": ("Japanese", "JP"),
    "jv": ("Javanese", "ID"), "ka": ("Georgian", "GE"), "kk": ("Kazakh", "KZ"),
    "km": ("Khmer", "KH"), "kn": ("Kannada", "IN"), "ko": ("Korean", "KR"),
    "ku": ("Kurdish", "TR"), "ky": ("Kyrgyz", "KG"), "lb": ("Luxembourgish", "LU"),
    "lo": ("Lao", "LA"), "lt": ("Lithuanian", "LT"), "lv": ("Latvian", "LV"),
    "mk": ("Macedonian", "MK"), "ml": ("Malayalam", "IN"), "mn": ("Mongolian", "MN"),
    "mr": ("Marathi", "IN"), "ms": ("Malay", "MY"), "mt": ("Maltese", "MT"),
    "my": ("Burmese", "MM"), "nb": ("Norwegian Bokmål", "NO"), "ne": ("Nepali", "NP"),
    "nl": ("Dutch", "NL"), "nn": ("Norwegian Nynorsk", "NO"), "no": ("Norwegian", "NO"),
    "or": ("Odia", "IN"), "pa": ("Punjabi", "IN"), "pl": ("Polish", "PL"),
    "ps": ("Pashto", "AF"), "pt": ("Portuguese", "PT"), "ro": ("Romanian", "RO"),
    "ru": ("Russian", "RU"), "sd": ("Sindhi", "PK"), "si": ("Sinhala", "LK"),
    "sk": ("Slovak", "SK"), "sl": ("Slovenian", "SI"), "so": ("Somali", "SO"),
    "sq": ("Albanian", "AL"), "sr": ("Serbian", "RS"), "su": ("Sundanese", "ID"),
    "sv": ("Swedish", "SE"), "sw": ("Swahili", "TZ"), "ta": ("Tamil", "IN"),
    "te": ("Telugu", "IN"), "tg": ("Tajik", "TJ"), "th": ("Thai", "TH"),
    "ti": ("Tigrinya", "ER"), "tk": ("Turkmen", "TM"), "tl": ("Filipino", "PH"),
    "tr": ("Turkish", "TR"), "tt": ("Tatar", "RU"), "uk": ("Ukrainian", "UA"),
    "ur": ("Urdu", "PK"), "uz": ("Uzbek", "UZ"), "vi": ("Vietnamese", "VN"),
    "wu": ("Wu Chinese", "CN"), "xh": ("Xhosa", "ZA"), "yu": ("Cantonese", "HK"),
    "zh": ("Chinese", "CN"), "zu": ("Zulu", "ZA"),
}

# Lookup table for display names (comprehensive — every reported code resolves).
LANGUAGE_NAMES: dict[str, str] = {code: name for code, (name, _) in _LANGUAGES.items()}

# Common languages ALWAYS offered in the selector, even if only multilingual voices
# (which can speak them) are configured. Kept deliberately separate from LANGUAGE_NAMES:
# the names map is a lookup table, not the "always show these" set.
_CURATED = {"en", "fr", "es", "de", "it", "pt", "nl", "pl", "ru", "tr", "ar", "hi", "zh", "ja", "ko"}


def _flag_emoji(country: str) -> str:
    """ISO 3166-1 alpha-2 country code → flag emoji (regional indicator pair)."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country.upper())


def flag_for(language: str | None) -> str:
    """Flag emoji for a language code. None or unknown → globe."""
    if not language:
        return "🌐"
    country = (_LANGUAGES.get(language) or (None, None))[1]
    return _flag_emoji(country) if country else "🌐"


def flag_country(language: str | None) -> str | None:
    """Lowercase ISO 3166-1 country code for a language's flag (consumed by the
    flag-icons CSS class `fi-XX`). None when there's no representative country."""
    if not language:
        return None
    country = (_LANGUAGES.get(language) or (None, None))[1]
    return country.lower() if country else None


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
