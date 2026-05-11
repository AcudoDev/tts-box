from app.pricing import estimate_cost_usd


def test_known_provider_model_returns_cost():
    cost = estimate_cost_usd("openai", "tts-1", 1000)
    assert cost == 0.015


def test_proportional_to_char_count():
    base = estimate_cost_usd("openai", "tts-1", 1000)
    doubled = estimate_cost_usd("openai", "tts-1", 2000)
    assert doubled == 2 * base


def test_unknown_provider_returns_none():
    assert estimate_cost_usd("unknown", "any", 100) is None


def test_unknown_model_returns_none():
    assert estimate_cost_usd("openai", "fake-model-xyz", 100) is None


def test_zero_chars_zero_cost():
    assert estimate_cost_usd("openai", "tts-1", 0) == 0.0


def test_elevenlabs_flash_cheaper_than_v3():
    long_text = 5000
    v3 = estimate_cost_usd("elevenlabs", "eleven_v3", long_text)
    flash = estimate_cost_usd("elevenlabs", "eleven_flash_v2_5", long_text)
    assert flash < v3
