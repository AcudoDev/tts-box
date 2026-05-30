import httpx
import pytest
import respx

from app import voice_catalog
from app.providers.azure import AzureSpeechProvider, _build_ssml, _locale_from_voice


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_REGION", "francecentral")
    return AzureSpeechProvider(api_key="az-test")


@pytest.fixture
def az(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    return AzureSpeechProvider(api_key="az-key")


def test_locale_from_voice_id():
    assert _locale_from_voice("fr-FR-DeniseNeural") == "fr-FR"
    assert _locale_from_voice("fr-FR-Vivienne:DragonHDLatestNeural") == "fr-FR"
    assert _locale_from_voice("weird") is None


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
    # Locale is derived from the voiceId even when language is None.
    assert "xml:lang='fr-FR'" in ssml


def test_list_models(provider):
    models = provider.list_models()
    assert "neural-standard" in models
    assert "neural-hd" in models
    assert "neural-multilingual" in models


_VOICE_LIST = [
    {"ShortName": "fr-FR-DeniseNeural", "DisplayName": "Denise", "Locale": "fr-FR", "Gender": "Female"},
    {"ShortName": "fr-FR-Remy:DragonHDLatestNeural", "DisplayName": "Remy", "Locale": "fr-FR", "Gender": "Male"},
    {"ShortName": "fr-FR-VivienneMultilingualNeural", "DisplayName": "Vivienne", "Locale": "fr-FR", "Gender": "Female"},
    {"ShortName": "de-DE-KatjaNeural", "DisplayName": "Katja", "Locale": "de-DE", "Gender": "Female"},
]


@respx.mock
async def test_list_voices_standard_excludes_hd_and_multilingual(az):
    respx.get("https://westeurope.tts.speech.microsoft.com/cognitiveservices/voices/list").mock(
        return_value=httpx.Response(200, json=_VOICE_LIST)
    )
    voices = await az.list_voices("neural-standard")
    ids = {v.id for v in voices}
    assert "fr-FR-DeniseNeural" in ids
    assert "de-DE-KatjaNeural" in ids
    assert "fr-FR-Remy:DragonHDLatestNeural" not in ids
    assert "fr-FR-VivienneMultilingualNeural" not in ids
    denise = next(v for v in voices if v.id == "fr-FR-DeniseNeural")
    assert denise.language == "fr"
    assert denise.multilingual is False


@respx.mock
async def test_list_voices_hd_only(az):
    respx.get("https://westeurope.tts.speech.microsoft.com/cognitiveservices/voices/list").mock(
        return_value=httpx.Response(200, json=_VOICE_LIST)
    )
    voices = await az.list_voices("neural-hd")
    assert {v.id for v in voices} == {"fr-FR-Remy:DragonHDLatestNeural"}


@respx.mock
async def test_list_voices_multilingual_flag(az):
    respx.get("https://westeurope.tts.speech.microsoft.com/cognitiveservices/voices/list").mock(
        return_value=httpx.Response(200, json=_VOICE_LIST)
    )
    voices = await az.list_voices("neural-multilingual")
    assert {v.id for v in voices} == {"fr-FR-VivienneMultilingualNeural"}
    assert voices[0].multilingual is True


@respx.mock
async def test_synthesize_derives_locale_from_voice(az):
    route = respx.post("https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1").mock(
        return_value=httpx.Response(200, content=b"AUDIO", headers={"content-type": "audio/mpeg"})
    )
    # Passe un code langue à 2 lettres ; le SSML doit quand même utiliser fr-FR.
    await az.synthesize("salut", "neural-standard", "fr-FR-DeniseNeural", language="fr")
    body = route.calls.last.request.content.decode()
    assert "xml:lang='fr-FR'" in body


@respx.mock
async def test_synthesize_posts_ssml_and_returns_audio(provider):
    route = respx.post(
        "https://francecentral.tts.speech.microsoft.com/cognitiveservices/v1"
    ).mock(return_value=httpx.Response(200, content=b"MP3DATA"))

    audio, mime = await provider.synthesize(
        "Bonjour.", "neural-standard", "fr-FR-HenriNeural", language="fr-FR"
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
        await provider.synthesize("hi", "neural-standard", "fr-FR-HenriNeural")


@respx.mock
async def test_list_voices_parses(provider):
    respx.get(
        "https://francecentral.tts.speech.microsoft.com/cognitiveservices/voices/list"
    ).mock(return_value=httpx.Response(200, json=[
        {"ShortName": "fr-FR-HenriNeural", "DisplayName": "Henri", "Locale": "fr-FR", "Gender": "Male"},
        {"ShortName": "en-US-JennyNeural", "DisplayName": "Jenny", "Locale": "en-US", "Gender": "Female"},
    ]))
    voices = await provider.list_voices("neural-standard")
    assert voices[0].id == "fr-FR-HenriNeural"
    assert voices[0].language == "fr"
    assert voices[0].gender == "male"
    assert voices[1].language == "en"


def test_azure_declares_model_dependent_voices():
    # Azure's list_voices() filters by model bucket (standard / hd / multilingual),
    # so fetch_all must NOT reuse one model's list for the others. The provider must
    # declare this, otherwise the HD and multilingual voices silently vanish.
    assert AzureSpeechProvider.voices_depend_on_model is True


@respx.mock
async def test_fetch_all_preserves_azure_per_model_buckets(az):
    # Regression: with voices_depend_on_model=False, fetch_all called list_voices once
    # ("neural-standard") and reused it for all 3 buckets, dropping HD + multilingual.
    voice_catalog.clear_cache()
    respx.get(
        "https://westeurope.tts.speech.microsoft.com/cognitiveservices/voices/list"
    ).mock(return_value=httpx.Response(200, json=_VOICE_LIST))
    fetched = await voice_catalog.fetch_all({"azure": az})
    voice_catalog.clear_cache()

    std = {v.id for v in fetched["azure"]["neural-standard"]}
    hd = {v.id for v in fetched["azure"]["neural-hd"]}
    ml = {v.id for v in fetched["azure"]["neural-multilingual"]}
    assert std == {"fr-FR-DeniseNeural", "de-DE-KatjaNeural"}
    assert hd == {"fr-FR-Remy:DragonHDLatestNeural"}
    assert ml == {"fr-FR-VivienneMultilingualNeural"}
