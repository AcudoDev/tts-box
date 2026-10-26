from __future__ import annotations

import base64

import httpx

from app.providers.base import TTSProvider, Voice, locale_from_voice_id

URL = "https://api.murf.ai/v1/speech/generate"
TIMEOUT = httpx.Timeout(30.0)

_MODELS = ["GEN2"]

# ISO 639-1 → Murf locale (fr → fr-FR). Used when no locale is encoded in voiceId
# (Murf voiceIds are usually locale-prefixed, e.g. "fr-FR-axel").
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
        locale = locale_from_voice_id(voice_id) or _LANG_TO_LOCALE.get(language or "")
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
        if not encoded:  # we always ask for encodeAsBase64
            raise RuntimeError("Murf response missing encodedAudio")
        return (base64.b64decode(encoded), "audio/mpeg")
