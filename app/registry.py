from __future__ import annotations
import importlib
import os
import pkgutil
from app.providers.base import TTSProvider, _REGISTRY


def _discover() -> None:
    """Import every module under app.providers to trigger __init_subclass__."""
    pkg = importlib.import_module("app.providers")
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_") and not mod.name.startswith("_mistral"):
            continue
        importlib.import_module(f"app.providers.{mod.name}")


def load_providers() -> dict[str, TTSProvider]:
    """Instantiate providers whose API key env var is set."""
    _discover()
    result: dict[str, TTSProvider] = {}
    for name, cls in _REGISTRY.items():
        key = os.getenv(cls.api_key_env)
        if key:
            result[name] = cls(api_key=key)
    return result


def known_provider_names() -> list[str]:
    _discover()
    return sorted(_REGISTRY.keys())
