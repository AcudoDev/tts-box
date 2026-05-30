import json
import pytest
import respx
import httpx
from app.providers.cartesia import CartesiaProvider


@pytest.fixture
def provider():
    return CartesiaProvider(api_key="ct-test")


@respx.mock
async def test_synthesize_posts_correctly(provider):
    route = respx.post("https://api.cartesia.ai/tts/bytes").mock(
        return_value=httpx.Response(200, content=b"MP3DATA", headers={"content-type": "audio/mpeg"})
    )
    audio, mime = await provider.synthesize("hi", "sonic-2", "voice-uuid")
    assert audio == b"MP3DATA"
    req = route.calls.last.request
    assert req.headers["x-api-key"] == "ct-test"
    assert req.headers["cartesia-version"] == "2024-11-13"
    body = json.loads(req.content)
    assert body["model_id"] == "sonic-2"
    assert body["transcript"] == "hi"
    assert body["voice"] == {"mode": "id", "id": "voice-uuid"}
    assert body["output_format"]["container"] == "mp3"


def test_list_models(provider):
    models = provider.list_models()
    assert "sonic-2" in models


@respx.mock
async def test_synthesize_passes_language(provider):
    respx.post("https://api.cartesia.ai/tts/bytes").mock(
        return_value=httpx.Response(200, content=b"x", headers={"content-type": "audio/mpeg"})
    )
    await provider.synthesize("salut", "sonic-2", "v", language="fr")
    body = json.loads(respx.calls.last.request.content)
    assert body["language"] == "fr"


@respx.mock
async def test_synthesize_omits_language_when_none(provider):
    respx.post("https://api.cartesia.ai/tts/bytes").mock(
        return_value=httpx.Response(200, content=b"x", headers={"content-type": "audio/mpeg"})
    )
    await provider.synthesize("hi", "sonic-2", "v")
    body = json.loads(respx.calls.last.request.content)
    assert "language" not in body


@respx.mock
async def test_list_voices_parses(provider):
    respx.get("https://api.cartesia.ai/voices").mock(return_value=httpx.Response(
        200,
        json=[
            {"id": "v1", "name": "Aria", "language": "en", "gender": "female"},
            {"id": "v2", "name": "Other"},
        ],
    ))
    voices = await provider.list_voices("sonic-2")
    assert voices[0].id == "v1"
    assert voices[0].name == "Aria"
    assert voices[0].language == "en"
    assert voices[1].language is None
    assert voices[0].multilingual is False
