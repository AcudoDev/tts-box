from __future__ import annotations

import re
import struct

import httpx

from app.providers.base import TTSProvider, Voice

URL = "https://openrouter.ai/api/v1/audio/speech"
TIMEOUT = httpx.Timeout(60.0)

# Models routed through OpenRouter. We keep only the ones not already
# covered by our direct provider integrations (openai/mistral are duplicates).
_MODELS = [
    "google/gemini-3.1-flash-tts-preview",
    "openai/gpt-4o-mini-tts-2025-12-15",
    "mistralai/voxtral-mini-tts-2603",
    "sesame/csm-1b",
    "hexgrad/kokoro-82m",
    "canopylabs/orpheus-3b-0.1-ft",
    "zyphra/zonos-v0.1-transformer",
    "zyphra/zonos-v0.1-hybrid",
]

# Gemini TTS only supports response_format=pcm. The rest accept mp3.
_PCM_ONLY_MODELS = {"google/gemini-3.1-flash-tts-preview"}


# ---------------------------------------------------------------------------
# Per-model voice catalogues — Vérifié le 2026-05-30.
# Each entry maps an OpenRouter model id to its fixed set of named voices, passed
# verbatim in the "voice" field of POST /api/v1/audio/speech. Models that expose
# no named voices (cloning / speaker-id only, e.g. sesame/csm-1b) are deliberately
# ABSENT so the UI falls back to a free-voice input.
# ---------------------------------------------------------------------------

# Google Gemini TTS — 30 fixed prebuilt voices (named after stars/moons). All are
# multilingual (the spoken language follows the input text, not the voice id).
_GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

# OpenAI gpt-4o-mini-tts — 13 preset voices (the classic 11 + marin, cedar).
# All multilingual (optimized for English but can speak ~99 languages).
_GPT4O_MINI_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar",
]

# Mistral Voxtral — 30 built-in preset voices: 4 speakers × emotion variants.
# (id, display name, language). Jane/Oliver = British EN, Paul = American EN,
# Marie = FR. Multilingual model (any voice can speak any supported language).
_VOXTRAL_VOICES = [
    ("gb_jane_neutral", "Jane (British English) - Neutral", "en"),
    ("gb_jane_confident", "Jane (British English) - Confident", "en"),
    ("gb_jane_curious", "Jane (British English) - Curious", "en"),
    ("gb_jane_frustrated", "Jane (British English) - Frustrated", "en"),
    ("gb_jane_jealousy", "Jane (British English) - Jealousy", "en"),
    ("gb_jane_sad", "Jane (British English) - Sad", "en"),
    ("gb_jane_shameful", "Jane (British English) - Shameful", "en"),
    ("gb_jane_confused", "Jane (British English) - Confused", "en"),
    ("gb_jane_sarcasm", "Jane (British English) - Sarcasm", "en"),
    ("en_paul_neutral", "Paul (American English) - Neutral", "en"),
    ("en_paul_confident", "Paul (American English) - Confident", "en"),
    ("en_paul_cheerful", "Paul (American English) - Cheerful", "en"),
    ("en_paul_happy", "Paul (American English) - Happy", "en"),
    ("en_paul_excited", "Paul (American English) - Excited", "en"),
    ("en_paul_frustrated", "Paul (American English) - Frustrated", "en"),
    ("en_paul_angry", "Paul (American English) - Angry", "en"),
    ("en_paul_sad", "Paul (American English) - Sad", "en"),
    ("gb_oliver_neutral", "Oliver (British English) - Neutral", "en"),
    ("gb_oliver_confident", "Oliver (British English) - Confident", "en"),
    ("gb_oliver_cheerful", "Oliver (British English) - Cheerful", "en"),
    ("gb_oliver_curious", "Oliver (British English) - Curious", "en"),
    ("gb_oliver_excited", "Oliver (British English) - Excited", "en"),
    ("gb_oliver_angry", "Oliver (British English) - Angry", "en"),
    ("gb_oliver_sad", "Oliver (British English) - Sad", "en"),
    ("fr_marie_neutral", "Marie (French) - Neutral", "fr"),
    ("fr_marie_happy", "Marie (French) - Happy", "fr"),
    ("fr_marie_excited", "Marie (French) - Excited", "fr"),
    ("fr_marie_curious", "Marie (French) - Curious", "fr"),
    ("fr_marie_angry", "Marie (French) - Angry", "fr"),
    ("fr_marie_sad", "Marie (French) - Sad", "fr"),
]

# Canopy Labs Orpheus (fine-tuned prod) — 7 English preset voices exposed by
# OpenRouter (upstream "zoe" is not surfaced). English-only, not multilingual.
_ORPHEUS_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac"]

# Zyphra Zonos (transformer + hybrid) — 5 fixed named voices each via OpenRouter.
# The 4 accent personas are English; "random" picks an arbitrary speaker.
_ZONOS_VOICES = [
    ("american_female", "American Female", "en"),
    ("american_male", "American Male", "en"),
    ("british_female", "British Female", "en"),
    ("british_male", "British Male", "en"),
    ("random", "Random", None),
]

# Kokoro-82m — 54 fixed preset voices. Voice id = [lang][gender]_[name]; the first
# letter encodes the language. Each voice is single-language (multilingual=False).
_KOKORO_PREFIX_LANG = {
    "a": "en", "b": "en", "e": "es", "f": "fr",
    "h": "hi", "i": "it", "j": "ja", "p": "pt", "z": "zh",
}
_KOKORO_VOICES = [
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
    "ef_dora", "em_alex", "em_santa",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "pf_dora", "pm_alex", "pm_santa",
]


def _kokoro_voice(vid: str) -> Voice:
    lang = _KOKORO_PREFIX_LANG.get(vid[0]) if vid else None
    return Voice(id=vid, name=vid, language=lang)


def _build_voices_by_model() -> dict[str, list[Voice]]:
    out: dict[str, list[Voice]] = {}
    out["google/gemini-3.1-flash-tts-preview"] = [
        Voice(id=v, name=v, multilingual=True) for v in _GEMINI_VOICES
    ]
    out["openai/gpt-4o-mini-tts-2025-12-15"] = [
        Voice(id=v, name=v, multilingual=True) for v in _GPT4O_MINI_VOICES
    ]
    out["mistralai/voxtral-mini-tts-2603"] = [
        Voice(id=vid, name=name, language=lang, multilingual=True)
        for vid, name, lang in _VOXTRAL_VOICES
    ]
    out["hexgrad/kokoro-82m"] = [_kokoro_voice(v) for v in _KOKORO_VOICES]
    out["canopylabs/orpheus-3b-0.1-ft"] = [
        Voice(id=v, name=v.capitalize(), language="en") for v in _ORPHEUS_VOICES
    ]
    zonos = [Voice(id=vid, name=name, language=lang) for vid, name, lang in _ZONOS_VOICES]
    out["zyphra/zonos-v0.1-transformer"] = list(zonos)
    out["zyphra/zonos-v0.1-hybrid"] = list(zonos)
    # sesame/csm-1b: no named voices (cloning / speaker-id only) → absent on purpose.
    return out


_VOICES_BY_MODEL = _build_voices_by_model()

_PCM_RE = re.compile(r"rate=(\d+).*?channels=(\d+)", re.IGNORECASE)


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int, channels: int, bits: int = 16) -> bytes:
    """Wrap raw PCM (signed 16-bit LE by convention) in a 44-byte WAV header."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
    )
    return header + pcm


class OpenRouterProvider(TTSProvider):
    """OpenRouter TTS — routes to multiple underlying providers via one endpoint."""

    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"
    voices_depend_on_model = True

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        # Fixed per-model catalogue; models without named voices return [] so the
        # UI exposes a free-voice input (cloning / speaker-id models).
        return list(_VOICES_BY_MODEL.get(model, []))

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        response_format = "pcm" if model in _PCM_ONLY_MODELS else "mp3"
        body = {
            "model": model,
            "input": text,
            "voice": voice_id,
            "response_format": response_format,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                URL,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            content_type = r.headers.get("content-type", "audio/mpeg")
            audio = r.content

        # If the server returned raw PCM, wrap it in a WAV container so browsers
        # can play the <audio src=...> directly without extra client-side decoding.
        if content_type.lower().startswith("audio/pcm"):
            m = _PCM_RE.search(content_type)
            sample_rate = int(m.group(1)) if m else 24000
            channels = int(m.group(2)) if m else 1
            audio = _wrap_pcm_as_wav(audio, sample_rate, channels)
            return (audio, "audio/wav")

        mime = content_type.split(";")[0].strip()
        return (audio, mime or "audio/mpeg")
