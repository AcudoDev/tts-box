"""Estimated TTS costs per provider/model.

Prices are USD per 1 000 characters of input text. They're approximations:
- OpenAI tts-1/tts-1-hd are billed per character (exact).
- OpenAI gpt-4o-mini-tts is billed per audio token (rough char-based estimate).
- ElevenLabs is billed per credit (~1 credit/char for v2/v3, 0.5 for turbo, 0.33 for flash);
  the actual $/credit depends on the user's plan. We use the Creator plan rate (~$0.00022/credit)
  as a reasonable middle ground.
- Cartesia: typical published rate ~$65/1M chars for Sonic, slightly lower for Turbo.

This is a comparison tool — relative numbers matter more than absolute precision.
"""
from __future__ import annotations

# USD per 1000 characters of input text.
_PRICE_PER_1K_CHARS: dict[tuple[str, str], float] = {
    # --- OpenAI ---
    ("openai", "tts-1"):           0.015,   # $15/1M chars
    ("openai", "tts-1-hd"):        0.030,   # $30/1M chars
    ("openai", "gpt-4o-mini-tts"): 0.015,   # approximate (audio-token billing)

    # --- ElevenLabs (Creator plan, ~$0.00022/credit) ---
    ("elevenlabs", "eleven_v3"):              0.220,  # 1 credit/char
    ("elevenlabs", "eleven_multilingual_v2"): 0.220,  # 1 credit/char
    ("elevenlabs", "eleven_turbo_v2"):        0.110,  # 0.5 credit/char
    ("elevenlabs", "eleven_turbo_v2_5"):      0.110,  # 0.5 credit/char
    ("elevenlabs", "eleven_flash_v2"):        0.073,  # 0.33 credit/char
    ("elevenlabs", "eleven_flash_v2_5"):      0.073,  # 0.33 credit/char

    # --- Cartesia ---
    ("cartesia", "sonic-2"):     0.065,
    ("cartesia", "sonic"):       0.065,
    ("cartesia", "sonic-turbo"): 0.045,

    # --- Murf (Creator plan, ~$0.20/1k chars on subscription) ---
    ("murf", "GEN2"): 0.200,
}


def estimate_cost_usd(provider: str, model: str, char_count: int) -> float | None:
    """Return estimated cost in USD for synthesizing `char_count` characters.

    Returns None if pricing is unknown for the given provider/model.
    """
    rate = _PRICE_PER_1K_CHARS.get((provider, model))
    if rate is None:
        return None
    return char_count / 1000.0 * rate
