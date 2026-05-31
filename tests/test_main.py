from unittest.mock import patch

from fastapi.testclient import TestClient

from app import voice_catalog
from app.main import app
from app.providers.base import Voice

client = TestClient(app)


def test_download_name_readable_and_cross_os_safe():
    from app.main import _download_name
    assert _download_name("Rachel", "elevenlabs", "mp3") == "Rachel-elevenlabs.mp3"
    # commas/parentheses stripped, hyphens/spaces kept
    assert _download_name("Roger - Laid-Back, Casual", "elevenlabs", "mp3") == \
        "Roger - Laid-Back Casual-elevenlabs.mp3"
    # Unicode letters survive; OS-illegal chars (slash, colon) are removed
    assert _download_name("Évariste", "azure", "wav") == "Évariste-azure.wav"
    name = _download_name("google/gemini: v3", "openrouter", "wav")
    assert "/" not in name and ":" not in name


def test_favicon_returns_no_content_not_404():
    # The browser auto-requests /favicon.ico; we answer 204 instead of a noisy 404.
    r = client.get("/favicon.ico")
    assert r.status_code == 204
    assert r.content == b""


def _fake_fetch_all():
    async def _f(providers, *, refresh=False):
        return {
            "azure": {"neural-standard": [
                Voice(id="fr-FR-DeniseNeural", name="Denise", language="fr"),
                Voice(id="de-DE-KatjaNeural", name="Katja", language="de"),
            ]},
        }
    return _f


def test_voices_route_filters_by_language_query_param():
    # The language <select> is named "language" (for the POST /generate form), so the
    # GET /voices request it triggers carries ?language=xx. The route must read that
    # same param, else switching language in the UI silently does nothing.
    with patch.object(voice_catalog, "fetch_all", _fake_fetch_all()):
        r = client.get("/voices?language=fr")
        assert r.status_code == 200
        assert "Denise" in r.text          # fr voice shown
        assert "Katja" not in r.text       # de voice hidden

        r2 = client.get("/voices?language=de")
        assert "Katja" in r2.text
        assert "Denise" not in r2.text
