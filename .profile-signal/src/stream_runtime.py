#!/usr/bin/env python3
"""Lightweight Profile Signal refresh for live-facing widgets.

This runtime intentionally avoids the Search API daily collector, CI aggregation,
and history reports. It refreshes only public-event-driven state and README
blocks so ACTIVITY STREAM and LIVE SIGNAL can run more frequently than the full
profile job while preserving the consumer's preset, theme, README path, and
heavier analytics state.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

DYNAMIC_KEYS = (
    "date",
    "timezone",
    "scope",
    "github_login",
    "status",
    "streak",
    "current_focus",
    "activity_stream",
)

DYNAMIC_WIDGETS = ("live_signal", "current_focus", "activity_stream")

MARKERS = {
    "live_signal": (
        "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->",
        "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->",
    ),
    "current_focus": (
        "<!-- PROFILE-SIGNAL:FOCUS:START -->",
        "<!-- PROFILE-SIGNAL:FOCUS:END -->",
    ),
    "activity_stream": (
        "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->",
        "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->",
    ),
}


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def merge_dynamic_state(existing: Mapping[str, Any], fresh: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in DYNAMIC_KEYS:
        if key in fresh:
            merged[key] = fresh[key]
    return merged


def replace_marker(text: str, start: str, end: str, block: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        return text
    return pattern.sub(block, text, count=1)


def state_refresh_time(state: Mapping[str, Any], fallback: datetime, tz: Any) -> datetime:
    value = state.get("generated_at")
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def with_updated_at(block: str, end_marker: str, refresh_at: datetime) -> str:
    zone = refresh_at.tzname() or "local"
    note = (
        '<p align="center"><sub>latest public signal refresh · '
        + refresh_at.strftime("%H:%M ")
        + zone
        + "</sub></p>"
    )
    return block.replace(end_marker, f"{note}\n{end_marker}", 1)


def load_runtime_config(config_path: Path, action_path: Path) -> tuple[Any, dict[str, Any], dict[str, bool]]:
    src = action_path / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    orchestrator = importlib.import_module("orchestrator")
    preset_runtime = importlib.import_module("preset_runtime")
    preset_runtime.install_registry(action_path)
    config = orchestrator.load_config(config_path)
    enabled = orchestrator.resolve_widgets(config)
    return orchestrator, config, enabled


def run(config_path: Path, workspace: Path, action_path: Path) -> None:
    orchestrator, config, enabled = load_runtime_config(config_path, action_path)

    profile = config.get("profile") or {}
    username = str(profile.get("username") or os.getenv("GITHUB_ACTOR") or "")
    if not username:
        raise ValueError("profile.username is required")
    timezone = str(profile.get("timezone") or "Asia/Tokyo")

    os.environ["GITHUB_LOGIN"] = username
    os.environ["PROFILE_TIMEZONE"] = timezone

    scripts = action_path / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    signal = load_module(scripts / "update-profile-signal.py", "profile_signal_stream_runtime")

    readme_rel = str((config.get("readme") or {}).get("path") or "README.md")
    readme_path = workspace / readme_rel

    signal.ROOT = workspace
    signal.README_PATH = readme_path
    signal.LOG_ROOT = workspace / "data" / "activity"
    signal.STATE_PATH = workspace / "data" / "profile-signal-state.json"
    signal.PULSE_PATH = workspace / "assets" / "dev-pulse.svg"

    now = datetime.now(signal.TZ)
    snapshot = signal.load_snapshot(now.date())
    if snapshot is None:
        print("Profile Signal stream refresh skipped: today's activity snapshot is not available yet")
        return

    try:
        events = signal.fetch_public_events()
    except RuntimeError as exc:
        print(f"warning: public events unavailable; keeping existing stream: {exc}")
        return

    fresh = signal.build_state(snapshot, events, now)

    existing: dict[str, Any] = {}
    if signal.STATE_PATH.exists():
        try:
            existing = json.loads(signal.STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

    merged = merge_dynamic_state(existing, fresh)
    state = signal.write_state(merged, now)
    refresh_at = state_refresh_time(state, now, signal.TZ)

    modules: dict[str, ModuleType] = {"signal": signal}
    blocks = orchestrator.build_blocks(str(config.get("theme", "signal")), snapshot, state, modules)
    if enabled.get("activity_stream", False):
        blocks["activity_stream"] = with_updated_at(
            blocks["activity_stream"],
            MARKERS["activity_stream"][1],
            refresh_at,
        )

    readme = readme_path.read_text(encoding="utf-8")
    for name in DYNAMIC_WIDGETS:
        if not enabled.get(name, False):
            continue
        start, end = MARKERS[name]
        readme = replace_marker(readme, start, end, blocks[name])

    readme_path.write_text(readme, encoding="utf-8")
    print(
        "Profile Signal stream refreshed:",
        f"user={username}",
        f"theme={config.get('theme')}",
        "widgets=" + ",".join(name for name in DYNAMIC_WIDGETS if enabled.get(name, False)),
        f"events={len(events)}",
        f"state_updated={refresh_at.isoformat(timespec='minutes')}",
    )


def main() -> None:
    workspace = Path(os.getenv("GITHUB_WORKSPACE", os.getcwd())).resolve()
    action_path = Path(os.getenv("PROFILE_SIGNAL_ACTION_PATH", Path(__file__).resolve().parents[1])).resolve()
    config_path = Path(os.getenv("PROFILE_SIGNAL_CONFIG", ".github/profile-signal.yml"))
    if not config_path.is_absolute():
        config_path = workspace / config_path
    run(config_path, workspace, action_path)


if __name__ == "__main__":
    main()
