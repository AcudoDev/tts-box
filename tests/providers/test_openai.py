import json
import pytest
import respx
import httpx
from app.providers.openai import OpenAIProvider


@pytest.fixture
def provider():
    return OpenAIProvider(api_key="sk-test")


@respx.mock
async def test_synthesize_posts_correctly(provider):
    route = respx.post("https://api.openai.com/v1/audio/speech").mock(
        return_value=httpx.Response(200, content=b"MP3DATA", headers={"content-type": "audio/mpeg"})
    )
    audio, mime = await provider.synthesize("hello", "tts-1-hd", "nova")
    assert audio == b"MP3DATA"
    assert mime == "audio/mpeg"
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "tts-1-hd"
    assert body["input"] == "hello"
    assert body["voice"] == "nova"
    assert body["response_format"] == "mp3"


def test_list_models(provider):
    models = provider.list_models()
    assert "tts-1" in models
    assert "tts-1-hd" in models
    # gpt-4o-mini-tts is reached via OpenRouter instead.
    assert "gpt-4o-mini-tts" not in models


async def test_list_voices_returns_static(provider):
    voices = await provider.list_voices("tts-1-hd")
    names = {v.name for v in voices}
    assert {"alloy", "nova", "shimmer"} <= names


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post("https://api.openai.com/v1/audio/speech").mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "tts-1", "nova")
