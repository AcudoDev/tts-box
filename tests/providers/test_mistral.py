import base64
import json
import pytest
import respx
import httpx
from app.providers.mistral import MistralProvider


@pytest.fixture
def provider():
    return MistralProvider(api_key="ms-test")


def test_list_models(provider):
    assert "voxtral-mini-tts-2603" in provider.list_models()


@respx.mock
async def test_synthesize_decodes_base64_audio(provider):
    raw = b"FAKEMP3BYTES"
    encoded = base64.b64encode(raw).decode()
    route = respx.post("https://api.mistral.ai/v1/audio/speech").mock(
        return_value=httpx.Response(200, json={"audio_data": encoded})
    )
    audio, mime = await provider.synthesize(
        "salut", "voxtral-mini-tts-2603", "voice-uuid", language="fr"
    )
    assert audio == raw
    assert mime == "audio/mpeg"

    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer ms-test"
    body = json.loads(req.content)
    assert body["input"] == "salut"
    assert body["model"] == "voxtral-mini-tts-2603"
    assert body["voice_id"] == "voice-uuid"
    assert body["response_format"] == "mp3"


@respx.mock
async def test_synthesize_raises_when_audio_data_missing(provider):
    respx.post("https://api.mistral.ai/v1/audio/speech").mock(
        return_value=httpx.Response(200, json={})
    )
    with pytest.raises(RuntimeError, match="audio_data"):
        await provider.synthesize("hi", "voxtral-mini-tts-2603", "v")


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post("https://api.mistral.ai/v1/audio/speech").mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "voxtral-mini-tts-2603", "v")
