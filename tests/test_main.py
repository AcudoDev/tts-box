from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_favicon_returns_no_content_not_404():
    # The browser auto-requests /favicon.ico; we answer 204 instead of a noisy 404.
    r = client.get("/favicon.ico")
    assert r.status_code == 204
    assert r.content == b""
