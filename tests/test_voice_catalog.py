import pytest

from app.providers.base import TTSProvider, Voice
from app.voice_catalog import (
    LANGUAGE_NAMES,
    available_languages,
    clear_cache,
    fetch_all,
    flag_country,
    groups_for_language,
    option_id,
    parse_token,
    resolve_voice,
    voice_matches_language,
)


def test_option_id_is_deterministic():
    a = option_id("azure", "neural-standard", "fr-FR-DeniseNeural")
    b = option_id("azure", "neural-standard", "fr-FR-DeniseNeural")
    assert a == b
    assert len(a) == 12


def test_option_id_differs_by_input():
    assert option_id("a", "m", "v1") != option_id("a", "m", "v2")


def test_parse_token_roundtrip():
    assert parse_token("openrouter|google/gemini-3.1-flash-tts-preview|Kore") == (
        "openrouter", "google/gemini-3.1-flash-tts-preview", "Kore"
    )


def test_parse_token_rejects_malformed():
    with pytest.raises(ValueError):
        parse_token("only-one-part")


def test_voice_matches_language_localized():
    fr = Voice(id="v", name="Denise", language="fr")
    assert voice_matches_language(fr, "fr") is True
    assert voice_matches_language(fr, "de") is False


def test_voice_matches_language_generalist_appears_everywhere():
    # No declared language (OpenAI, Gemini, gpt-4o-mini) → shown under every language.
    generalist = Voice(id="v", name="nova")  # language=None
    assert voice_matches_language(generalist, "fr") is True
    assert voice_matches_language(generalist, "ar") is True


def test_voice_matches_language_declared_language_filters_even_if_multilingual():
    # A voice with a declared language (e.g. Voxtral 'Marie (French)') appears ONLY under
    # that language, even though its model is multilingual.
    marie = Voice(id="v", name="Marie (French)", language="fr")
    assert voice_matches_language(marie, "fr") is True
    assert voice_matches_language(marie, "de") is False


class _Counter(TTSProvider):
    name = "counter"
    api_key_env = "COUNTER_KEY"
    voices_depend_on_model = False

    def __init__(self):
        super().__init__(api_key="k")
        self.calls = 0

    def list_models(self): return ["m1", "m2"]
    async def list_voices(self, model):
        self.calls += 1
        return [Voice(id=f"{model}-v", name="V")]
    async def synthesize(self, *a, **k): return (b"", "audio/mpeg")


class _Boom(TTSProvider):
    """Provider whose voice listing fails (e.g. expired API key)."""

    name = "boom"
    api_key_env = "BOOM_KEY"

    def __init__(self):
        super().__init__(api_key="k")

    def list_models(self): return ["m"]
    async def list_voices(self, model):
        raise RuntimeError("bad key")
    async def synthesize(self, *a, **k): return (b"", "audio/mpeg")


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


async def test_fetch_all_returns_nested_structure():
    p = _Counter()
    result = await fetch_all({"counter": p})
    assert set(result["counter"].keys()) == {"m1", "m2"}


async def test_fetch_all_reuses_when_model_independent():
    p = _Counter()
    await fetch_all({"counter": p})
    # voices_depend_on_model is False → 1 seul appel réseau réutilisé pour m1 & m2
    assert p.calls == 1


async def test_fetch_all_uses_cache_second_time():
    p = _Counter()
    await fetch_all({"counter": p})
    await fetch_all({"counter": p})
    assert p.calls == 1  # second appel servi par le cache


async def test_fetch_all_refresh_bypasses_cache():
    p = _Counter()
    await fetch_all({"counter": p})
    await fetch_all({"counter": p}, refresh=True)
    assert p.calls == 2


async def test_fetch_all_skips_failing_provider():
    # A single broken provider (bad key, rate-limit, network) must not break the
    # whole catalog — the healthy providers still come back.
    good = _Counter()
    bad = _Boom()
    result = await fetch_all({"counter": good, "boom": bad})
    assert result["counter"]["m1"]          # healthy provider present
    assert result.get("boom", {}) == {}     # failing provider omitted, no crash


def _fetched():
    return {
        "azure": {"neural-standard": [
            Voice(id="fr-FR-DeniseNeural", name="Denise", language="fr"),
            Voice(id="de-DE-KatjaNeural", name="Katja", language="de"),
        ]},
        "openai": {"tts-1": [Voice(id="nova", name="nova")]},
    }


def test_available_languages_unions_locales_and_curated():
    langs = available_languages(_fetched())
    assert "fr" in langs and "de" in langs
    assert "en" in langs  # de la liste curée même si aucune voix localisée EN
    # triées, codes connus seulement
    assert langs == sorted(langs)


def test_groups_for_language_filters_localized_keeps_multilingual():
    groups = groups_for_language(_fetched(), {"azure": "Azure", "openai": "OpenAI"}, "de")
    flat = {(prov, v.id) for prov, models in groups for _, voices in models for v in voices}
    assert ("azure", "de-DE-KatjaNeural") in flat
    assert ("azure", "fr-FR-DeniseNeural") not in flat  # localisée fr, exclue
    assert ("openai", "nova") in flat                    # multilingue, gardée


def test_groups_omit_empty_models():
    groups = groups_for_language(_fetched(), {"azure": "Azure", "openai": "OpenAI"}, "fr")
    # le modèle openai tts-1 (multilingue) reste ; azure ne garde que Denise
    az = next(models for prov, models in groups if prov == "azure")
    assert all(len(voices) > 0 for _, voices in az)


def test_resolve_voice_finds_in_fetched():
    v = resolve_voice(_fetched(), "azure", "neural-standard", "fr-FR-DeniseNeural")
    assert v is not None and v.name == "Denise"
    assert resolve_voice(_fetched(), "azure", "neural-standard", "ghost") is None


def test_flag_country_codes():
    # Lowercase ISO 3166-1 codes for the flag-icons `fi-XX` class.
    assert flag_country("fr") == "fr"
    assert flag_country("en") == "gb"   # English → GB (representative)
    assert flag_country("ja") == "jp"
    assert flag_country(None) is None
    assert flag_country("zz") is None   # unknown language → no flag


def test_language_names_are_english_and_comprehensive():
    assert LANGUAGE_NAMES["fr"] == "French"
    assert LANGUAGE_NAMES["de"] == "German"
    # Codes providers report but that weren't in the old 15-entry curated set
    # must now resolve to a real English name (not just the raw code).
    for code in ["af", "wu", "yu", "iu", "nb", "ps", "or", "sw", "uz"]:
        name = LANGUAGE_NAMES.get(code)
        assert name and name != code


async def test_cache_hits_do_not_extend_ttl(monkeypatch):
    from types import SimpleNamespace

    import app.voice_catalog as vc
    now = [0.0]
    # Patch the module's `time` name only — the global clock also drives asyncio.
    monkeypatch.setattr(vc, "time", SimpleNamespace(monotonic=lambda: now[0]))
    p = _Counter()
    await fetch_all({"counter": p})
    now[0] = 3000.0
    await fetch_all({"counter": p})  # cache hit
    now[0] = 3700.0                  # > 1 h after the real fetch → must refetch
    await fetch_all({"counter": p})
    assert p.calls == 2
