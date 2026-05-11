import dataclasses
import pytest
from app.providers.base import Voice, TTSProvider, _REGISTRY


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


def test_subclass_auto_registers():
    class FakeProvider(TTSProvider):
        name = "fake_test"
        api_key_env = "FAKE_KEY"

        def list_models(self):
            return ["m1"]

        async def list_voices(self, model):
            return []

        async def synthesize(self, text, model, voice_id):
            return (b"", "audio/mpeg")

    assert "fake_test" in _REGISTRY
    assert _REGISTRY["fake_test"] is FakeProvider


def test_subclass_must_have_name():
    with pytest.raises(TypeError):
        class BadProvider(TTSProvider):
            def list_models(self): return []
            async def list_voices(self, model): return []
            async def synthesize(self, text, model, voice_id):
                return (b"", "audio/mpeg")
