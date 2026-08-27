#!/usr/bin/env python3
"""Load YAML-defined Profile Signal presets before running the orchestrator."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

import orchestrator

PRESET_SCHEMA_VERSION = 1
SUPPORTED_THEMES = {"signal", "minimal", "terminal"}
REQUIRED_PRESETS = {"minimal", "standard", "full", "terminal"}


def load_registry(action_path: Path) -> dict[str, dict[str, Any]]:
    preset_dir = action_path / "presets"
    if not preset_dir.is_dir():
        raise RuntimeError(f"Profile Signal preset directory is missing: {preset_dir}")

    registry: dict[str, dict[str, Any]] = {}
    for path in sorted(preset_dir.glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError(f"Preset must be a YAML mapping: {path.name}")
        if int(raw.get("version", PRESET_SCHEMA_VERSION)) != PRESET_SCHEMA_VERSION:
            raise ValueError(f"Unsupported preset schema version: {path.name}")

        preset_id = str(raw.get("id") or path.stem)
        if preset_id != path.stem:
            raise ValueError(f"Preset id must match filename: {path.name}")
        if preset_id in registry:
            raise ValueError(f"Duplicate preset id: {preset_id}")

        widgets = raw.get("widgets")
        if not isinstance(widgets, list) or not widgets:
            raise ValueError(f"Preset widgets must be a non-empty list: {path.name}")
        widget_names = [str(item) for item in widgets]
        if len(widget_names) != len(set(widget_names)):
            raise ValueError(f"Preset contains duplicate widgets: {path.name}")
        unknown_widgets = sorted(set(widget_names) - set(orchestrator.WIDGET_ORDER))
        if unknown_widgets:
            raise ValueError(
                f"Preset contains unknown widgets ({', '.join(unknown_widgets)}): {path.name}"
            )

        theme = str(raw.get("theme") or "signal")
        if theme not in SUPPORTED_THEMES:
            raise ValueError(f"Preset uses unsupported theme '{theme}': {path.name}")

        registry[preset_id] = {
            "widgets": frozenset(widget_names),
            "theme": theme,
            "description": str(raw.get("description") or ""),
        }

    missing = sorted(REQUIRED_PRESETS - set(registry))
    if missing:
        raise RuntimeError("Missing required Profile Signal presets: " + ", ".join(missing))
    return registry


def install_registry(action_path: Path) -> dict[str, dict[str, Any]]:
    registry = load_registry(action_path)
    orchestrator.PRESETS = {
        preset_id: set(definition["widgets"])
        for preset_id, definition in registry.items()
    }

    original_load_config = orchestrator.load_config

    def load_config(path: Path) -> dict[str, Any]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise ValueError("Profile Signal config must be a YAML mapping")

        config = original_load_config(path)
        preset = str(config.get("preset", "standard"))
        if "theme" not in raw:
            config["theme"] = registry[preset]["theme"]
        return config

    orchestrator.load_config = load_config
    return registry


def main() -> None:
    action_path = Path(
        os.getenv("GITHUB_ACTION_PATH", str(Path(__file__).resolve().parents[1]))
    ).resolve()
    registry = install_registry(action_path)
    print("Profile Signal presets loaded:", ",".join(sorted(registry)))
    orchestrator.main()


if __name__ == "__main__":
    main()
