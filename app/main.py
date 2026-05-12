from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from app.registry import load_providers
from app.presets import load_presets
from app.synthesizer import Synthesizer

load_dotenv()

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")

PROVIDERS = load_providers()
PRESETS = load_presets(
    PROJECT_ROOT / "presets.yaml",
    available_providers=set(PROVIDERS.keys()),
)
SYNTH = Synthesizer()


_PROVIDER_DISPLAY = {
    "elevenlabs": {"label": "ElevenLabs",  "color": "#7c3aed"},
    "openai":     {"label": "OpenAI",      "color": "#10a37f"},
    "cartesia":   {"label": "Cartesia",    "color": "#6b7280"},
    "murf":       {"label": "Murf",        "color": "#ea580c"},
    "azure":      {"label": "Azure Speech","color": "#0078d4"},
    "openrouter": {"label": "OpenRouter",  "color": "#6366f1"},
}


def _group_presets_by_provider_and_model(presets):
    """Two-level grouping: provider → model → list of presets.

    Returns list[ (provider_name, list[ (model_name, list[Preset]) ]) ] preserving
    the order in which providers/models first appear in `presets`.
    """
    # provider -> model -> [presets]
    by_provider: dict[str, dict[str, list]] = {}
    provider_order: list[str] = []
    model_order: dict[str, list[str]] = {}
    for p in presets:
        if p.provider not in by_provider:
            by_provider[p.provider] = {}
            provider_order.append(p.provider)
            model_order[p.provider] = []
        if p.model not in by_provider[p.provider]:
            by_provider[p.provider][p.model] = []
            model_order[p.provider].append(p.model)
        by_provider[p.provider][p.model].append(p)

    # Prefer the canonical provider order, then fall back to insertion order.
    ordered_providers = []
    seen = set()
    for provider in _PROVIDER_DISPLAY:
        if provider in by_provider:
            ordered_providers.append(provider)
            seen.add(provider)
    for provider in provider_order:
        if provider not in seen:
            ordered_providers.append(provider)

    out = []
    for provider in ordered_providers:
        models = [(m, by_provider[provider][m]) for m in model_order[provider]]
        out.append((provider, models))
    return out


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "groups": _group_presets_by_provider_and_model(PRESETS),
            "provider_display": _PROVIDER_DISPLAY,
        },
    )


from fastapi import Form
from typing import Annotated


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    text: Annotated[str, Form()],
    selected: Annotated[list[str], Form()] = [],
):
    by_id = {p.id: p for p in PRESETS}
    chosen = [
        by_id[pid] for pid in selected
        if pid in by_id and not by_id[pid].disabled_reason
    ]

    items = []
    for preset in chosen:
        provider = PROVIDERS.get(preset.provider)
        if not provider:
            continue
        items.append((preset.id, provider, preset.model, preset.voice, preset.language))

    session_id = SYNTH.start_session(text, items)

    return templates.TemplateResponse(
        request,
        "_card_grid.html",
        {
            "session_id": session_id,
            "selected": chosen,
        },
    )


from fastapi import HTTPException
from fastapi.responses import Response


_MIME_TO_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
}


def _ext_for(mime: str | None) -> str:
    return _MIME_TO_EXT.get((mime or "").lower(), "mp3")


@app.get("/result/{session_id}/{preset_id}", response_class=HTMLResponse)
async def result(request: Request, session_id: str, preset_id: str):
    by_id = {p.id: p for p in PRESETS}
    preset = by_id.get(preset_id)
    if not preset:
        raise HTTPException(404, "unknown preset")

    res = SYNTH.get(session_id, preset_id)
    if res is None:
        raise HTTPException(404, "unknown session")

    if res.status == "pending":
        return templates.TemplateResponse(
            request,
            "card_loading.html",
            {"preset": preset, "session_id": session_id},
        )
    if res.status == "error":
        return templates.TemplateResponse(
            request,
            "card_error.html",
            {
                "preset": preset,
                "error_msg": res.error_msg,
                "latency_ms": res.latency_ms,
            },
        )
    return templates.TemplateResponse(
        request,
        "card_done.html",
        {
            "preset": preset,
            "session_id": session_id,
            "latency_ms": res.latency_ms,
            "ext": _ext_for(res.mime),
            "char_count": res.char_count,
            "cost_usd": res.cost_usd,
        },
    )


@app.get("/audio/{session_id}/{preset_id}.{ext}")
async def audio(session_id: str, preset_id: str, ext: str):
    res = SYNTH.get(session_id, preset_id)
    if res is None or res.status != "done" or res.audio is None:
        raise HTTPException(404, "audio not available")
    return Response(content=res.audio, media_type=res.mime or "audio/mpeg")
