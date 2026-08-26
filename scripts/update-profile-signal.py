#!/usr/bin/env python3
"""Generate Profile Signal Phase 1 widgets from public GitHub activity.

This script intentionally stays separate from update-profile-activity.py during
Phase 1. The existing TODAY collector remains stable while this layer adds
analytics and modular README widgets. A later phase can merge the collectors
behind a normalized data model once the widgets have been dogfooded.
"""

from __future__ import annotations

import html
import json
import os
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from profile_signal import (
    activity_total,
    calculate_streak,
    code_weather,
    current_focus,
    dev_status,
    latest_activity_at,
)

LOGIN = os.getenv("GITHUB_LOGIN", "mizzz-ivr")
TZ_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
LOG_ROOT = ROOT / "data" / "activity"
STATE_PATH = ROOT / "data" / "profile-signal-state.json"

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


def build_state(
    snapshot: dict[str, Any],
    public_events: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    today = now.date()
    today_events = [event for event in public_events if event_local_date(event) == today]
    focus_events = today_events or fallback_events(snapshot)
    focus = current_focus(focus_events)

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
        "schema_version": 1,
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


def replace_marker_block(text: str, start_marker: str, end_marker: str, block: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + block + text[end:]


def update_readme(state: dict[str, Any]) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    live = render_live_signal(state)
    focus = render_focus(state)

    if LIVE_START in text and LIVE_END in text:
        text = replace_marker_block(text, LIVE_START, LIVE_END, live)
    elif DAILY_START in text:
        text = text.replace(DAILY_START, f"{live}\n\n{DAILY_START}", 1)
    else:
        raise RuntimeError("Could not find DAILY-ACTIVITY marker for LIVE SIGNAL insertion")

    if FOCUS_START in text and FOCUS_END in text:
        text = replace_marker_block(text, FOCUS_START, FOCUS_END, focus)
    elif DAILY_END in text:
        text = text.replace(DAILY_END, f"{DAILY_END}\n\n{focus}", 1)
    else:
        raise RuntimeError("Could not find DAILY-ACTIVITY marker for CURRENT FOCUS insertion")

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
    update_readme(state)
    print(
        "Profile Signal refreshed:",
        state["status"]["label"],
        state["code_weather"]["label"],
        state["streak"],
        (state.get("current_focus") or {}).get("repo"),
    )


if __name__ == "__main__":
    main()
