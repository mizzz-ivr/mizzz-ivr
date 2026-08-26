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

STREAM_EVENT_TYPES = {
    "PushEvent",
    "PullRequestEvent",
    "IssuesEvent",
    "ReleaseEvent",
    "CreateEvent",
}


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

        entry = scores.setdefault(
            str(repo),
            {
                "repo": str(repo),
                "score": 0,
                "events": 0,
                "last_activity_at": None,
            },
        )
        entry["score"] += score_event(event)
        entry["events"] += 1

        created_at = event.get("created_at")
        if created_at:
            current = entry.get("last_activity_at")
            if current is None or str(created_at) > str(current):
                entry["last_activity_at"] = str(created_at)

    return sorted(
        scores.values(),
        key=lambda item: (-int(item["score"]), -int(item["events"]), str(item["repo"])),
    )


def ranked_repositories(
    events: Iterable[Mapping[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    ranked = repository_activity(events)
    total_score = sum(int(item["score"]) for item in ranked)
    result: list[dict[str, Any]] = []
    for item in ranked[: max(0, limit)]:
        entry = dict(item)
        entry["share"] = round((int(entry["score"]) / max(1, total_score)) * 100)
        result.append(entry)
    return result


def current_focus(events: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ranked = ranked_repositories(events, limit=1)
    return ranked[0] if ranked else None


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


def _event_number(payload: Mapping[str, Any], key: str) -> str:
    item = payload.get(key) or {}
    number = item.get("number") or payload.get("number")
    return f"#{number}" if number is not None else ""


def summarize_event(event: Mapping[str, Any]) -> dict[str, str] | None:
    event_type = str(event.get("type", ""))
    if event_type not in STREAM_EVENT_TYPES:
        return None

    repo = str((event.get("repo") or {}).get("name") or "")
    if not repo:
        return None

    payload = event.get("payload") or {}
    created_at = str(event.get("created_at") or "")
    repo_url = f"https://github.com/{repo}"

    if event_type == "PushEvent":
        size = max(1, int(payload.get("size", 0) or 0))
        ref = str(payload.get("ref") or "").removeprefix("refs/heads/")
        suffix = f" to {ref}" if ref else ""
        return {
            "label": "PUSH",
            "repo": repo,
            "title": f"{size} commit{'s' if size != 1 else ''} pushed{suffix}",
            "url": f"{repo_url}/commits",
            "at": created_at,
        }

    if event_type == "PullRequestEvent":
        action = str(payload.get("action") or "updated")
        pr = payload.get("pull_request") or {}
        number = _event_number(payload, "pull_request")
        if action == "closed" and pr.get("merged") is True:
            verb = "Merged PR"
        elif action == "opened":
            verb = "Opened PR"
        elif action == "reopened":
            verb = "Reopened PR"
        elif action == "closed":
            verb = "Closed PR"
        else:
            verb = f"PR {action}"
        return {
            "label": "PR",
            "repo": repo,
            "title": f"{verb} {number}".strip(),
            "url": str(pr.get("html_url") or repo_url),
            "at": created_at,
        }

    if event_type == "IssuesEvent":
        action = str(payload.get("action") or "updated")
        issue = payload.get("issue") or {}
        number = _event_number(payload, "issue")
        verb = {
            "opened": "Opened issue",
            "closed": "Closed issue",
            "reopened": "Reopened issue",
        }.get(action, f"Issue {action}")
        return {
            "label": "ISSUE",
            "repo": repo,
            "title": f"{verb} {number}".strip(),
            "url": str(issue.get("html_url") or repo_url),
            "at": created_at,
        }

    if event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        name = release.get("name") or release.get("tag_name") or "release"
        return {
            "label": "RELEASE",
            "repo": repo,
            "title": f"Published {name}",
            "url": str(release.get("html_url") or f"{repo_url}/releases"),
            "at": created_at,
        }

    ref_type = str(payload.get("ref_type") or "ref")
    ref = str(payload.get("ref") or "")
    title = f"Created {ref_type} {ref}".strip()
    return {
        "label": "CREATE",
        "repo": repo,
        "title": title,
        "url": repo_url,
        "at": created_at,
    }


def activity_stream(
    events: Iterable[Mapping[str, Any]],
    limit: int = 4,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for event in events:
        summary = summarize_event(event)
        if summary is not None:
            items.append(summary)

    items.sort(key=lambda item: item.get("at", ""), reverse=True)
    return items[: max(0, limit)]
