import asyncio
import pytest
from app.synthesizer import Synthesizer
from app.providers.base import TTSProvider
from app.voice_catalog import Selection


class FakeProvider(TTSProvider):
    name = "fake_synth"
    api_key_env = "FAKE_SYNTH_KEY"

    def __init__(self, fail: bool = False, delay: float = 0):
        super().__init__(api_key="k")
        self._fail = fail
        self._delay = delay

    def list_models(self): return ["m"]
    async def list_voices(self, model): return []

    async def synthesize(self, text, model, voice_id, language=None):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("boom")
        return (b"AUDIO", "audio/mpeg")


def _sel(oid):
    return Selection(id=oid, label="Voice", provider="fake_synth", model="m", voice="v", language=None)


async def test_run_session_populates_cache():
    synth = Synthesizer()
    provider = FakeProvider()
    items = [(_sel("o1"), provider), (_sel("o2"), provider)]
    sid = synth.start_session("hello", items)
    await synth.wait_all(sid)
    r1 = synth.get(sid, "o1")
    assert r1.status == "done"
    assert r1.audio == b"AUDIO"
    assert r1.char_count == len("hello")


async def test_get_selection_returns_metadata():
    synth = Synthesizer()
    sid = synth.start_session("hi", [(_sel("o1"), FakeProvider())])
    sel = synth.get_selection(sid, "o1")
    assert sel is not None and sel.label == "Voice" and sel.provider == "fake_synth"
    assert synth.get_selection(sid, "ghost") is None


async def test_error_does_not_crash_others():
    synth = Synthesizer()
    items = [(_sel("ok"), FakeProvider()), (_sel("ko"), FakeProvider(fail=True))]
    sid = synth.start_session("hi", items)
    await synth.wait_all(sid)
    assert synth.get(sid, "ok").status == "done"
    assert synth.get(sid, "ko").status == "error"
    assert "boom" in synth.get(sid, "ko").error_msg


async def test_new_session_purges_old():
    synth = Synthesizer()
    s1 = synth.start_session("hi", [(_sel("o1"), FakeProvider())])
    await synth.wait_all(s1)
    s2 = synth.start_session("bye", [(_sel("o1"), FakeProvider())])
    assert synth.get(s1, "o1") is None


def test_get_unknown_returns_none():
    synth = Synthesizer()
    assert synth.get("nope", "nope") is None
