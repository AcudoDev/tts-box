from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class Preset:
    id: str
    label: str
    provider: str
    model: str
    voice: str
    language: str | None = None
    enabled: bool = True
    disabled_reason: str | None = None


def load_presets(path: Path, available_providers: set[str]) -> list[Preset]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entries = (raw or {}).get("presets", [])
    presets: list[Preset] = []
    seen_ids: set[str] = set()
    for entry in entries:
        pid = entry["id"]
        if pid in seen_ids:
            raise ValueError(f"duplicate preset id: {pid}")
        seen_ids.add(pid)
        preset = Preset(
            id=pid,
            label=entry["label"],
            provider=entry["provider"],
            model=entry["model"],
            voice=entry["voice"],
            language=entry.get("language"),
            enabled=entry.get("enabled", True),
        )
        if preset.provider not in available_providers:
            preset.disabled_reason = "API key missing or provider unknown"
        presets.append(preset)
    return presets
