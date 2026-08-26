#!/usr/bin/env python3
"""Generate modular Profile Signal widgets from public GitHub activity.

TODAY remains the stable Search API collector. This layer consumes its daily
snapshots plus GitHub's public Events API, derives analytics, and renders the
profile widgets. Keeping collection and presentation separate lets the profile
be dogfooded before the collectors are unified behind a normalized data model.
"""

from __future__ import annotations

import html
import json
import os
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from profile_signal import (
    activity_stream,
    activity_total,
    calculate_streak,
    code_weather,
    current_focus,
    dev_status,
    latest_activity_at,
    ranked_repositories,
)

LOGIN = os.getenv("GITHUB_LOGIN", "mizzz-ivr")
TZ_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
LOG_ROOT = ROOT / "data" / "activity"
STATE_PATH = ROOT / "data" / "profile-signal-state.json"
PULSE_PATH = ROOT / "assets" / "dev-pulse.svg"

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = f"{LOGIN}-profile-signal"
EVENTS_PER_PAGE = 100
EVENT_PAGES = 3

DAILY_START = "<!-- DAILY-ACTIVITY:START -->"
DAILY_END = "<!-- DAILY-ACTIVITY:END -->"
LIVE_START = "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->"
LIVE_END = "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->"
FOCUS_START = "<!-- PROFILE-SIGNAL:FOCUS:START -->"
FOCUS_END = "<!-- PROFILE-SIGNAL:FOCUS:END -->"
PULSE_START = "<!-- PROFILE-SIGNAL:PULSE:START -->"
PULSE_END = "<!-- PROFILE-SIGNAL:PULSE:END -->"
BUILDING_START = "<!-- PROFILE-SIGNAL:NOW-BUILDING:START -->"
BUILDING_END = "<!-- PROFILE-SIGNAL:NOW-BUILDING:END -->"
STREAM_START = "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->"
STREAM_END = "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->"


def request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 429, 500, 502, 503, 504} and attempt < 2:
                retry_after = exc.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 + attempt * 2
                time_module.sleep(max(1, min(delay, 30)))
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API request failed ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < 2:
                time_module.sleep(2 + attempt * 2)
                continue
            raise RuntimeError(f"GitHub API request failed: {exc}") from exc

    raise RuntimeError("GitHub API request failed")


def snapshot_path(day: date) -> Path:
    return LOG_ROOT / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.json"


def load_snapshot(day: date) -> dict[str, Any] | None:
    path = snapshot_path(day)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def fetch_public_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    quoted_login = urllib.parse.quote(LOGIN, safe="")
    for page in range(1, EVENT_PAGES + 1):
        url = (
            f"{API_BASE}/users/{quoted_login}/events/public"
            f"?per_page={EVENTS_PER_PAGE}&page={page}"
        )
        payload = request_json(url)
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected public events payload")
        events.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < EVENTS_PER_PAGE:
            break
    return events


def event_local_date(event: dict[str, Any]) -> date | None:
    value = event.get("created_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(TZ).date()


def fallback_events(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    type_map = {
        "commit": ("PushEvent", {"size": 1}),
        "pr": ("PullRequestEvent", {"action": "opened"}),
        "issue": ("IssuesEvent", {"action": "opened"}),
        "done": ("IssuesEvent", {"action": "closed"}),
    }
    result: list[dict[str, Any]] = []
    for item in snapshot.get("activity") or []:
        event_type, payload = type_map.get(str(item.get("type")), ("WatchEvent", {}))
        result.append(
            {
                "type": event_type,
                "repo": {"name": item.get("repo", "")},
                "payload": payload,
                "created_at": item.get("at", ""),
            }
        )
    return result


def fetch_languages(repo: str) -> list[str]:
    if "/" not in repo:
        return []
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in repo.split("/", 1))
    payload = request_json(f"{API_BASE}/repos/{encoded}/languages")
    if not isinstance(payload, dict):
        return []
    ranked = sorted(payload.items(), key=lambda pair: (-int(pair[1]), pair[0]))
    return [str(language) for language, _ in ranked[:4]]


def local_active_dates(public_events: list[dict[str, Any]]) -> set[date]:
    active: set[date] = set()

    for path in LOG_ROOT.glob("*/*/*.json"):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            snapshot_day = date.fromisoformat(str(snapshot.get("date")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if activity_total(snapshot) > 0:
            active.add(snapshot_day)

    for event in public_events:
        day = event_local_date(event)
        if day is not None:
            active.add(day)

    return active


def format_last_activity(value: str | None) -> str:
    if not value:
        return "no recent public activity"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return "recent public activity"
    now = datetime.now(TZ)
    if parsed.date() == now.date():
        return parsed.strftime("%H:%M JST")
    return parsed.strftime("%m/%d %H:%M JST")


def pulse_series(today: date) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        snapshot = load_snapshot(day)
        metrics = dict((snapshot or {}).get("metrics") or {})
        result.append(
            {
                "date": day.isoformat(),
                "total": activity_total(snapshot),
                "commits": int(metrics.get("commits", 0) or 0),
                "prs": int(metrics.get("prs_opened", 0) or 0),
                "issues": int(metrics.get("issues_created", 0) or 0)
                + int(metrics.get("issues_completed", 0) or 0),
            }
        )
    return result


def build_state(
    snapshot: dict[str, Any],
    public_events: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    today = now.date()
    today_events = [event for event in public_events if event_local_date(event) == today]
    widget_events = today_events or fallback_events(snapshot)

    focus = current_focus(widget_events)
    if focus is not None:
        try:
            focus["stack"] = fetch_languages(str(focus["repo"]))
        except RuntimeError as exc:
            print(f"warning: could not fetch focus languages: {exc}")
            focus["stack"] = []

    last_at = latest_activity_at(snapshot, public_events)
    status = dev_status(last_at, now)
    weather = code_weather(activity_total(snapshot))
    streak = calculate_streak(local_active_dates(public_events), today)

    return {
        "schema_version": 2,
        "date": today.isoformat(),
        "timezone": TZ_NAME,
        "scope": "public",
        "github_login": LOGIN,
        "status": {
            "label": status["label"],
            "symbol": status["symbol"],
            "last_activity_at": last_at,
        },
        "code_weather": weather,
        "streak": streak,
        "activity_total": activity_total(snapshot),
        "current_focus": focus,
        "dev_pulse": pulse_series(today),
        "now_building": ranked_repositories(widget_events, limit=3),
        "activity_stream": activity_stream(widget_events, limit=4),
    }


def write_state(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    existing: dict[str, Any] | None = None
    if STATE_PATH.exists():
        try:
            existing = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = None

    comparable = None
    if existing is not None:
        comparable = {key: value for key, value in existing.items() if key != "generated_at"}
    if comparable == state:
        return existing or state

    payload = dict(state)
    payload["generated_at"] = now.isoformat(timespec="seconds")
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def render_today(snapshot: dict[str, Any]) -> str:
    metrics = snapshot.get("metrics") or {}
    return f'''{DAILY_START}
## TODAY // Activity overview

<p align="center">
  <sub>{html.escape(str(snapshot.get("date", "")))} JST · public GitHub activity</sub>
</p>

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS OPENED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_created", 0) or 0)}</strong><br/><sub>ISSUES CREATED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE</sub></td>
  </tr>
</table>

<p align="center"><sub>Auto-updated by GitHub Actions · recent events are shown in ACTIVITY STREAM</sub></p>
{DAILY_END}'''


def render_live_signal(state: dict[str, Any]) -> str:
    status = state.get("status") or {}
    weather = state.get("code_weather") or {}
    last_display = html.escape(format_last_activity(status.get("last_activity_at")))
    total = int(state.get("activity_total", 0) or 0)
    streak = int(state.get("streak", 0) or 0)

    return f'''{LIVE_START}
## LIVE SIGNAL // Development status

<table>
  <tr>
    <td width="33%" align="center"><strong>{html.escape(str(status.get("symbol", "○")))} {html.escape(str(status.get("label", "QUIET")))}</strong><br/><sub>last public activity · {last_display}</sub></td>
    <td width="34%" align="center"><strong>{html.escape(str(weather.get("icon", "🌙")))} {html.escape(str(weather.get("label", "REST DAY")))}</strong><br/><sub>{total} public actions today</sub></td>
    <td width="33%" align="center"><strong>🔥 {streak} DAY STREAK</strong><br/><sub>public activity · recent history</sub></td>
  </tr>
</table>
{LIVE_END}'''


def render_focus(state: dict[str, Any]) -> str:
    focus = state.get("current_focus")
    if not focus:
        body = '<p align="center"><sub>No public focus detected yet today.</sub></p>'
    else:
        repo = html.escape(str(focus.get("repo", "unknown")))
        repo_url = html.escape(f"https://github.com/{focus.get('repo', '')}", quote=True)
        score = int(focus.get("score", 0) or 0)
        share = int(focus.get("share", 0) or 0)
        event_count = int(focus.get("events", 0) or 0)
        stack = focus.get("stack") or []
        stack_html = " ".join(f"<code>{html.escape(str(language))}</code>" for language in stack)
        if not stack_html:
            stack_html = "<sub>language data unavailable</sub>"

        body = f'''<table>
  <tr>
    <td width="62%" valign="top"><strong><a href="{repo_url}">{repo}</a></strong><br/><sub>{share}% of weighted repository activity · score {score} · {event_count} events</sub></td>
    <td width="38%" valign="top"><strong>TODAY&apos;S STACK</strong><br/>{stack_html}</td>
  </tr>
</table>'''

    return f'''{FOCUS_START}
## CURRENT FOCUS // What is moving now

{body}

<p align="center"><sub>Focus uses weighted public GitHub events; repository language data comes from the current focus repository.</sub></p>
{FOCUS_END}'''


def render_pulse_svg(state: dict[str, Any]) -> str:
    series = list(state.get("dev_pulse") or [])
    width = 880
    height = 210
    chart_top = 58
    chart_bottom = 148
    left = 54
    step = 112
    maximum = max(1, max((int(item.get("total", 0) or 0) for item in series), default=0))

    points: list[str] = []
    labels: list[str] = []
    circles: list[str] = []
    for index, item in enumerate(series):
        total = int(item.get("total", 0) or 0)
        x = left + index * step + 31
        ratio = total / maximum
        y = chart_bottom - round((chart_bottom - chart_top) * ratio)
        points.append(f"{x},{y}")
        day = str(item.get("date", ""))[5:]
        labels.append(f'<text class="label" x="{x}" y="177" text-anchor="middle">{day}</text>')
        labels.append(f'<text class="value" x="{x}" y="{max(38, y - 10)}" text-anchor="middle">{total}</text>')
        circles.append(f'<circle class="point" cx="{x}" cy="{y}" r="5" />')

    polyline = " ".join(points)
    area_points = f"{left + 31},{chart_bottom} {polyline} {left + (len(series) - 1) * step + 31},{chart_bottom}" if series else ""
    latest = series[-1] if series else {}
    latest_summary = (
        f"C {int(latest.get('commits', 0) or 0)} · "
        f"PR {int(latest.get('prs', 0) or 0)} · "
        f"ISSUE {int(latest.get('issues', 0) or 0)}"
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Developer activity pulse for the last seven days</title>
  <desc id="desc">Seven day public GitHub activity totals, with today's commit, pull request and issue counts.</desc>
  <style>
    .title {{ fill: #24292f; font: 600 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: .08em; }}
    .meta {{ fill: #57606a; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .label {{ fill: #57606a; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .value {{ fill: #57606a; font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .grid {{ stroke: #d0d7de; stroke-width: 1; }}
    .area {{ fill: #8b5cf6; fill-opacity: .10; }}
    .line {{ fill: none; stroke: #8b5cf6; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
    .point {{ fill: #8b5cf6; }}
    @media (prefers-color-scheme: dark) {{
      .title {{ fill: #f0f6fc; }}
      .meta, .label, .value {{ fill: #8c959f; }}
      .grid {{ stroke: #30363d; }}
      .area {{ fill: #a78bfa; fill-opacity: .12; }}
      .line {{ stroke: #a78bfa; }}
      .point {{ fill: #a78bfa; }}
    }}
  </style>
  <text class="title" x="24" y="25">DEV PULSE · LAST 7 DAYS</text>
  <text class="meta" x="856" y="25" text-anchor="end">{html.escape(latest_summary)}</text>
  <line class="grid" x1="24" y1="{chart_bottom + 0.5}" x2="856" y2="{chart_bottom + 0.5}" />
  <polygon class="area" points="{area_points}" />
  <polyline class="line" points="{polyline}" />
  {''.join(circles)}
  {''.join(labels)}
  <text class="meta" x="24" y="201">activity = commits + PRs opened + issues created + issues done</text>
</svg>
'''


def write_pulse_svg(state: dict[str, Any]) -> None:
    PULSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_pulse_svg(state)
    if PULSE_PATH.exists() and PULSE_PATH.read_text(encoding="utf-8") == rendered:
        return
    PULSE_PATH.write_text(rendered, encoding="utf-8")


def render_pulse() -> str:
    return f'''{PULSE_START}
## DEV PULSE // Last 7 days

<p align="center">
  <img src="./assets/dev-pulse.svg" width="100%" alt="7 day public GitHub development pulse" />
</p>
{PULSE_END}'''


def render_now_building(state: dict[str, Any]) -> str:
    repos = list(state.get("now_building") or [])
    if not repos:
        content = '<p align="center"><sub>No active public repositories detected yet today.</sub></p>'
    else:
        cards: list[str] = []
        for index, item in enumerate(repos, start=1):
            repo_raw = str(item.get("repo", "unknown"))
            repo = html.escape(repo_raw)
            url = html.escape(f"https://github.com/{repo_raw}", quote=True)
            share = int(item.get("share", 0) or 0)
            score = int(item.get("score", 0) or 0)
            events = int(item.get("events", 0) or 0)
            active = html.escape(format_last_activity(item.get("last_activity_at")))
            cards.append(
                f'<td width="33%" valign="top"><strong>{index:02d} · <a href="{url}">{repo}</a></strong><br/>'
                f'<sub>{share}% weighted activity · score {score} · {events} events<br/>last activity · {active}</sub></td>'
            )
        while len(cards) < 3:
            cards.append('<td width="33%" valign="top"><sub>waiting for activity</sub></td>')
        content = f'''<table>
  <tr>
    {''.join(cards)}
  </tr>
</table>'''

    return f'''{BUILDING_START}
## NOW BUILDING // Active repositories

{content}

<p align="center"><sub>Ranked by weighted public GitHub activity · project health joins this widget in a later phase.</sub></p>
{BUILDING_END}'''


def format_stream_time(value: str, today: date) -> str:
    if not value:
        return "--:--"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return "--:--"
    if parsed.date() == today:
        return parsed.strftime("%H:%M")
    return parsed.strftime("%m/%d")


def render_activity_stream(state: dict[str, Any]) -> str:
    items = list(state.get("activity_stream") or [])
    today = date.fromisoformat(str(state.get("date")))
    if not items:
        rows = '<tr><td colspan="3" align="center"><sub>No public development events recorded yet today.</sub></td></tr>'
    else:
        rendered_rows: list[str] = []
        for item in items:
            label = html.escape(str(item.get("label", "ACTIVITY")))
            repo_raw = str(item.get("repo", "unknown"))
            repo = html.escape(repo_raw)
            repo_url = html.escape(f"https://github.com/{repo_raw}", quote=True)
            title = html.escape(str(item.get("title", "Public activity")))
            url = html.escape(str(item.get("url", repo_url)), quote=True)
            at = html.escape(format_stream_time(str(item.get("at", "")), today))
            rendered_rows.append(
                f'<tr><td width="10%"><code>{at}</code></td>'
                f'<td width="14%"><code>{label}</code></td>'
                f'<td><strong><a href="{repo_url}">{repo}</a></strong> — <a href="{url}">{title}</a></td></tr>'
            )
        rows = "\n    ".join(rendered_rows)

    return f'''{STREAM_START}
## ACTIVITY STREAM // Latest public signals

<table>
  <tbody>
    {rows}
  </tbody>
</table>
{STREAM_END}'''


def replace_marker_block(text: str, start_marker: str, end_marker: str, block: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + block + text[end:]


def insert_after_marker(text: str, end_marker: str, block: str) -> str:
    if end_marker not in text:
        raise RuntimeError(f"Could not find insertion marker: {end_marker}")
    return text.replace(end_marker, f"{end_marker}\n\n{block}", 1)


def update_readme(snapshot: dict[str, Any], state: dict[str, Any]) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    today = render_today(snapshot)
    live = render_live_signal(state)
    focus = render_focus(state)
    pulse = render_pulse()
    building = render_now_building(state)
    stream = render_activity_stream(state)

    if LIVE_START in text and LIVE_END in text:
        text = replace_marker_block(text, LIVE_START, LIVE_END, live)
    elif DAILY_START in text:
        text = text.replace(DAILY_START, f"{live}\n\n{DAILY_START}", 1)
    else:
        raise RuntimeError("Could not find DAILY-ACTIVITY marker for LIVE SIGNAL insertion")

    if DAILY_START in text and DAILY_END in text:
        text = replace_marker_block(text, DAILY_START, DAILY_END, today)
    else:
        raise RuntimeError("Could not find DAILY-ACTIVITY marker for TODAY rendering")

    if FOCUS_START in text and FOCUS_END in text:
        text = replace_marker_block(text, FOCUS_START, FOCUS_END, focus)
    else:
        text = insert_after_marker(text, DAILY_END, focus)

    if PULSE_START in text and PULSE_END in text:
        text = replace_marker_block(text, PULSE_START, PULSE_END, pulse)
    else:
        text = insert_after_marker(text, FOCUS_END, pulse)

    if BUILDING_START in text and BUILDING_END in text:
        text = replace_marker_block(text, BUILDING_START, BUILDING_END, building)
    else:
        text = insert_after_marker(text, PULSE_END, building)

    if STREAM_START in text and STREAM_END in text:
        text = replace_marker_block(text, STREAM_START, STREAM_END, stream)
    else:
        text = insert_after_marker(text, BUILDING_END, stream)

    README_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    now = datetime.now(TZ)
    snapshot = load_snapshot(now.date())
    if snapshot is None:
        raise RuntimeError("Today's activity snapshot does not exist; run update-profile-activity.py first")

    try:
        public_events = fetch_public_events()
    except RuntimeError as exc:
        print(f"warning: public events unavailable, using snapshot fallback: {exc}")
        public_events = []

    state = write_state(build_state(snapshot, public_events, now), now)
    write_pulse_svg(state)
    update_readme(snapshot, state)
    print(
        "Profile Signal refreshed:",
        state["status"]["label"],
        state["code_weather"]["label"],
        state["streak"],
        (state.get("current_focus") or {}).get("repo"),
        f"building={len(state.get('now_building') or [])}",
        f"stream={len(state.get('activity_stream') or [])}",
    )


if __name__ == "__main__":
    main()
