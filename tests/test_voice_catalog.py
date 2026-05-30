import pytest
from app.voice_catalog import (
    option_id,
    parse_token,
    Selection,
    voice_matches_language,
    fetch_all,
    clear_cache,
)
from app.providers.base import Voice, TTSProvider


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
    fr = Voice(id="v", name="Denise", language="fr", multilingual=False)
    assert voice_matches_language(fr, "fr") is True
    assert voice_matches_language(fr, "de") is False


def test_voice_matches_language_multilingual_always():
    ml = Voice(id="v", name="Rachel", multilingual=True)
    assert voice_matches_language(ml, "fr") is True
    assert voice_matches_language(ml, "de") is True


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
