import base64
import json

import httpx
import pytest
import respx

from app.providers.murf import MurfProvider


@pytest.fixture
def provider():
    return MurfProvider(api_key="mk-test")


def test_list_models(provider):
    assert "GEN2" in provider.list_models()


@respx.mock
async def test_synthesize_decodes_base64_audio(provider):
    raw = b"FAKEMP3BYTES"
    encoded = base64.b64encode(raw).decode()
    route = respx.post("https://api.murf.ai/v1/speech/generate").mock(
        return_value=httpx.Response(200, json={"encodedAudio": encoded, "audioLengthInSeconds": 1.2})
    )
    audio, mime = await provider.synthesize("salut", "GEN2", "fr-FR-axel", language="fr")
    assert audio == raw
    assert mime == "audio/mpeg"

    req = route.calls.last.request
    assert req.headers["api-key"] == "mk-test"
    body = json.loads(req.content)
    assert body["text"] == "salut"
    assert body["voiceId"] == "fr-FR-axel"
    assert body["modelVersion"] == "GEN2"
    assert body["format"] == "MP3"
    assert body["encodeAsBase64"] is True
    assert body["locale"] == "fr-FR"


@pytest.mark.parametrize("voice_id,language,locale", [
    ("Natalie", "fr", "fr-FR"),   # no prefix → language hint
    ("Natalie", "xx", None),      # unknown language → omitted
    ("Natalie", None, None),
])
@respx.mock
async def test_synthesize_locale_fallback(provider, voice_id, language, locale):
    route = respx.post("https://api.murf.ai/v1/speech/generate").mock(
        return_value=httpx.Response(200, json={"encodedAudio": base64.b64encode(b"x").decode()})
    )
    await provider.synthesize("hi", "GEN2", voice_id, language=language)
    assert json.loads(route.calls.last.request.content).get("locale") == locale


@respx.mock
async def test_synthesize_missing_audio_raises(provider):
    respx.post("https://api.murf.ai/v1/speech/generate").mock(
        return_value=httpx.Response(200, json={"audioFile": "https://cdn.murf.ai/abc.mp3"})
    )
    with pytest.raises(RuntimeError, match="encodedAudio"):
        await provider.synthesize("hi", "GEN2", "en-US-natalie")


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post("https://api.murf.ai/v1/speech/generate").mock(
        return_value=httpx.Response(401, json={"error": "invalid key"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "GEN2", "Natalie")


@respx.mock
async def test_list_voices_parses_locale_to_language(provider):
    respx.get("https://api.murf.ai/v1/speech/voices").mock(
        return_value=httpx.Response(200, json=[
            {"voiceId": "fr-FR-axel", "displayName": "Axel", "locale": "fr-FR", "gender": "Male"},
            {"voiceId": "en-US-natalie", "displayName": "Natalie", "locale": "en-US", "gender": "Female"},
        ])
    )
    voices = await provider.list_voices("GEN2")
    assert len(voices) == 2
    axel = next(v for v in voices if v.id == "fr-FR-axel")
    assert axel.name == "Axel"
    assert axel.language == "fr"
    assert axel.gender == "male"
    req = respx.calls.last.request
    assert req.headers["api-key"] == "mk-test"
