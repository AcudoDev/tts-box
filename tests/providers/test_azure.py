import pytest
import respx
import httpx
from app.providers.azure import AzureSpeechProvider, _build_ssml


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_REGION", "francecentral")
    return AzureSpeechProvider(api_key="az-test")


def test_build_ssml_escapes_text():
    ssml = _build_ssml("Hello <b>world</b> & co.", "fr-FR-HenriNeural", "fr-FR")
    assert "&lt;b&gt;" in ssml
    assert "&amp;" in ssml
    assert "fr-FR-HenriNeural" in ssml
    assert "xml:lang='fr-FR'" in ssml


def test_build_ssml_handles_voice_with_colon():
    ssml = _build_ssml("Salut.", "fr-FR-Vivienne:DragonHDLatestNeural", None)
    # The colon-bearing voice must be properly quoted as an attribute.
    assert "fr-FR-Vivienne:DragonHDLatestNeural" in ssml
    # Defaults to fr-FR when language is None.
    assert "xml:lang='fr-FR'" in ssml


def test_list_models(provider):
    assert "neural" in provider.list_models()


@respx.mock
async def test_synthesize_posts_ssml_and_returns_audio(provider):
    route = respx.post(
        "https://francecentral.tts.speech.microsoft.com/cognitiveservices/v1"
    ).mock(return_value=httpx.Response(200, content=b"MP3DATA"))

    audio, mime = await provider.synthesize(
        "Bonjour.", "neural", "fr-FR-HenriNeural", language="fr-FR"
    )
    assert audio == b"MP3DATA"
    assert mime == "audio/mpeg"

    req = route.calls.last.request
    assert req.headers["ocp-apim-subscription-key"] == "az-test"
    assert req.headers["content-type"] == "application/ssml+xml"
    assert "audio-24khz-96kbitrate-mono-mp3" in req.headers["x-microsoft-outputformat"]
    body = req.content.decode()
    assert "Bonjour." in body
    assert "fr-FR-HenriNeural" in body


@respx.mock
async def test_synthesize_http_error(provider):
    respx.post(
        "https://francecentral.tts.speech.microsoft.com/cognitiveservices/v1"
    ).mock(return_value=httpx.Response(401, text="unauthorized"))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize("hi", "neural", "fr-FR-HenriNeural")


@respx.mock
async def test_list_voices_parses(provider):
    respx.get(
        "https://francecentral.tts.speech.microsoft.com/cognitiveservices/voices/list"
    ).mock(return_value=httpx.Response(200, json=[
        {"ShortName": "fr-FR-HenriNeural", "DisplayName": "Henri", "Locale": "fr-FR", "Gender": "Male"},
        {"ShortName": "en-US-JennyNeural", "DisplayName": "Jenny", "Locale": "en-US", "Gender": "Female"},
    ]))
    voices = await provider.list_voices("neural")
    assert voices[0].id == "fr-FR-HenriNeural"
    assert voices[0].language == "fr"
    assert voices[0].gender == "male"
    assert voices[1].language == "en"
