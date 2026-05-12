import json
import struct
import pytest
import respx
import httpx
from app.providers.openrouter import (
    OpenRouterProvider,
    _wrap_pcm_as_wav,
    _PCM_ONLY_MODELS,
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
