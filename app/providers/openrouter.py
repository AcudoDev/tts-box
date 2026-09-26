from __future__ import annotations

import io
import re
import wave

import httpx

from app.providers.base import TTSProvider, Voice

URL = "https://openrouter.ai/api/v1/audio/speech"
TIMEOUT = httpx.Timeout(60.0)

# Models routed through OpenRouter — from GET /api/v1/models?output_modalities=speech,
# vérifié le 2026-09-26. openai/gpt-4o-mini-tts (404) and zyphra/zonos-* (no endpoints)
# were dropped by OpenRouter; gpt-4o-mini-tts now goes through the direct OpenAI provider.
_MODELS = [
    "google/gemini-3.8-flash-tts",
    "google/gemini-3.8-flash-lite-tts",
    "google/gemini-3.1-flash-tts-preview",
    "microsoft/mai-voice-2",
    "microsoft/mai-voice-2-flash",
    "x-ai/grok-voice-tts-1.0",
    "minimax/speech-2.8-hd",
    "minimax/speech-2.8-turbo",
    "deepgram/aura-2",
    "deepgram/flux-tts:free",
    "qwen/qwen-audio-3.0-tts-plus",
    "qwen/qwen-audio-3.0-tts-flash",
    "fish-audio/s2.1-pro",
    "fish-audio/s2.1-pro-free:free",
    "fish-audio/s2-pro",
    "fish-audio/s1",
    "bytedance-seed/seed-audio-1-0",
    "mistralai/voxtral-mini-tts-2603",
    "sesame/csm-1b",
    "hexgrad/kokoro-82m",
    "canopylabs/orpheus-3b-0.1-ft",
]

# Gemini TTS only supports response_format=pcm. The rest accept mp3.
_PCM_ONLY_MODELS = {m for m in _MODELS if m.startswith("google/gemini-")}

# "voice" is optional and has no public named catalogue on these → provider default.
_DEFAULT_VOICE_MODELS = [
    m for m in _MODELS if m.startswith(("fish-audio/", "bytedance-seed/"))
]


# ---------------------------------------------------------------------------
# Per-model voice catalogues — Vérifié le 2026-09-26.
# Each entry maps an OpenRouter model id to its fixed set of named voices, passed
# verbatim in the "voice" field of POST /api/v1/audio/speech. Models without named
# voices (Fish Audio: reference-id; Seed Audio: voice described in the prompt) get a
# single "Default" voice — see _DEFAULT_VOICE_MODELS.
# New lists (2026-09-26) are copied from the models API "supported_voices" field.
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

# Sesame CSM-1B — speaker presets now exposed by OpenRouter. English-only.
_SESAME_VOICES = [
    "conversational_a", "conversational_b",
    "read_speech_a", "read_speech_b", "read_speech_c", "read_speech_d", "none",
]

# Microsoft MAI-Voice-2 (+ Flash) — 4 locale-tagged voices "xx-YY-Name:MAI-Voice-2".
# The model speaks 15 languages; the locale prefix is the voice's native language.
_MAI_VOICES = [
    "en-US-Harper:MAI-Voice-2", "es-MX-Valeria:MAI-Voice-2",
    "fr-FR-Soleil:MAI-Voice-2", "de-DE-Klaus:MAI-Voice-2",
]

# xAI Grok Voice TTS — 5 voices, 20+ languages with automatic language detection.
_GROK_VOICES = ["eve", "ara", "rex", "sal", "leo"]

# Qwen-Audio-3.0-TTS (DashScope) — 2 voices per tier; multilingual, native language
# not documented → generalist (shown under every language).
_QWEN_VOICES = {
    "qwen/qwen-audio-3.0-tts-plus": ["longanlingxin", "longanlufeng"],
    "qwen/qwen-audio-3.0-tts-flash": ["loongjohn", "longanhuan_v3.6"],
}

# Deepgram — voice id ends with its language code ("aura-2-agathe-fr" → "fr").
# Flux is English-only; Aura-2 voices are each single-language.
_DEEPGRAM_FLUX_VOICES = [
    "flux-alexis-en", "flux-bree-en", "flux-brittany-en", "flux-brooke-en",
    "flux-bruce-en", "flux-cliff-en", "flux-cole-en", "flux-colin-en",
    "flux-conor-en", "flux-donovan-en", "flux-drew-en", "flux-elise-en",
    "flux-gemma-en", "flux-haley-en", "flux-hannah-en", "flux-heather-en",
    "flux-jack-en", "flux-kai-en", "flux-kelsey-en", "flux-kit-en", "flux-maeve-en",
    "flux-marcelo-en", "flux-marcus-en", "flux-meena-en", "flux-meghan-en",
    "flux-miles-en", "flux-naveen-en", "flux-paige-en", "flux-priya-en",
    "flux-rufus-en", "flux-sean-en", "flux-sharon-en", "flux-sienna-en",
    "flux-tanner-en", "flux-wade-en", "flux-wes-en",
]

_DEEPGRAM_AURA2_VOICES = [
    "aura-2-thalia-en", "aura-2-agathe-fr", "aura-2-agustina-es",
    "aura-2-alvaro-es", "aura-2-ama-ja", "aura-2-amalthea-en",
    "aura-2-andromeda-en", "aura-2-antonia-es", "aura-2-apollo-en",
    "aura-2-aquila-es", "aura-2-arcas-en", "aura-2-aries-en", "aura-2-asteria-en",
    "aura-2-athena-en", "aura-2-atlas-en", "aura-2-aurelia-de", "aura-2-aurora-en",
    "aura-2-beatrix-nl", "aura-2-callista-en", "aura-2-carina-es",
    "aura-2-celeste-es", "aura-2-cesare-it", "aura-2-cinzia-it", "aura-2-cora-en",
    "aura-2-cordelia-en", "aura-2-cornelia-nl", "aura-2-daphne-nl",
    "aura-2-delia-en", "aura-2-demetra-it", "aura-2-diana-es", "aura-2-dionisio-it",
    "aura-2-draco-en", "aura-2-ebisu-ja", "aura-2-elara-de", "aura-2-electra-en",
    "aura-2-elio-it", "aura-2-estrella-es", "aura-2-fabian-de", "aura-2-flavio-it",
    "aura-2-fujin-ja", "aura-2-gloria-es", "aura-2-harmonia-en", "aura-2-hector-fr",
    "aura-2-helena-en", "aura-2-hera-en", "aura-2-hermes-en", "aura-2-hestia-nl",
    "aura-2-hyperion-en", "aura-2-iris-en", "aura-2-izanami-ja", "aura-2-janus-en",
    "aura-2-javier-es", "aura-2-julius-de", "aura-2-juno-en", "aura-2-jupiter-en",
    "aura-2-kara-de", "aura-2-lara-de", "aura-2-lars-nl", "aura-2-leda-nl",
    "aura-2-livia-it", "aura-2-luciano-es", "aura-2-luna-en", "aura-2-maia-it",
    "aura-2-mars-en", "aura-2-melia-it", "aura-2-minerva-en", "aura-2-neptune-en",
    "aura-2-nestor-es", "aura-2-odysseus-en", "aura-2-olivia-es",
    "aura-2-ophelia-en", "aura-2-orion-en", "aura-2-orpheus-en",
    "aura-2-pandora-en", "aura-2-phoebe-en", "aura-2-pluto-en", "aura-2-rhea-nl",
    "aura-2-roman-nl", "aura-2-sander-nl", "aura-2-saturn-en", "aura-2-selena-es",
    "aura-2-selene-en", "aura-2-silvia-es", "aura-2-sirio-es", "aura-2-theia-en",
    "aura-2-uzume-ja", "aura-2-valerio-es", "aura-2-vesta-en", "aura-2-viktoria-de",
    "aura-2-zeus-en",
]

# MiniMax Speech 2.8 (HD + Turbo) — English presets of a multilingual model.
_MINIMAX_VOICES = [
    "English_expressive_narrator", "English_radiant_girl",
    "English_magnetic_voiced_man", "English_compelling_lady1",
    "English_Aussie_Bloke", "English_captivating_female1", "English_Upbeat_Woman",
    "English_Trustworth_Man", "English_CalmWoman", "English_UpsetGirl",
    "English_Gentle-voiced_man", "English_Whispering_girl", "English_Diligent_Man",
    "English_Graceful_Lady", "English_ReservedYoungMan", "English_PlayfulGirl",
    "English_ManWithDeepVoice", "English_MaturePartner", "English_FriendlyPerson",
    "English_MatureBoss", "English_Debator", "English_LovelyGirl",
    "English_Steadymentor", "English_Deep-VoicedGentleman", "English_Wiselady",
    "English_CaptivatingStoryteller", "English_DecentYoungMan",
    "English_SentimentalLady", "English_ImposingManner", "English_SadTeen",
    "English_PassionateWarrior", "English_WiseScholar", "English_Soft-spokenGirl",
    "English_SereneWoman", "English_ConfidentWoman", "English_PatientMan",
    "English_Comedian", "English_BossyLeader", "English_Strong-WilledBoy",
    "English_StressedLady", "English_AssertiveQueen", "English_AnimeCharacter",
    "English_Jovialman", "English_WhimsicalGirl", "English_Kind-heartedGirl",
]

# Kokoro-82m — 54 fixed preset voices. Voice id = [lang][gender]_[name]; the first
# letter encodes the language. Each voice is single-language.
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


def _deepgram_voice(vid: str) -> Voice:
    name = vid.split("-")[-2].capitalize()  # "aura-2-agathe-fr" → "Agathe"
    return Voice(id=vid, name=name, language=vid.rsplit("-", 1)[1])


def _build_voices_by_model() -> dict[str, list[Voice]]:
    out: dict[str, list[Voice]] = {}
    for m in _PCM_ONLY_MODELS:  # every Gemini TTS model shares the same 30 voices
        out[m] = [Voice(id=v, name=v) for v in _GEMINI_VOICES]
    for m in ("microsoft/mai-voice-2", "microsoft/mai-voice-2-flash"):
        out[m] = [
            Voice(id=v, name=v.split(":")[0].rsplit("-", 1)[1], language=v[:2])
            for v in _MAI_VOICES
        ]
    out["x-ai/grok-voice-tts-1.0"] = [
        Voice(id=v, name=v.capitalize()) for v in _GROK_VOICES
    ]
    for m in ("minimax/speech-2.8-hd", "minimax/speech-2.8-turbo"):
        out[m] = [
            Voice(
                id=v, name=v.removeprefix("English_").replace("_", " "),
                language="en",
            )
            for v in _MINIMAX_VOICES
        ]
    out["deepgram/aura-2"] = [_deepgram_voice(v) for v in _DEEPGRAM_AURA2_VOICES]
    out["deepgram/flux-tts:free"] = [_deepgram_voice(v) for v in _DEEPGRAM_FLUX_VOICES]
    for m, ids in _QWEN_VOICES.items():
        out[m] = [Voice(id=v, name=v) for v in ids]
    out["sesame/csm-1b"] = [Voice(id=v, name=v, language="en") for v in _SESAME_VOICES]
    out["mistralai/voxtral-mini-tts-2603"] = [
        Voice(id=vid, name=name, language=lang)
        for vid, name, lang in _VOXTRAL_VOICES
    ]
    out["hexgrad/kokoro-82m"] = [_kokoro_voice(v) for v in _KOKORO_VOICES]
    out["canopylabs/orpheus-3b-0.1-ft"] = [
        Voice(id=v, name=v.capitalize(), language="en") for v in _ORPHEUS_VOICES
    ]
    # No named voices: "voice" is optional there, so expose a single "Default" entry
    # (empty id → omitted from the request) instead of hiding the model.
    for m in _DEFAULT_VOICE_MODELS:
        out[m] = [Voice(id="", name="Default")]
    return out


_VOICES_BY_MODEL = _build_voices_by_model()

_PCM_RE = re.compile(r"rate=(\d+).*?channels=(\d+)", re.IGNORECASE)


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int, channels: int) -> bytes:
    """Wrap raw PCM (signed 16-bit LE by convention) in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


class OpenRouterProvider(TTSProvider):
    """OpenRouter TTS — routes to multiple underlying providers via one endpoint."""

    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"
    voices_depend_on_model = True

    def list_models(self) -> list[str]:
        return list(_MODELS)

    async def list_voices(self, model: str) -> list[Voice]:
        # Fixed per-model catalogue.
        return list(_VOICES_BY_MODEL.get(model, []))

    async def synthesize(
        self, text: str, model: str, voice_id: str, language: str | None = None
    ) -> tuple[bytes, str]:
        response_format = "pcm" if model in _PCM_ONLY_MODELS else "mp3"
        body = {
            "model": model,
            "input": text,
            "response_format": response_format,
        }
        if voice_id:  # empty = model's default voice (Fish Audio, Seed Audio)
            body["voice"] = voice_id
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
