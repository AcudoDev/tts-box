# TTS Box

App locale (single-user) pour comparer rapidement le rendu de plusieurs providers TTS sur un même texte.

Providers supportés : **ElevenLabs**, **OpenAI**, **Cartesia**. Stub Mistral (en attente d'une API TTS publique).

## Setup

```bash
cp .env.example .env
# édite .env et remplis les clés des providers à activer
uv sync
```

## Lancer

```bash
uv run uvicorn app.main:app --reload
```

Ouvrir <http://127.0.0.1:8000>.

## Utilisation

1. Édite `presets.yaml` pour définir les combos `(provider, modèle, voix)` à comparer.
2. Sur la page : tape un texte, coche les voix voulues, clique "Générer".
3. Les cartes apparaissent l'une après l'autre selon la latence des providers.
4. Raccourci : `Ctrl+Enter` dans le textarea pour soumettre.
5. Bouton `↓ DL` sur chaque carte pour télécharger l'audio.

Les audios sont **éphémères** : un nouveau submit purge tout, et fermer le serveur efface tout.

## Ajouter un provider

1. Créer `app/providers/<nom>.py` avec une classe qui hérite de `TTSProvider`
   (voir `app/providers/elevenlabs.py` comme modèle).
2. Ajouter sa variable d'env dans `.env.example`.
3. Restart `uvicorn`. Le provider apparaît automatiquement.

## Tests

```bash
uv run pytest
```

## Stack

FastAPI · HTMX · Jinja2 · httpx · pytest · uv
