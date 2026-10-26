from app import registry
from app.providers.base import TTSProvider


def _make_provider(name: str, env_var: str):
    class P(TTSProvider):
        def list_models(self): return ["m"]
        async def list_voices(self, model): return []
        async def synthesize(self, text, model, voice_id, language=None):
            return (b"", "audio/mpeg")
    P.name, P.api_key_env = name, env_var
    return P


def test_load_returns_only_providers_with_keys(monkeypatch):
    alpha, beta = _make_provider("alpha", "ALPHA_KEY"), _make_provider("beta", "BETA_KEY")
    monkeypatch.setattr(registry, "PROVIDER_CLASSES", (alpha, beta))
    monkeypatch.setenv("ALPHA_KEY", "value-a")
    monkeypatch.delenv("BETA_KEY", raising=False)

    loaded = registry.load_providers()
    assert set(loaded) == {"alpha"}
    assert loaded["alpha"].api_key == "value-a"


def test_registry_lists_every_provider_once():
    names = [cls.name for cls in registry.PROVIDER_CLASSES]
    assert sorted(names) == ["azure", "cartesia", "elevenlabs", "murf", "openai", "openrouter"]
