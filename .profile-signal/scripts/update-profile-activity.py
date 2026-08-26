#!/usr/bin/env python3
"""Update the profile README with public GitHub activity for the current JST day.

The script intentionally uses unauthenticated GitHub Search API requests so the
published profile can never accidentally expose private repository metadata.
It refreshes today and yesterday, persists one JSON snapshot per day, renders a
small seven-day SVG, and only replaces the README marker block.
"""

from __future__ import annotations

import html
import json
import os
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LOGIN = os.getenv("GITHUB_LOGIN", "mizzz-ivr")
TZ_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = f"{LOGIN}-profile-activity"

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
LOG_ROOT = ROOT / "data" / "activity"
CHART_PATH = ROOT / "assets" / "activity-7d.svg"

START_MARKER = "<!-- DAILY-ACTIVITY:START -->"
END_MARKER = "<!-- DAILY-ACTIVITY:END -->"
NOW_HEADING = "## NOW // What I build"

MAX_ACTIVITY_ITEMS = 5
SEARCH_PER_PAGE = 100


def zulu(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_window(day: date) -> str:
    start_local = datetime.combine(day, time.min, TZ)
    end_local = start_local + timedelta(days=1) - timedelta(seconds=1)
    return f"{zulu(start_local)}..{zulu(end_local)}"


def request_json(path: str, params: dict[str, str | int]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}{path}?{query}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }

    request = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            retryable = exc.code in {403, 429, 500, 502, 503, 504}
            if retryable and attempt < 2:
                retry_after = exc.headers.get("Retry-After")
                reset = exc.headers.get("X-RateLimit-Reset")
                delay = 2 + attempt * 2

                if retry_after and retry_after.isdigit():
                    delay = max(delay, int(retry_after))
                elif reset and reset.isdigit():
                    delay = max(
                        delay,
                        min(65, int(reset) - int(time_module.time()) + 1),
                    )

                time_module.sleep(max(1, delay))
                continue

            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API request failed ({exc.code}) for {path}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt < 2:
                time_module.sleep(2 + attempt * 2)
                continue
            raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc

    raise RuntimeError(f"GitHub API request failed for {path}")


def search(path: str, query: str, sort: str) -> dict[str, Any]:
    return request_json(
        path,
        {
            "q": query,
            "sort": sort,
            "order": "desc",
            "per_page": SEARCH_PER_PAGE,
        },
    )


def repository_from_api_url(url: str) -> str:
    prefix = "https://api.github.com/repos/"
    return url.removeprefix(prefix) if url.startswith(prefix) else "unknown"


def first_line(value: str, limit: int = 96) -> str:
    text = " ".join((value or "").splitlines()).strip()
    return text[:limit] if text else "Untitled activity"


def collect_day(day: date) -> dict[str, Any]:
    window = utc_window(day)

    commits = search(
        "/search/commits",
        f"author:{LOGIN} author-date:{window}",
        "author-date",
    )
    prs = search(
        "/search/issues",
        f"is:pr author:{LOGIN} created:{window}",
        "created",
    )
    issues_created = search(
        "/search/issues",
        f"is:issue author:{LOGIN} created:{window}",
        "created",
    )
    issues_completed = search(
        "/search/issues",
        f"is:issue author:{LOGIN} is:closed reason:completed closed:{window}",
        "updated",
    )

    activity: list[dict[str, str]] = []

    for item in commits.get("items", []):
        repository = item.get("repository") or {}
        if repository.get("private") is True:
            continue

        commit = item.get("commit") or {}
        author = commit.get("author") or commit.get("committer") or {}
        activity.append(
            {
                "type": "commit",
                "repo": repository.get("full_name", "unknown"),
                "title": first_line(commit.get("message", "")),
                "url": item.get("html_url", ""),
                "at": author.get("date", ""),
            }
        )

    for item in prs.get("items", []):
        activity.append(
            {
                "type": "pr",
                "repo": repository_from_api_url(item.get("repository_url", "")),
                "title": first_line(
                    f"PR #{item.get('number', '?')} {item.get('title', '')}"
                ),
                "url": item.get("html_url", ""),
                "at": item.get("created_at", ""),
            }
        )

    for item in issues_created.get("items", []):
        activity.append(
            {
                "type": "issue",
                "repo": repository_from_api_url(item.get("repository_url", "")),
                "title": first_line(
                    f"Issue #{item.get('number', '?')} {item.get('title', '')}"
                ),
                "url": item.get("html_url", ""),
                "at": item.get("created_at", ""),
            }
        )

    for item in issues_completed.get("items", []):
        activity.append(
            {
                "type": "done",
                "repo": repository_from_api_url(item.get("repository_url", "")),
                "title": first_line(
                    f"Issue #{item.get('number', '?')} {item.get('title', '')}"
                ),
                "url": item.get("html_url", ""),
                "at": item.get("closed_at", "") or item.get("updated_at", ""),
            }
        )

    activity.sort(key=lambda item: item.get("at", ""), reverse=True)

    return {
        "schema_version": 1,
        "date": day.isoformat(),
        "timezone": TZ_NAME,
        "scope": "public",
        "github_login": LOGIN,
        "metrics": {
            "commits": int(commits.get("total_count", 0)),
            "prs_opened": int(prs.get("total_count", 0)),
            "issues_created": int(issues_created.get("total_count", 0)),
            "issues_completed": int(issues_completed.get("total_count", 0)),
        },
        "activity": activity[:MAX_ACTIVITY_ITEMS],
    }


def snapshot_path(day: date) -> Path:
    return LOG_ROOT / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.json"


def write_snapshot(day: date, snapshot: dict[str, Any], now: datetime) -> dict[str, Any]:
    path = snapshot_path(day)
    old: dict[str, Any] | None = None

    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            old = None

    comparable_old = None
    if old is not None:
        comparable_old = {key: value for key, value in old.items() if key != "generated_at"}

    if comparable_old == snapshot:
        return old or snapshot

    payload = dict(snapshot)
    payload["generated_at"] = now.isoformat(timespec="seconds")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def load_snapshot(day: date) -> dict[str, Any] | None:
    path = snapshot_path(day)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def metric(snapshot: dict[str, Any] | None, key: str) -> int:
    if not snapshot:
        return 0
    return int((snapshot.get("metrics") or {}).get(key, 0))


def activity_total(snapshot: dict[str, Any] | None) -> int:
    return sum(
        metric(snapshot, key)
        for key in ("commits", "prs_opened", "issues_created", "issues_completed")
    )


def render_chart(today: date) -> str:
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    snapshots = [load_snapshot(day) for day in days]
    totals = [activity_total(snapshot) for snapshot in snapshots]
    maximum = max(1, max(totals, default=0))

    width = 880
    height = 184
    chart_top = 48
    chart_bottom = 142
    chart_height = chart_bottom - chart_top
    left = 54
    step = 112
    bar_width = 62

    bars: list[str] = []
    for index, (day, total) in enumerate(zip(days, totals, strict=True)):
        x = left + index * step
        bar_height = 0 if total == 0 else max(4, round(chart_height * total / maximum))
        y = chart_bottom - bar_height
        value_y = max(35, y - 8)
        label = day.strftime("%m/%d")

        bars.append(
            f'<rect class="bar" x="{x}" y="{y}" width="{bar_width}" '
            f'height="{bar_height}" rx="8" />'
        )
        bars.append(
            f'<text class="value" x="{x + bar_width / 2:.1f}" y="{value_y}" '
            f'text-anchor="middle">{total}</text>'
        )
        bars.append(
            f'<text class="label" x="{x + bar_width / 2:.1f}" y="166" '
            f'text-anchor="middle">{label}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">7 day public GitHub activity</title>
  <desc id="desc">Daily totals for commits, opened pull requests, created issues and completed issues.</desc>
  <style>
    .title {{ fill: #24292f; font: 600 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: .08em; }}
    .label {{ fill: #57606a; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .value {{ fill: #57606a; font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .grid {{ stroke: #d0d7de; stroke-width: 1; }}
    .bar {{ fill: #8b5cf6; }}
    @media (prefers-color-scheme: dark) {{
      .title {{ fill: #f0f6fc; }}
      .label, .value {{ fill: #8c959f; }}
      .grid {{ stroke: #30363d; }}
      .bar {{ fill: #a78bfa; }}
    }}
  </style>
  <text class="title" x="24" y="25">PUBLIC ACTIVITY · 7D</text>
  <line class="grid" x1="24" y1="{chart_bottom + 0.5}" x2="856" y2="{chart_bottom + 0.5}" />
  {''.join(bars)}
</svg>
'''


def write_chart(today: date) -> None:
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_chart(today)
    if CHART_PATH.exists() and CHART_PATH.read_text(encoding="utf-8") == rendered:
        return
    CHART_PATH.write_text(rendered, encoding="utf-8")


def activity_label(event_type: str) -> str:
    return {
        "commit": "COMMIT",
        "pr": "PR",
        "issue": "ISSUE",
        "done": "DONE",
    }.get(event_type, "ACTIVITY")


def render_readme_block(snapshot: dict[str, Any]) -> str:
    metrics = snapshot.get("metrics") or {}
    events = snapshot.get("activity") or []

    if events:
        items: list[str] = []
        for event in events:
            repo = html.escape(str(event.get("repo", "unknown")))
            title = html.escape(str(event.get("title", "Untitled activity")))
            url = html.escape(str(event.get("url", "")), quote=True)
            repo_url = html.escape(f"https://github.com/{event.get('repo', '')}", quote=True)
            label = html.escape(activity_label(str(event.get("type", ""))))
            title_markup = f'<a href="{url}">{title}</a>' if url else title
            items.append(
                f'  <li><code>{label}</code> '
                f'<strong><a href="{repo_url}">{repo}</a></strong> — {title_markup}</li>'
            )
        activity_html = "\n".join(items)
    else:
        activity_html = "  <li><sub>No public activity recorded yet today.</sub></li>"

    return f'''{START_MARKER}
## TODAY // Activity overview

<p align="center">
  <sub>{html.escape(snapshot["date"])} JST · public GitHub activity</sub>
</p>

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(metrics.get("commits", 0))}</strong><br/><sub>COMMITS</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("prs_opened", 0))}</strong><br/><sub>PRS OPENED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_created", 0))}</strong><br/><sub>ISSUES CREATED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_completed", 0))}</strong><br/><sub>ISSUES DONE</sub></td>
  </tr>
</table>

<strong>Today&apos;s signal</strong>

<ul>
{activity_html}
</ul>

<p align="center">
  <img src="./assets/activity-7d.svg" width="100%" alt="7 day public GitHub activity trend" />
</p>

<p align="center">
  <sub>Auto-updated by GitHub Actions · Issue done = authored issue closed as completed</sub>
</p>
{END_MARKER}'''


def update_readme(snapshot: dict[str, Any]) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    block = render_readme_block(snapshot)

    if START_MARKER in text and END_MARKER in text:
        start = text.index(START_MARKER)
        end = text.index(END_MARKER, start) + len(END_MARKER)
        updated = text[:start] + block + text[end:]
    elif NOW_HEADING in text:
        updated = text.replace(
            NOW_HEADING,
            f"{block}\n\n---\n\n{NOW_HEADING}",
            1,
        )
    else:
        raise RuntimeError(
            f"Could not find README markers or fallback heading: {NOW_HEADING}"
        )

    if updated != text:
        README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    now = datetime.now(TZ)
    today = now.date()
    yesterday = today - timedelta(days=1)

    # Exactly eight Search API requests: four for today, four for yesterday.
    # This stays below the unauthenticated Search API's per-minute ceiling.
    today_snapshot = write_snapshot(today, collect_day(today), now)
    write_snapshot(yesterday, collect_day(yesterday), now)

    write_chart(today)
    update_readme(today_snapshot)

    print(
        "Profile activity refreshed:",
        today_snapshot["date"],
        today_snapshot["metrics"],
    )


if __name__ == "__main__":
    main()
