# TTS Box

A local web app to compare text-to-speech providers **side-by-side** on the same text.
Pick your language, browse **every voice** each configured provider offers (filtered to
that language), select the ones you want, and listen to the results as they stream in.

**Providers:** ElevenLabs · OpenAI · Azure Speech · Cartesia · Murf · OpenRouter
(Gemini, gpt-4o-mini, Voxtral, Kokoro, and more).

![TTS Box — pick a language, browse every voice, compare side-by-side](docs/screenshot.png)

## How it works

- **Dynamic voice discovery** — voices are fetched live from each provider's API
  (cached for 1 h), not hard-coded. Hit **↻ refresh voices** to re-fetch.
- **Language filtering** — choose a target language; provider-localized voices
  (Azure, Cartesia, Murf) are filtered to it, while multilingual voices
  (ElevenLabs, OpenAI, Gemini…) are always shown and tagged `multilingual`.
- **No accounts, no database, ephemeral audio** — a new generation purges the
  previous one; closing the server clears everything.

## Setup

```bash
cp .env.example .env       # then fill in the keys for the providers you want
uv sync
```

A missing key simply hides that provider — no error. You need at least one key.

| Provider | Env var(s) | Get a key |
|----------|-----------|-----------|
| ElevenLabs | `ELEVENLABS_API_KEY` | https://elevenlabs.io |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com |
| Azure Speech | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | https://portal.azure.com |
| Cartesia | `CARTESIA_API_KEY` | https://cartesia.ai |
| Murf | `MURF_API_KEY` | https://murf.ai |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai |

## Run

```bash
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

1. Choose a language. The voice list updates to show what can speak it.
2. Search/filter, then check the voices to compare. **★ Save selection** stores your
   picks in the browser for next time.
3. Type your text and click **Generate** (or `Ctrl+Enter`).
4. Cards stream in as each provider responds. **↓ DL** downloads the audio.

## Add a provider

1. Create `app/providers/<name>.py` with a class extending `TTSProvider`
   (see `app/providers/elevenlabs.py`). Implement `list_models`, `list_voices`,
   and `synthesize`. Mark voices `multilingual=True` if they aren't tied to a locale.
2. Add its env var to `.env.example`.
3. Restart `uvicorn` — the provider is auto-discovered.

## Tests

```bash
uv run pytest          # unit tests (httpx mocked via respx)
uv run ruff check .    # lint
```

## Stack

FastAPI · HTMX · Jinja2 · httpx · pytest · uv. No JS build step.

## Credits

Country flags by [flag-icons](https://github.com/lipis/flag-icons) (MIT).
