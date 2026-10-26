import dataclasses

from app.providers.base import TTSProvider, Voice, locale_from_voice_id


def test_voice_minimal_fields():
    v = Voice(id="abc", name="Alice")
    assert v.id == "abc"
    assert v.name == "Alice"
    assert v.language is None
    assert v.gender is None


def test_voice_all_fields():
    v = Voice(id="abc", name="Alice", language="fr", gender="female")
    assert v.language == "fr"
    assert v.gender == "female"


def test_voice_frozen():
    v = Voice(id="abc", name="Alice")
    try:
        v.id = "xyz"
        raise AssertionError("Voice should be frozen")
    except dataclasses.FrozenInstanceError:
        pass


def test_locale_from_voice_id():
    assert locale_from_voice_id("fr-FR-DeniseNeural") == "fr-FR"
    assert locale_from_voice_id("fr-FR-Vivienne:DragonHDLatestNeural") == "fr-FR"
    assert locale_from_voice_id("en-US-natalie") == "en-US"
    assert locale_from_voice_id("Natalie") is None
    assert locale_from_voice_id("weird") is None


def test_provider_voices_depend_on_model_defaults_false():
    assert TTSProvider.voices_depend_on_model is False
