import pytest
from app.voice_catalog import option_id, parse_token, Selection, voice_matches_language
from app.providers.base import Voice


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
