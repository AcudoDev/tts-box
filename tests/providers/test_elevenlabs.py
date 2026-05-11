import json
import pytest
import respx
import httpx
from app.providers.elevenlabs import ElevenLabsProvider


@pytest.fixture
def provider():
    return ElevenLabsProvider(api_key="test-key")


@respx.mock
async def test_synthesize_posts_correctly(provider):
    route = respx.post(
        "https://api.elevenlabs.io/v1/text-to-speech/voice123"
    ).mock(return_value=httpx.Response(200, content=b"MP3DATA", headers={"content-type": "audio/mpeg"}))

    audio, mime = await provider.synthesize("hello", "eleven_multilingual_v2", "voice123")

    assert audio == b"MP3DATA"
    assert mime == "audio/mpeg"
    req = route.calls.last.request
    assert req.headers["xi-api-key"] == "test-key"
    body = json.loads(req.content)
    assert body == {"text": "hello", "model_id": "eleven_multilingual_v2"}


@respx.mock
async def test_synthesize_raises_on_http_error(provider):
    respx.post("https://api.elevenlabs.io/v1/text-to-speech/v").mock(
        return_value=httpx.Response(401, json={"detail": "unauthorized"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "eleven_multilingual_v2", "v")


@respx.mock
async def test_list_voices_parses_response(provider):
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, json={
            "voices": [
                {"voice_id": "v1", "name": "Rachel", "labels": {"language": "en", "gender": "female"}},
                {"voice_id": "v2", "name": "Bob", "labels": {}},
            ]
        })
    )
    voices = await provider.list_voices("eleven_multilingual_v2")
    assert len(voices) == 2
    assert voices[0].id == "v1"
    assert voices[0].name == "Rachel"
    assert voices[0].language == "en"
    assert voices[1].language is None


def test_list_models_returns_known_models(provider):
    models = provider.list_models()
    assert "eleven_multilingual_v2" in models
