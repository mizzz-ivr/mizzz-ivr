#!/usr/bin/env python3
"""Config-driven Profile Signal orchestrator.

This wrapper lets the current profile implementation run as a reusable GitHub
Action without forcing the underlying collectors/renderers to know where the
consumer repository lives. It loads the existing modules, redirects their
workspace paths, executes only the required collection/analytics phases, then
renders only the widgets enabled by config.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import yaml

WIDGET_ORDER = (
    "live_signal",
    "today",
    "current_focus",
    "dev_pulse",
    "now_building",
    "activity_stream",
    "dev_recap",
)

PRESETS = {
    "minimal": {"live_signal", "current_focus"},
    "standard": {"live_signal", "today", "current_focus", "dev_pulse"},
    "full": set(WIDGET_ORDER),
    "terminal": set(WIDGET_ORDER),
}

MARKERS = {
    "live_signal": ("<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->", "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->"),
    "today": ("<!-- DAILY-ACTIVITY:START -->", "<!-- DAILY-ACTIVITY:END -->"),
    "current_focus": ("<!-- PROFILE-SIGNAL:FOCUS:START -->", "<!-- PROFILE-SIGNAL:FOCUS:END -->"),
    "dev_pulse": ("<!-- PROFILE-SIGNAL:PULSE:START -->", "<!-- PROFILE-SIGNAL:PULSE:END -->"),
    "now_building": ("<!-- PROFILE-SIGNAL:NOW-BUILDING:START -->", "<!-- PROFILE-SIGNAL:NOW-BUILDING:END -->"),
    "activity_stream": ("<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->", "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->"),
    "dev_recap": ("<!-- PROFILE-SIGNAL:RECAP:START -->", "<!-- PROFILE-SIGNAL:RECAP:END -->"),
}

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "profile": {"username": "", "timezone": "Asia/Tokyo"},
    "privacy": {"public_only": True},
    "preset": "standard",
    "theme": "signal",
    "widgets": {},
    "readme": {
        "path": "README.md",
        "auto_insert_markers": True,
        "insert_before": "## NOW // What I build",
        "empty_disabled": True,
    },
}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


def load_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError("Profile Signal config must be a YAML mapping")
    config = deep_merge(DEFAULT_CONFIG, raw)
    if int(config.get("version", 1)) != 1:
        raise ValueError("Unsupported Profile Signal config version")
    if config.get("privacy", {}).get("public_only") is not True:
        raise ValueError("Profile Signal v0 requires privacy.public_only: true")
    preset = str(config.get("preset", "standard"))
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    theme = str(config.get("theme", "signal"))
    if theme not in {"signal", "minimal", "terminal"}:
        raise ValueError(f"Unknown theme: {theme}")
    if preset == "terminal" and "theme" not in raw:
        config["theme"] = "terminal"
    return config


def resolve_widgets(config: Mapping[str, Any]) -> dict[str, bool]:
    preset = str(config.get("preset", "standard"))
    enabled = {name: name in PRESETS[preset] for name in WIDGET_ORDER}
    overrides = config.get("widgets") or {}
    if not isinstance(overrides, Mapping):
        raise ValueError("widgets must be a mapping")
    for name, value in overrides.items():
        if name not in enabled:
            raise ValueError(f"Unknown widget: {name}")
        if isinstance(value, Mapping):
            if "enabled" in value:
                enabled[name] = bool(value["enabled"])
        else:
            enabled[name] = bool(value)
    return enabled


def locate_source_root(action_path: Path) -> Path:
    for candidate in (action_path, action_path.parent):
        if (candidate / "scripts" / "update-profile-activity.py").exists():
            return candidate
    raise RuntimeError("Could not locate Profile Signal source scripts")


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def redirect_paths(module: ModuleType, workspace: Path, mapping: Mapping[str, str]) -> None:
    if hasattr(module, "ROOT"):
        module.ROOT = workspace
    for attr, rel in mapping.items():
        if hasattr(module, attr):
            setattr(module, attr, workspace / rel)


def marker_pattern(start: str, end: str) -> re.Pattern[str]:
    return re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)


def empty_marker(name: str) -> str:
    start, end = MARKERS[name]
    return f"{start}\n{end}"


def apply_blocks(text: str, blocks: Mapping[str, str], enabled: Mapping[str, bool], *, auto_insert: bool, insert_before: str, empty_disabled: bool) -> str:
    missing: list[str] = []
    for name in WIDGET_ORDER:
        start, end = MARKERS[name]
        has_pair = start in text and end in text
        if enabled.get(name, False):
            if has_pair:
                text = marker_pattern(start, end).sub(blocks[name], text, count=1)
            else:
                missing.append(name)
        elif has_pair and empty_disabled:
            text = marker_pattern(start, end).sub(empty_marker(name), text, count=1)

    if missing:
        if not auto_insert:
            names = ", ".join(missing)
            raise RuntimeError(f"README is missing enabled widget markers: {names}")
        insertion = "\n\n".join(blocks[name] for name in WIDGET_ORDER if name in missing)
        if insert_before and insert_before in text:
            text = text.replace(insert_before, f"{insertion}\n\n---\n\n{insert_before}", 1)
        else:
            text = text.rstrip() + "\n\n---\n\n" + insertion + "\n"
    return text


def status_values(state: Mapping[str, Any]) -> tuple[str, str, str, int, int]:
    status = state.get("status") or {}
    weather = state.get("code_weather") or {}
    return (
        str(status.get("symbol", "○")),
        str(status.get("label", "QUIET")),
        f"{weather.get('icon', '🌙')} {weather.get('label', 'REST DAY')}",
        int(state.get("activity_total", 0) or 0),
        int(state.get("streak", 0) or 0),
    )


def render_minimal(name: str, snapshot: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    start, end = MARKERS[name]
    if name == "live_signal":
        symbol, label, weather, total, streak = status_values(state)
        return f"{start}\n## LIVE SIGNAL\n\n`{symbol} {label}` · `{weather}` · `🔥 {streak}d` · {total} actions\n{end}"
    if name == "today":
        m = snapshot.get("metrics") or {}
        return f"{start}\n## TODAY\n\n`{int(m.get('commits', 0) or 0)} commits` · `{int(m.get('prs_opened', 0) or 0)} PRs` · `{int(m.get('issues_created', 0) or 0)} issues` · `{int(m.get('issues_completed', 0) or 0)} done`\n{end}"
    if name == "current_focus":
        focus = state.get("current_focus") or {}
        repo = str(focus.get("repo") or "No public focus yet")
        stack = " · ".join(str(x) for x in focus.get("stack") or [])
        share = int(focus.get("share", 0) or 0)
        extra = f" · {stack}" if stack else ""
        return f"{start}\n## CURRENT FOCUS\n\n**{repo}** · {share}% weighted activity{extra}\n{end}"
    if name == "dev_pulse":
        return f'{start}\n## DEV PULSE\n\n<p align="center"><img src="./assets/dev-pulse.svg" width="100%" alt="7 day development pulse" /></p>\n{end}'
    if name == "now_building":
        rows = [f"- **{item.get('repo')}** · {item.get('share', 0)}% · {(item.get('health') or {}).get('label', 'ACTIVE')}" for item in state.get("now_building") or []]
        return f"{start}\n## NOW BUILDING\n\n{chr(10).join(rows) or '- No active public repositories yet.'}\n{end}"
    if name == "activity_stream":
        rows = [f"- `{item.get('label', 'ACTIVITY')}` **{item.get('repo')}** — {item.get('title')}" for item in state.get("activity_stream") or []]
        return f"{start}\n## ACTIVITY STREAM\n\n{chr(10).join(rows) or '- No recent public development events.'}\n{end}"
    recap = state.get("dev_recap") or {}
    weekly = recap.get("weekly") or {}
    metrics = weekly.get("metrics") or {}
    return f"{start}\n## DEV RECAP\n\n**{weekly.get('period', '')}** · {metrics.get('commits', 0)} commits · {metrics.get('prs_opened', 0)} PRs · {metrics.get('issues_completed', 0)} issues done\n{end}"


def render_terminal(name: str, snapshot: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    start, end = MARKERS[name]
    heading = name.replace("_", " ").upper()
    lines: list[str] = []
    if name == "live_signal":
        symbol, label, weather, total, streak = status_values(state)
        lines = [f"status   {symbol} {label}", f"weather  {weather}", f"streak   {streak} days", f"actions  {total} today"]
    elif name == "today":
        m = snapshot.get("metrics") or {}
        lines = [f"commits  {m.get('commits', 0)}", f"prs      {m.get('prs_opened', 0)}", f"issues   {m.get('issues_created', 0)}", f"done     {m.get('issues_completed', 0)}"]
    elif name == "current_focus":
        focus = state.get("current_focus") or {}
        lines = [f"project  {focus.get('repo', 'none')}", f"share    {focus.get('share', 0)}%", f"score    {focus.get('score', 0)}", f"stack    {' / '.join(str(x) for x in focus.get('stack') or []) or 'n/a'}"]
    elif name == "dev_pulse":
        ci = state.get("ci_signal") or {}
        rate = ci.get("pass_rate")
        rate_text = "n/a" if rate is None else f"{rate}%"
        lines = ["window   last 7 days", f"ci       {ci.get('label', 'NO SIGNAL')}", f"pass     {rate_text}", f"runs     {ci.get('passed', 0)}/{ci.get('evaluated', 0)} passed"]
    elif name == "now_building":
        lines = [f"{i:02d}       {item.get('repo')} · {(item.get('health') or {}).get('label', 'ACTIVE')}" for i, item in enumerate(state.get("now_building") or [], 1)] or ["none"]
    elif name == "activity_stream":
        lines = [f"{item.get('label', 'ACTIVITY'):<8} {item.get('repo')} · {item.get('title')}" for item in state.get("activity_stream") or []] or ["no recent public development events"]
    else:
        recap = state.get("dev_recap") or {}
        weekly = recap.get("weekly") or {}
        m = weekly.get("metrics") or {}
        lines = [f"period   {weekly.get('period', '')}", f"commits  {m.get('commits', 0)}", f"prs      {m.get('prs_opened', 0)}", f"done     {m.get('issues_completed', 0)}", f"badges   {len(recap.get('achievements') or [])}"]
    body = "\n".join(lines)
    return f"{start}\n## {heading} // Terminal\n\n```text\nmizzz@github:~$ {name.replace('_', '-')}\n{body}\n```\n{end}"


def signal_blocks(snapshot: Mapping[str, Any], state: Mapping[str, Any], modules: Mapping[str, ModuleType]) -> dict[str, str]:
    signal = modules["signal"]
    operations = modules.get("operations")
    history = modules.get("history")
    return {
        "live_signal": signal.render_live_signal(dict(state)),
        "today": signal.render_today(dict(snapshot)),
        "current_focus": signal.render_focus(dict(state)),
        "dev_pulse": operations.render_pulse(dict(state)) if operations else signal.render_pulse(),
        "now_building": operations.render_now_building(dict(state)) if operations else signal.render_now_building(dict(state)),
        "activity_stream": signal.render_activity_stream(dict(state)),
        "dev_recap": history.render_recap(state) if history else empty_marker("dev_recap"),
    }


def build_blocks(theme: str, snapshot: Mapping[str, Any], state: Mapping[str, Any], modules: Mapping[str, ModuleType]) -> dict[str, str]:
    if theme == "signal":
        return signal_blocks(snapshot, state, modules)
    if theme == "minimal":
        return {name: render_minimal(name, snapshot, state) for name in WIDGET_ORDER}
    return {name: render_terminal(name, snapshot, state) for name in WIDGET_ORDER}


def run(config: Mapping[str, Any], action_path: Path, workspace: Path) -> None:
    username = str((config.get("profile") or {}).get("username") or os.getenv("GITHUB_ACTOR") or "")
    if not username:
        raise ValueError("profile.username is required")
    timezone = str((config.get("profile") or {}).get("timezone") or "Asia/Tokyo")
    os.environ["GITHUB_LOGIN"] = username
    os.environ["PROFILE_TIMEZONE"] = timezone

    enabled = resolve_widgets(config)
    source_root = locate_source_root(action_path)
    scripts = source_root / "scripts"
    sys.path.insert(0, str(scripts))

    activity = load_module(scripts / "update-profile-activity.py", "profile_signal_activity_runtime")
    signal = load_module(scripts / "update-profile-signal.py", "profile_signal_widget_runtime")
    operations: ModuleType | None = None
    history: ModuleType | None = None

    redirect_paths(activity, workspace, {"README_PATH": "README.md", "LOG_ROOT": "data/activity", "CHART_PATH": "assets/activity-7d.svg"})
    redirect_paths(signal, workspace, {"README_PATH": "README.md", "LOG_ROOT": "data/activity", "STATE_PATH": "data/profile-signal-state.json", "PULSE_PATH": "assets/dev-pulse.svg"})

    readme_rel = str((config.get("readme") or {}).get("path") or "README.md")
    readme_path = workspace / readme_rel
    activity.README_PATH = readme_path
    signal.README_PATH = readme_path

    now = datetime.now(signal.TZ)
    today = now.date()
    yesterday = today - timedelta(days=1)
    today_snapshot = activity.write_snapshot(today, activity.collect_day(today), now)
    activity.write_snapshot(yesterday, activity.collect_day(yesterday), now)

    needs_signal = any(enabled[name] for name in WIDGET_ORDER if name != "today")
    if needs_signal:
        try:
            events = signal.fetch_public_events()
        except RuntimeError as exc:
            print(f"warning: public events unavailable, using snapshot fallback: {exc}")
            events = []
        state = signal.write_state(signal.build_state(today_snapshot, events, now), now)
        if enabled.get("dev_pulse"):
            signal.write_pulse_svg(state)
    else:
        state = {"schema_version": 1, "date": today.isoformat(), "timezone": timezone, "scope": "public", "github_login": username}

    needs_operations = enabled.get("dev_pulse", False) or enabled.get("now_building", False)
    if needs_operations and needs_signal:
        operations = load_module(scripts / "profile_signal_operations.py", "profile_signal_operations_runtime")
        redirect_paths(operations, workspace, {"README_PATH": readme_rel, "STATE_PATH": "data/profile-signal-state.json"})
        operations.README_PATH = readme_path
        state = operations.write_state(operations.enrich_now_building(dict(state), now), now)

    if enabled.get("dev_recap") and needs_signal:
        history = load_module(scripts / "profile_signal_history.py", "profile_signal_history_runtime")
        redirect_paths(history, workspace, {"README_PATH": readme_rel, "LOG_ROOT": "data/activity", "WEEKLY_ROOT": "data/weekly", "MONTHLY_ROOT": "data/monthly", "STATE_PATH": "data/profile-signal-state.json"})
        history.README_PATH = readme_path
        snapshots = history.load_all_snapshots()
        weekly, monthly = history.refresh_reports(snapshots, today, now)
        state = history.write_state(history.history_state(dict(state), snapshots, weekly, monthly), now)

    modules: dict[str, ModuleType] = {"signal": signal}
    if operations:
        modules["operations"] = operations
    if history:
        modules["history"] = history

    blocks = build_blocks(str(config.get("theme", "signal")), today_snapshot, state, modules)
    readme = readme_path.read_text(encoding="utf-8")
    readme_cfg = config.get("readme") or {}
    updated = apply_blocks(
        readme,
        blocks,
        enabled,
        auto_insert=bool(readme_cfg.get("auto_insert_markers", True)),
        insert_before=str(readme_cfg.get("insert_before") or ""),
        empty_disabled=bool(readme_cfg.get("empty_disabled", True)),
    )
    readme_path.write_text(updated, encoding="utf-8")
    print("Profile Signal action refreshed:", f"user={username}", f"preset={config.get('preset')}", f"theme={config.get('theme')}", "widgets=" + ",".join(name for name in WIDGET_ORDER if enabled[name]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.getenv("PROFILE_SIGNAL_CONFIG", ".github/profile-signal.yml"))
    parser.add_argument("--workspace", default=os.getenv("GITHUB_WORKSPACE", os.getcwd()))
    parser.add_argument("--action-path", default=os.getenv("GITHUB_ACTION_PATH", str(Path(__file__).resolve().parents[1])))
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    action_path = Path(args.action_path).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = workspace / config_path
    config = load_config(config_path)
    run(config, action_path, workspace)


if __name__ == "__main__":
    main()
