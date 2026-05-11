# TTS Box

App locale pour comparer le rendu de plusieurs providers TTS sur un même texte.

## Setup

1. Copier `.env.example` vers `.env` et remplir les clés des providers voulus.
2. `uv sync`
3. Éditer `presets.yaml` (voir l'exemple fourni).
4. `uv run uvicorn app.main:app --reload`
5. Ouvrir <http://127.0.0.1:8000>.

## Ajouter un provider

Créer `app/providers/<nom>.py` avec une classe héritant de `TTSProvider` (voir `elevenlabs.py`). Ajouter sa variable d'env dans `.env.example`.
