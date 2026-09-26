"""Estimated TTS costs per provider/model.

Prices are USD per 1 000 characters of input text. They're approximations:
- OpenAI tts-1/tts-1-hd are billed per character (exact).
- OpenAI gpt-4o-mini-tts is billed per audio token (rough char-based estimate).
- OpenRouter TTS: per input character, except Gemini (text + audio tokens).
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
    ("openai", "gpt-4o-mini-tts"): 0.015,   # ~$0.015/min of audio (OpenAI estimate)
    ("openai", "tts-1"):           0.015,   # $15/1M chars
    ("openai", "tts-1-hd"):        0.030,   # $30/1M chars

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

    # --- Mistral Voxtral TTS is now reached via OpenRouter (see below). ---

    # --- Azure Speech (Neural Standard $16/1M chars on S0; F0 tier = 0.5M chars free/month) ---
    ("azure", "neural-standard"):     0.016,
    ("azure", "neural-hd"):           0.030,  # Dragon HD voices, premium tier
    ("azure", "neural-multilingual"): 0.024,  # multilingual voices, slight premium

    # --- OpenRouter (API pricing, vérifié le 2026-09-26) ---
    # TTS "prompt" price is per input character → ×1000. Gemini instead bills text
    # tokens (~250/1k chars) + audio output tokens (25/s, ~65 s of speech per 1k chars
    # → ~1625 tokens). Seed Audio's unit isn't documented → unpriced.
    ("openrouter", "google/gemini-3.8-flash-tts"):      250 * 0.0000005 + 1625 * 0.000009,
    ("openrouter", "google/gemini-3.8-flash-lite-tts"): 250 * 0.0000005 + 1625 * 0.000006,
    ("openrouter", "google/gemini-3.1-flash-tts-preview"): 250 * 0.000001 + 1625 * 0.00002,
    ("openrouter", "microsoft/mai-voice-2"):         0.022,
    ("openrouter", "microsoft/mai-voice-2-flash"):   0.015,
    ("openrouter", "x-ai/grok-voice-tts-1.0"):       0.015,
    ("openrouter", "minimax/speech-2.8-hd"):         0.100,
    ("openrouter", "minimax/speech-2.8-turbo"):      0.060,
    ("openrouter", "deepgram/aura-2"):               0.030,
    ("openrouter", "deepgram/flux-tts:free"):        0.0,
    ("openrouter", "qwen/qwen-audio-3.0-tts-plus"):  0.020,
    ("openrouter", "qwen/qwen-audio-3.0-tts-flash"): 0.015,
    ("openrouter", "fish-audio/s2.1-pro"):           0.015,
    ("openrouter", "fish-audio/s2.1-pro-free:free"): 0.0,
    ("openrouter", "fish-audio/s2-pro"):             0.015,
    ("openrouter", "fish-audio/s1"):                 0.015,
    ("openrouter", "mistralai/voxtral-mini-tts-2603"): 0.016,
    ("openrouter", "sesame/csm-1b"):                 0.007,
    ("openrouter", "hexgrad/kokoro-82m"):            0.004,
    ("openrouter", "canopylabs/orpheus-3b-0.1-ft"):  0.007,
}


def estimate_cost_usd(provider: str, model: str, char_count: int) -> float | None:
    """Return estimated cost in USD for synthesizing `char_count` characters.

    Returns None if pricing is unknown for the given provider/model.
    """
    rate = _PRICE_PER_1K_CHARS.get((provider, model))
    if rate is None:
        return None
    return char_count / 1000.0 * rate
