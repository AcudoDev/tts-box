import json

import httpx
import pytest
import respx

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
    # OpenRouter dropped gpt-4o-mini-tts, so it is served directly again.
    assert "gpt-4o-mini-tts" in models


async def test_list_voices_returns_static(provider):
    voices = await provider.list_voices("tts-1-hd")
    names = {v.name for v in voices}
    assert {"alloy", "nova", "shimmer"} <= names


async def test_list_voices_are_multilingual():
    from app.providers.openai import OpenAIProvider
    voices = await OpenAIProvider(api_key="k").list_voices("tts-1")
    assert len(voices) == 9
    assert all(v.multilingual for v in voices)


async def test_list_voices_gpt4o_mini_has_13(provider):
    # tts-1 voices + ballad, verse, marin, cedar (gpt-4o-mini-tts only).
    voices = await provider.list_voices("gpt-4o-mini-tts")
    assert len(voices) == 13
    assert {"marin", "cedar", "ballad"} <= {v.id for v in voices}


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post("https://api.openai.com/v1/audio/speech").mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "tts-1", "nova")
