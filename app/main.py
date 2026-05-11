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
