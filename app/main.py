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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "presets": PRESETS},
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
        items.append((preset.id, provider, preset.model, preset.voice))

    session_id = SYNTH.start_session(text, items)

    return templates.TemplateResponse(
        "_card_grid.html",
        {
            "request": request,
            "session_id": session_id,
            "selected": chosen,
        },
    )
