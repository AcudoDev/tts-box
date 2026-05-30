from __future__ import annotations
import hashlib
from dataclasses import dataclass
from app.providers.base import Voice


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
