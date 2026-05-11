import pytest
from pathlib import Path
from app.presets import load_presets, Preset

FIX = Path(__file__).parent / "fixtures"


def test_load_valid_returns_presets():
    presets = load_presets(FIX / "presets_valid.yaml", available_providers={"alpha", "beta"})
    assert len(presets) == 2
    assert presets[0].id == "p1"
    assert presets[0].enabled is True
    assert presets[0].disabled_reason is None
    assert presets[1].enabled is False


def test_unknown_provider_marks_disabled():
    presets = load_presets(FIX / "presets_valid.yaml", available_providers={"alpha"})
    p2 = next(p for p in presets if p.id == "p2")
    assert p2.disabled_reason == "API key missing or provider unknown"


def test_duplicate_id_raises():
    with pytest.raises(ValueError, match="duplicate"):
        load_presets(FIX / "presets_dup_id.yaml", available_providers={"alpha"})


def test_preset_default_enabled_true():
    p = Preset(id="x", label="X", provider="alpha", model="m", voice="v")
    assert p.enabled is True
    assert p.disabled_reason is None
