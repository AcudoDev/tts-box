from __future__ import annotations
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal
import httpx
from app.providers.base import TTSProvider
from app.pricing import estimate_cost_usd


def _format_error(e: Exception) -> str:
    """Produce a human-readable one-line error message.

    For HTTP errors, try to extract a meaningful field from the JSON body
    (ElevenLabs uses detail.message, OpenAI/Mistral use error.message, etc.).
    """
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        try:
            payload = e.response.json()
        except (json.JSONDecodeError, ValueError):
            return f"HTTP {code}: {e.response.text[:120]}".strip()
        msg = (
            (payload.get("detail") or {}).get("message")
            if isinstance(payload.get("detail"), dict)
            else None
        )
        if not msg:
            msg = payload.get("detail") if isinstance(payload.get("detail"), str) else None
        if not msg and isinstance(payload.get("error"), dict):
            msg = payload["error"].get("message")
        if not msg:
            msg = payload.get("message")
        if not msg:
            msg = str(payload)[:200]
        return f"HTTP {code}: {msg}"
    return f"{type(e).__name__}: {e}"

Status = Literal["pending", "done", "error"]


@dataclass
class Result:
    status: Status = "pending"
    audio: bytes | None = None
    mime: str | None = None
    latency_ms: int | None = None
    error_msg: str | None = None
    char_count: int | None = None
    cost_usd: float | None = None


@dataclass
class _Session:
    results: dict[str, Result] = field(default_factory=dict)
    tasks: list[asyncio.Task] = field(default_factory=list)


class Synthesizer:
    """In-memory orchestrator. Single active session (mono-user, local)."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def start_session(
        self,
        text: str,
        items: list[tuple[str, TTSProvider, str, str, str | None]],
    ) -> str:
        # Purge everything else — mono-user, only one session at a time.
        self._sessions.clear()
        session_id = uuid.uuid4().hex[:8]
        session = _Session()
        self._sessions[session_id] = session
        for preset_id, provider, model, voice, language in items:
            session.results[preset_id] = Result(status="pending")
            task = asyncio.create_task(
                self._run(session, preset_id, provider, text, model, voice, language)
            )
            session.tasks.append(task)
        return session_id

    async def _run(
        self,
        session: _Session,
        preset_id: str,
        provider: TTSProvider,
        text: str,
        model: str,
        voice: str,
        language: str | None,
    ) -> None:
        start = time.monotonic()
        try:
            audio, mime = await provider.synthesize(text, model, voice, language)
            char_count = len(text)
            session.results[preset_id] = Result(
                status="done",
                audio=audio,
                mime=mime,
                latency_ms=int((time.monotonic() - start) * 1000),
                char_count=char_count,
                cost_usd=estimate_cost_usd(provider.name, model, char_count),
            )
        except Exception as e:
            session.results[preset_id] = Result(
                status="error",
                latency_ms=int((time.monotonic() - start) * 1000),
                error_msg=_format_error(e),
            )

    async def wait_all(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        if session.tasks:
            await asyncio.gather(*session.tasks, return_exceptions=True)

    def get(self, session_id: str, preset_id: str) -> Result | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session.results.get(preset_id)
