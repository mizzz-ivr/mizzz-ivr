#!/usr/bin/env python3
"""Pure analytics helpers for Profile Signal widgets."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable, Mapping

WEIGHTS = {
    "commit": 1,
    "issue_opened": 2,
    "issue_completed": 3,
    "pr_opened": 4,
    "pr_merged": 6,
    "release": 10,
}

WEATHER_LEVELS = (
    (0, "REST DAY", "🌙"),
    (5, "LIGHT CODING", "☁️"),
    (20, "ACTIVE", "🌤️"),
    (50, "HEAVY CODING", "⚡"),
)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def activity_total(snapshot: Mapping[str, Any] | None) -> int:
    if not snapshot:
        return 0
    metrics = snapshot.get("metrics") or {}
    return sum(
        int(metrics.get(key, 0) or 0)
        for key in ("commits", "prs_opened", "issues_created", "issues_completed")
    )


def code_weather(total: int) -> dict[str, str]:
    for ceiling, label, icon in WEATHER_LEVELS:
        if total <= ceiling:
            return {"label": label, "icon": icon}
    return {"label": "STORM", "icon": "🌩️"}


def dev_status(last_activity_at: str | None, now: datetime) -> dict[str, Any]:
    last = parse_timestamp(last_activity_at)
    if last is None:
        return {"label": "QUIET", "symbol": "○", "age_seconds": None}

    now_utc = now.astimezone(UTC)
    age = max(0, int((now_utc - last).total_seconds()))
    if age <= 3600:
        label, symbol = "BUILDING", "●"
    elif age <= 6 * 3600:
        label, symbol = "RECENTLY ACTIVE", "◐"
    elif age <= 24 * 3600:
        label, symbol = "OFFLINE", "○"
    else:
        label, symbol = "QUIET", "○"
    return {"label": label, "symbol": symbol, "age_seconds": age}


def relative_age(age_seconds: int | None) -> str:
    if age_seconds is None:
        return "no recent public activity"
    if age_seconds < 60:
        return "just now"
    minutes = age_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def calculate_streak(active_dates: Iterable[date], today: date) -> int:
    active = set(active_dates)
    streak = 0
    cursor = today
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def score_event(event: Mapping[str, Any]) -> int:
    event_type = str(event.get("type", ""))
    payload = event.get("payload") or {}

    if event_type == "PushEvent":
        return max(1, int(payload.get("size", 0) or 0)) * WEIGHTS["commit"]
    if event_type == "PullRequestEvent":
        action = payload.get("action")
        pr = payload.get("pull_request") or {}
        if action == "opened":
            return WEIGHTS["pr_opened"]
        if action == "closed" and pr.get("merged") is True:
            return WEIGHTS["pr_merged"]
        return 1
    if event_type == "IssuesEvent":
        action = payload.get("action")
        if action == "opened":
            return WEIGHTS["issue_opened"]
        if action == "closed":
            return WEIGHTS["issue_completed"]
        return 1
    if event_type == "ReleaseEvent":
        return WEIGHTS["release"]
    return 1


def repository_activity(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for event in events:
        repo = (event.get("repo") or {}).get("name")
        if not repo:
            continue
        entry = scores.setdefault(repo, {"repo": repo, "score": 0, "events": 0})
        entry["score"] += score_event(event)
        entry["events"] += 1

    return sorted(
        scores.values(),
        key=lambda item: (-int(item["score"]), -int(item["events"]), str(item["repo"])),
    )


def current_focus(events: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ranked = repository_activity(events)
    if not ranked:
        return None
    total_score = sum(int(item["score"]) for item in ranked)
    winner = dict(ranked[0])
    winner["share"] = round((int(winner["score"]) / max(1, total_score)) * 100)
    return winner


def latest_activity_at(
    snapshot: Mapping[str, Any] | None,
    events: Iterable[Mapping[str, Any]],
) -> str | None:
    candidates: list[str] = []
    if snapshot:
        for item in snapshot.get("activity") or []:
            value = item.get("at")
            if value:
                candidates.append(str(value))
    for event in events:
        value = event.get("created_at")
        if value:
            candidates.append(str(value))

    parsed = [(parse_timestamp(value), value) for value in candidates]
    parsed = [(dt, raw) for dt, raw in parsed if dt is not None]
    if not parsed:
        return None
    return max(parsed, key=lambda pair: pair[0])[1]
