import json
import struct

import httpx
import pytest
import respx

from app.providers.openrouter import (
    _PCM_ONLY_MODELS,
    OpenRouterProvider,
    _wrap_pcm_as_wav,
)


@pytest.fixture
def provider():
    return OpenRouterProvider(api_key="or-test")


def test_wrap_pcm_writes_valid_wav_header():
    pcm = b"\x00\x00" * 100  # 100 silent samples
    wav = _wrap_pcm_as_wav(pcm, sample_rate=24000, channels=1)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[12:16] == b"fmt "
    # Sample rate at offset 24 (little-endian uint32)
    assert struct.unpack_from("<I", wav, 24)[0] == 24000
    # Channels at offset 22 (little-endian uint16)
    assert struct.unpack_from("<H", wav, 22)[0] == 1
    # Data section follows
    assert wav[36:40] == b"data"
    # Data size
    assert struct.unpack_from("<I", wav, 40)[0] == len(pcm)


def test_list_models_includes_gemini_and_sesame(provider):
    models = provider.list_models()
    assert "google/gemini-3.1-flash-tts-preview" in models
    assert "sesame/csm-1b" in models


def test_pcm_only_set_contains_gemini():
    assert "google/gemini-3.1-flash-tts-preview" in _PCM_ONLY_MODELS


@respx.mock
async def test_synthesize_mp3_passthrough(provider):
    route = respx.post("https://openrouter.ai/api/v1/audio/speech").mock(
        return_value=httpx.Response(200, content=b"MP3DATA", headers={"content-type": "audio/mpeg"})
    )
    audio, mime = await provider.synthesize("hi", "sesame/csm-1b", "nova")
    assert audio == b"MP3DATA"
    assert mime == "audio/mpeg"
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "sesame/csm-1b"
    assert body["response_format"] == "mp3"
    assert body["voice"] == "nova"


@respx.mock
async def test_synthesize_pcm_wrapped_as_wav(provider):
    pcm = b"\x10\x00" * 50
    respx.post("https://openrouter.ai/api/v1/audio/speech").mock(
        return_value=httpx.Response(
            200,
            content=pcm,
            headers={"content-type": "audio/pcm;rate=24000;channels=1"},
        )
    )
    audio, mime = await provider.synthesize(
        "salut", "google/gemini-3.1-flash-tts-preview", "Kore", language="fr"
    )
    assert mime == "audio/wav"
    assert audio[:4] == b"RIFF"
    assert audio[8:12] == b"WAVE"
    # Header (44) + pcm payload (100) = 144 bytes
    assert len(audio) == 44 + len(pcm)


@respx.mock
async def test_gemini_forces_pcm_format(provider):
    route = respx.post("https://openrouter.ai/api/v1/audio/speech").mock(
        return_value=httpx.Response(
            200,
            content=b"\x00\x00",
            headers={"content-type": "audio/pcm;rate=24000;channels=1"},
        )
    )
    await provider.synthesize("x", "google/gemini-3.1-flash-tts-preview", "Kore")
    body = json.loads(route.calls.last.request.content)
    assert body["response_format"] == "pcm"


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post("https://openrouter.ai/api/v1/audio/speech").mock(
        return_value=httpx.Response(402, json={"error": {"message": "Insufficient credits"}})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("x", "sesame/csm-1b", "nova")


async def test_list_voices_gemini_has_30_multilingual(provider):
    voices = await provider.list_voices("google/gemini-3.1-flash-tts-preview")
    assert len(voices) == 30
    assert all(v.multilingual for v in voices)
    assert any(v.id == "Kore" for v in voices)


async def test_list_voices_gpt4o_mini_has_13(provider):
    # Verified 2026-05-30 against OpenAI's current catalogue: 13 voices
    # (the older 11 + the two newest, marin and cedar). All multilingual.
    voices = await provider.list_voices("openai/gpt-4o-mini-tts-2025-12-15")
    assert {v.id for v in voices} >= {"alloy", "onyx", "shimmer", "marin", "cedar"}
    assert len(voices) == 13
    assert all(v.multilingual for v in voices)


async def test_list_voices_voxtral_has_french_marie(provider):
    # Verified preset ids from Mistral's official hosted demo (gb_/en_/fr_ scheme).
    voices = await provider.list_voices("mistralai/voxtral-mini-tts-2603")
    ids = {v.id for v in voices}
    assert "fr_marie_neutral" in ids
    assert "en_paul_neutral" in ids
    marie = next(v for v in voices if v.id == "fr_marie_neutral")
    assert marie.language == "fr"
    assert marie.multilingual is True


async def test_list_voices_kokoro_derives_language_from_prefix(provider):
    voices = await provider.list_voices("hexgrad/kokoro-82m")
    assert len(voices) == 54  # Verified full Kokoro preset catalogue
    siwis = next(v for v in voices if v.id == "ff_siwis")
    assert siwis.language == "fr"
    assert siwis.multilingual is False
    # Prefix → language: 'a'/'b' English, 'j' Japanese, 'z' Mandarin.
    assert next(v for v in voices if v.id == "af_heart").language == "en"
    assert next(v for v in voices if v.id == "jf_alpha").language == "ja"
    assert next(v for v in voices if v.id == "zf_xiaobei").language == "zh"


async def test_list_voices_orpheus_has_7_english(provider):
    # Verified against OpenRouter's live supported_voices (7, English-only).
    voices = await provider.list_voices("canopylabs/orpheus-3b-0.1-ft")
    assert {v.id for v in voices} == {"tara", "leah", "jess", "leo", "dan", "mia", "zac"}
    assert all(v.language == "en" and not v.multilingual for v in voices)


async def test_list_voices_zonos_has_named_accent_voices(provider):
    # Verified: OpenRouter exposes 5 fixed named voices for both Zonos variants.
    voices = await provider.list_voices("zyphra/zonos-v0.1-transformer")
    assert {v.id for v in voices} == {
        "american_female", "american_male", "british_female", "british_male", "random",
    }


async def test_list_voices_cloning_model_is_empty(provider):
    # sesame/csm-1b has no named voices (speaker-id / cloning only) → UI free-voice mode.
    assert await provider.list_voices("sesame/csm-1b") == []


def test_provider_voices_depend_on_model(provider):
    assert provider.voices_depend_on_model is True
