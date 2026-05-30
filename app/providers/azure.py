from __future__ import annotations

import os
import xml.sax.saxutils as saxutils

import httpx

from app.providers.base import TTSProvider, Voice

TIMEOUT = httpx.Timeout(30.0)

# Azure encodes the actual model in the voice name (XxxNeural, XxxMultilingualNeural,
# Xxx:DragonHDLatestNeural). The `model` field here is a logical grouping used
# for UI organization + pricing — it's never sent to the API.
_MODELS = ["neural-standard", "neural-hd", "neural-multilingual"]


def _endpoint(region: str) -> str:
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"


def _locale_from_voice(voice_id: str) -> str | None:
    """Azure voiceId = '<lang>-<REGION>-<Name...>' → '<lang>-<REGION>'."""
    parts = voice_id.split("-", 2)
    if len(parts) >= 2 and len(parts[0]) == 2 and len(parts[1]) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return None


def _model_of_voice(short_name: str) -> str:
    """Bucket an Azure ShortName into one of our logical models.

    HD/Dragon voices carry a ':Dragon...' suffix (DragonHDLatest/Omni/Flash);
    multilingual voices end in 'MultilingualNeural'; everything else is standard.
    """
    if "DragonHD" in short_name:
        return "neural-hd"
    if short_name.endswith("MultilingualNeural"):
        return "neural-multilingual"
    return "neural-standard"


def _build_ssml(text: str, voice_id: str, language: str | None) -> str:
    # Prefer the full locale derived from the voiceId (e.g. "fr-FR"); fall back to
    # the caller-provided language, then a neutral default.
    lang = _locale_from_voice(voice_id) or language or "en-US"
    # Some HD voices use a colon in their name (e.g. "fr-FR-Vivienne:DragonHDLatestNeural"),
    # which is valid as an attribute value but must be XML-escaped.
    voice_attr = saxutils.quoteattr(voice_id)
    text_escaped = saxutils.escape(text)
    return (
        f"<speak version='1.0' xml:lang='{lang}'>"
        f"<voice xml:lang='{lang}' name={voice_attr}>{text_escaped}</voice>"
        f"</speak>"
    )


class AzureSpeechProvider(TTSProvider):
    """Azure Speech Service (Cognitive Services) Neural TTS."""

    name = "azure"
    api_key_env = "AZURE_SPEECH_KEY"

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)
        # Region is the second piece of config required for Azure.
        self.region = os.getenv("AZURE_SPEECH_REGION", "westeurope")

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                headers={"Ocp-Apim-Subscription-Key": self.api_key},
            )
            r.raise_for_status()
            data = r.json()
        out: list[Voice] = []
        for v in data:
            short = v["ShortName"]
            if _model_of_voice(short) != model:
                continue
            out.append(Voice(
                id=short,
                name=v.get("DisplayName", short),
                language=(v.get("Locale") or "")[:2] or None,
                gender=(v.get("Gender") or "").lower() or None,
                multilingual=(model == "neural-multilingual"),
            ))
        return out

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        ssml = _build_ssml(text, voice_id, language)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                _endpoint(self.region),
                headers={
                    "ocp-apim-subscription-key": self.api_key,
                    "content-type": "application/ssml+xml",
                    "x-microsoft-outputformat": "audio-24khz-96kbitrate-mono-mp3",
                    "user-agent": "tts-box",
                },
                content=ssml.encode("utf-8"),
            )
            r.raise_for_status()
            return (r.content, "audio/mpeg")
