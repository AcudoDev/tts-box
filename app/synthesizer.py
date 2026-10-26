from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import httpx

from app.pricing import estimate_cost_usd
from app.providers.base import TTSProvider
from app.voice_catalog import Selection


def _format_error(e: Exception) -> str:
    """Produce a human-readable one-line error message.

    For HTTP errors, try to extract a meaningful field from the JSON body
    (ElevenLabs uses detail.message, OpenAI/Mistral use error.message, etc.).
    """
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        try:
            payload = e.response.json()
        except ValueError:  # JSONDecodeError is a ValueError subclass
            return f"HTTP {code}: {e.response.text[:120]}".strip()
        if not isinstance(payload, dict):  # a list/str body must not crash the task
            return f"HTTP {code}: {str(payload)[:200]}"
        detail, error = payload.get("detail"), payload.get("error")
        msg = (
            (detail.get("message") if isinstance(detail, dict) else None)
            or (detail if isinstance(detail, str) else None)
            or (error.get("message") if isinstance(error, dict) else None)
            or payload.get("message")
            or str(payload)[:200]
        )
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
    id: str
    text: str
    items: dict[str, tuple[Selection, TTSProvider]] = field(default_factory=dict)
    results: dict[str, Result] = field(default_factory=dict)
    tasks: list[asyncio.Task] = field(default_factory=list)


class Synthesizer:
    """In-memory orchestrator. Single active session (mono-user, local)."""

    def __init__(self) -> None:
        self._session: _Session | None = None

    def _current(self, session_id: str) -> _Session | None:
        session = self._session
        return session if session and session.id == session_id else None

    def start_session(
        self,
        text: str,
        items: list[tuple[Selection, TTSProvider]],
    ) -> str:
        # Replaces the previous session — mono-user, only one session at a time.
        session = self._session = _Session(id=uuid.uuid4().hex[:8], text=text)
        for sel, provider in items:
            session.items[sel.id] = (sel, provider)
            self._spawn(session, sel.id)
        return session.id

    def retry(self, session_id: str, option_id: str) -> Selection | None:
        """Re-run synthesis for one option of the current session."""
        sel = self.get_selection(session_id, option_id)
        if sel:
            self._spawn(self._session, option_id)
        return sel

    def _spawn(self, session: _Session, option_id: str) -> None:
        session.results[option_id] = Result(status="pending")
        # Keep a strong ref: asyncio only holds weak refs to running tasks.
        session.tasks.append(asyncio.create_task(self._run(session, option_id)))

    def get_selection(self, session_id: str, option_id: str) -> Selection | None:
        session = self._current(session_id)
        item = session.items.get(option_id) if session else None
        return item[0] if item else None

    async def _run(self, session: _Session, option_id: str) -> None:
        (sel, provider), text = session.items[option_id], session.text
        start = time.monotonic()
        try:
            audio, mime = await provider.synthesize(text, sel.model, sel.voice, sel.language)
            char_count = len(text)
            session.results[option_id] = Result(
                status="done",
                audio=audio,
                mime=mime,
                latency_ms=int((time.monotonic() - start) * 1000),
                char_count=char_count,
                cost_usd=estimate_cost_usd(provider.name, sel.model, char_count),
            )
        except Exception as e:
            session.results[option_id] = Result(
                status="error",
                latency_ms=int((time.monotonic() - start) * 1000),
                error_msg=_format_error(e),
            )

    def get(self, session_id: str, option_id: str) -> Result | None:
        session = self._current(session_id)
        return session.results.get(option_id) if session else None
