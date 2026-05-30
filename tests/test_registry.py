import pytest

from app.providers.base import _REGISTRY, TTSProvider


@pytest.fixture(autouse=True)
def clean_registry():
    snapshot = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


def _make_provider(name: str, env_var: str):
    # Use type() so attrs exist when __init_subclass__ runs.
    async def _voices(self, m): return []
    async def _synth(self, t, m, v): return (b"", "audio/mpeg")
    attrs = {
        "name": name,
        "api_key_env": env_var,
        "list_models": lambda self: ["m"],
        "list_voices": _voices,
        "synthesize": _synth,
    }
    return type(f"P_{name}", (TTSProvider,), attrs)


def test_load_returns_only_providers_with_keys(monkeypatch):
    from app.registry import load_providers
    _make_provider("alpha", "ALPHA_KEY")
    _make_provider("beta", "BETA_KEY")

    monkeypatch.setenv("ALPHA_KEY", "value-a")
    monkeypatch.delenv("BETA_KEY", raising=False)

    loaded = load_providers()
    assert "alpha" in loaded
    assert "beta" not in loaded
    assert loaded["alpha"].api_key == "value-a"


def test_load_returns_empty_when_no_keys(monkeypatch):
    from app.registry import load_providers
    _make_provider("gamma", "GAMMA_KEY")
    monkeypatch.delenv("GAMMA_KEY", raising=False)
    # Only the dynamically-created provider should be considered for this test;
    # real providers aren't imported yet so registry only contains 'gamma'.
    loaded = load_providers()
    assert "gamma" not in loaded


def test_load_lists_known_provider_names(monkeypatch):
    from app.registry import known_provider_names
    _make_provider("delta", "DELTA_KEY")
    names = known_provider_names()
    assert "delta" in names
