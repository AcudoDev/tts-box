import asyncio
import pytest
from app.synthesizer import Synthesizer, Result
from app.providers.base import TTSProvider


class FakeProvider(TTSProvider):
    name = "fake_synth"
    api_key_env = "FAKE_SYNTH_KEY"

    def __init__(self, audio: bytes = b"AUDIO", mime: str = "audio/mpeg", fail: bool = False, delay: float = 0):
        super().__init__(api_key="k")
        self._audio = audio
        self._mime = mime
        self._fail = fail
        self._delay = delay

    def list_models(self): return ["m"]
    async def list_voices(self, model): return []

    async def synthesize(self, text, model, voice_id):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("boom")
        return (self._audio, self._mime)


async def test_run_session_populates_cache():
    synth = Synthesizer()
    provider = FakeProvider()
    tasks = [
        ("p1", provider, "m", "v"),
        ("p2", provider, "m", "v"),
    ]
    session_id = synth.start_session("hello", tasks)
    await synth.wait_all(session_id)

    r1 = synth.get(session_id, "p1")
    assert r1.status == "done"
    assert r1.audio == b"AUDIO"
    assert r1.mime == "audio/mpeg"
    assert r1.latency_ms is not None and r1.latency_ms >= 0
    assert r1.char_count == len("hello")
    # Unknown provider → cost_usd is None.
    assert r1.cost_usd is None


async def test_run_session_error_does_not_crash():
    synth = Synthesizer()
    good = FakeProvider()
    bad = FakeProvider(fail=True)
    tasks = [("p1", good, "m", "v"), ("p2", bad, "m", "v")]
    session_id = synth.start_session("hi", tasks)
    await synth.wait_all(session_id)
    assert synth.get(session_id, "p1").status == "done"
    assert synth.get(session_id, "p2").status == "error"
    assert "boom" in synth.get(session_id, "p2").error_msg


async def test_new_session_purges_old_cache():
    synth = Synthesizer()
    provider = FakeProvider()
    s1 = synth.start_session("hi", [("p1", provider, "m", "v")])
    await synth.wait_all(s1)
    assert synth.get(s1, "p1") is not None

    s2 = synth.start_session("bye", [("p1", provider, "m", "v")])
    assert synth.get(s1, "p1") is None  # purged


def test_get_unknown_returns_none():
    synth = Synthesizer()
    assert synth.get("nope", "nope") is None
