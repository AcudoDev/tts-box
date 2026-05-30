from __future__ import annotations

import base64

import httpx

from app.providers.base import TTSProvider, Voice

URL = "https://api.murf.ai/v1/speech/generate"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = ["GEN2"]

# ISO 639-1 → Murf locale (fr → fr-FR). Used when no locale is encoded in voiceId.
_LANG_TO_LOCALE = {
    "fr": "fr-FR",
    "en": "en-US",
    "es": "es-ES",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-BR",
    "nl": "nl-NL",
    "pl": "pl-PL",
    "zh": "zh-CN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "hi": "hi-IN",
    "ru": "ru-RU",
    "tr": "tr-TR",
    "el": "el-GR",
    "ta": "ta-IN",
    "bn": "bn-IN",
    "hr": "hr-HR",
}


def _derive_locale(voice_id: str, language: str | None) -> str | None:
    """Murf's voiceId is usually prefixed with locale (e.g. "fr-FR-axel").
    If so, derive the locale from it. Otherwise fall back to the language hint.
    """
    parts = voice_id.split("-", 2)
    if len(parts) >= 2 and len(parts[0]) == 2 and len(parts[1]) == 2:
        return f"{parts[0]}-{parts[1]}"
    if language:
        return _LANG_TO_LOCALE.get(language)
    return None


class MurfProvider(TTSProvider):
    name = "murf"
    api_key_env = "MURF_API_KEY"

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        # Murf returns a top-level JSON array of voice objects. Authoritative
        # fields: voiceId, displayName, locale (BCP-47, e.g. "fr-FR"), gender
        # (capitalized enum Male/Female/NonBinary).
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.murf.ai/v1/speech/voices",
                headers={"api-key": self.api_key},
            )
            r.raise_for_status()
            data = r.json()
        out: list[Voice] = []
        for v in data:
            locale = v.get("locale") or ""
            out.append(Voice(
                id=v["voiceId"],
                name=v.get("displayName", v["voiceId"]),
                language=locale[:2] or None,
                gender=(v.get("gender") or "").lower() or None,
            ))
        return out

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        body: dict = {
            "text": text,
            "voiceId": voice_id,
            "modelVersion": model,
            "format": "MP3",
            "encodeAsBase64": True,
        }
        locale = _derive_locale(voice_id, language)
        if locale:
            body["locale"] = locale

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                URL,
                headers={
                    "api-key": self.api_key,
                    "content-type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()

        encoded = data.get("encodedAudio")
        if encoded:
            return (base64.b64decode(encoded), "audio/mpeg")

        # Fallback: server returned only a URL.
        audio_url = data.get("audioFile")
        if not audio_url:
            raise RuntimeError("Murf response missing both encodedAudio and audioFile")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r2 = await client.get(audio_url)
            r2.raise_for_status()
            return (r2.content, "audio/mpeg")
