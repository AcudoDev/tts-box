from __future__ import annotations

from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import voice_catalog
from app.registry import load_providers
from app.synthesizer import Synthesizer
from app.voice_catalog import Selection, option_id, parse_token

load_dotenv()

ROOT = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    # Browsers auto-request /favicon.ico; return 204 so it isn't a noisy 404.
    return Response(status_code=204)


PROVIDERS = load_providers()
SYNTH = Synthesizer()

DEFAULT_LANG = "en"

# Texte d'exemple par langue (fallback EN). Sert d'amorce au chargement.
SAMPLE_TEXT = {
    "en": "Hello, this is a test sentence to compare several text-to-speech voices. "
          "Listen to the prosody, rhythm and overall quality across providers.",
    "fr": "Bonjour, voici un texte de test pour comparer plusieurs voix de synthèse vocale. "
          "Évaluez la prosodie, le rythme et la qualité entre les fournisseurs.",
    "es": "Hola, esta es una frase de prueba para comparar varias voces de síntesis de voz.",
    "de": "Hallo, dies ist ein Testsatz zum Vergleich mehrerer Sprachausgabe-Stimmen.",
}


def _sample_text(lang: str) -> str:
    return SAMPLE_TEXT.get(lang, SAMPLE_TEXT["en"])


_PROVIDER_DISPLAY = {
    "elevenlabs": {"label": "ElevenLabs",  "color": "#7c3aed"},
    "openai":     {"label": "OpenAI",      "color": "#10a37f"},
    "cartesia":   {"label": "Cartesia",    "color": "#6b7280"},
    "murf":       {"label": "Murf",        "color": "#ea580c"},
    "azure":      {"label": "Azure Speech","color": "#0078d4"},
    "openrouter": {"label": "OpenRouter",  "color": "#6366f1"},
}


_MIME_TO_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
}


def _ext_for(mime: str | None) -> str:
    return _MIME_TO_EXT.get((mime or "").lower(), "mp3")


def _provider_labels() -> dict[str, str]:
    return {name: disp["label"] for name, disp in _PROVIDER_DISPLAY.items()}


async def _voices_context(lang: str, *, refresh: bool = False) -> dict:
    fetched = await voice_catalog.fetch_all(PROVIDERS, refresh=refresh)
    groups = voice_catalog.groups_for_language(fetched, _provider_labels(), lang)
    languages = voice_catalog.available_languages(fetched)
    return {
        "groups": groups,
        "languages": [(code, voice_catalog.LANGUAGE_NAMES.get(code, code)) for code in languages],
        "current_lang": lang,
        "provider_display": _PROVIDER_DISPLAY,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctx = await _voices_context(DEFAULT_LANG)
    ctx["request"] = request
    ctx["sample_text"] = _sample_text(DEFAULT_LANG)
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/voices", response_class=HTMLResponse)
async def voices(request: Request, lang: str = DEFAULT_LANG, refresh: bool = False):
    ctx = await _voices_context(lang, refresh=refresh)
    ctx["request"] = request
    return templates.TemplateResponse(request, "_voices.html", ctx)


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    text: Annotated[str, Form()],
    language: Annotated[str, Form()] = DEFAULT_LANG,
    selected: Annotated[list[str], Form()] = [],
):
    fetched = await voice_catalog.fetch_all(PROVIDERS)
    items: list[tuple[Selection, object]] = []
    seen: set[str] = set()
    for token in selected:
        try:
            provider_name, model, voice = parse_token(token)
        except ValueError:
            continue
        provider = PROVIDERS.get(provider_name)
        if not provider:
            continue
        oid = option_id(provider_name, model, voice)
        if oid in seen:
            continue
        seen.add(oid)
        resolved = voice_catalog.resolve_voice(fetched, provider_name, model, voice)
        label = resolved.name if resolved else voice
        sel = Selection(
            id=oid, label=label, provider=provider_name,
            model=model, voice=voice, language=language or None,
        )
        items.append((sel, provider))

    session_id = SYNTH.start_session(text, items)
    return templates.TemplateResponse(
        request, "_card_grid.html",
        {"session_id": session_id, "selected": [s for s, _ in items]},
    )


@app.get("/result/{session_id}/{option_id}", response_class=HTMLResponse)
async def result(request: Request, session_id: str, option_id: str):
    option = SYNTH.get_selection(session_id, option_id)
    res = SYNTH.get(session_id, option_id)
    if option is None or res is None:
        raise HTTPException(404, "unknown session or option")

    if res.status == "pending":
        return templates.TemplateResponse(
            request, "card_loading.html", {"option": option, "session_id": session_id},
        )
    if res.status == "error":
        return templates.TemplateResponse(
            request, "card_error.html",
            {"option": option, "error_msg": res.error_msg, "latency_ms": res.latency_ms},
        )
    return templates.TemplateResponse(
        request, "card_done.html",
        {
            "option": option, "session_id": session_id, "latency_ms": res.latency_ms,
            "ext": _ext_for(res.mime), "char_count": res.char_count, "cost_usd": res.cost_usd,
        },
    )


@app.get("/audio/{session_id}/{option_id}.{ext}")
async def audio(session_id: str, option_id: str, ext: str):
    res = SYNTH.get(session_id, option_id)
    if res is None or res.status != "done" or res.audio is None:
        raise HTTPException(404, "audio not available")
    return Response(content=res.audio, media_type=res.mime or "audio/mpeg")
