#!/usr/bin/env python3
"""Generate tracked weekly/monthly history and the DEV RECAP widget."""

from __future__ import annotations

import html
import json
import os
import subprocess
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

LOGIN = os.getenv("GITHUB_LOGIN", "mizzz-ivr")
TZ_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
LOG_ROOT = ROOT / "data" / "activity"
WEEKLY_ROOT = ROOT / "data" / "weekly"
MONTHLY_ROOT = ROOT / "data" / "monthly"
STATE_PATH = ROOT / "data" / "profile-signal-state.json"

RECAP_START = "<!-- PROFILE-SIGNAL:RECAP:START -->"
RECAP_END = "<!-- PROFILE-SIGNAL:RECAP:END -->"
BUILD_LOGIC_HEADING = "## BUILD LOGIC // How I work"

METRIC_KEYS = ("commits", "prs_opened", "issues_created", "issues_completed")


def snapshot_total(snapshot: Mapping[str, Any] | None) -> int:
    if not snapshot:
        return 0
    metrics = snapshot.get("metrics") or {}
    return sum(int(metrics.get(key, 0) or 0) for key in METRIC_KEYS)


def load_all_snapshots() -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(LOG_ROOT.glob("*/*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            date.fromisoformat(str(payload.get("date")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            snapshots.append(payload)
    snapshots.sort(key=lambda item: str(item.get("date", "")))
    return snapshots


def aggregate_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
    start: date,
    end: date,
    period: str,
) -> dict[str, Any]:
    selected: list[Mapping[str, Any]] = []
    for snapshot in snapshots:
        try:
            day = date.fromisoformat(str(snapshot.get("date")))
        except (TypeError, ValueError):
            continue
        if start <= day <= end:
            selected.append(snapshot)

    metrics = {key: 0 for key in METRIC_KEYS}
    active_days = 0
    tracked_dates: list[str] = []

    for snapshot in selected:
        raw_metrics = snapshot.get("metrics") or {}
        for key in METRIC_KEYS:
            metrics[key] += int(raw_metrics.get(key, 0) or 0)
        if snapshot_total(snapshot) > 0:
            active_days += 1
        tracked_dates.append(str(snapshot.get("date")))

    metrics["activity_total"] = sum(metrics[key] for key in METRIC_KEYS)
    return {
        "schema_version": 1,
        "period": period,
        "timezone": TZ_NAME,
        "scope": "public",
        "github_login": LOGIN,
        "coverage": {
            "start_date": tracked_dates[0] if tracked_dates else None,
            "end_date": tracked_dates[-1] if tracked_dates else None,
            "tracked_days": len(tracked_dates),
            "active_days": active_days,
        },
        "metrics": metrics,
    }


def longest_streak(active_dates: Iterable[date]) -> tuple[int, date | None]:
    ordered = sorted(set(active_dates))
    best = 0
    current = 0
    previous: date | None = None
    best_end: date | None = None
    for day in ordered:
        current = current + 1 if previous is not None and day == previous + timedelta(days=1) else 1
        if current > best:
            best = current
            best_end = day
        previous = day
    return best, best_end


def achievement_engine(snapshots: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[tuple[date, Mapping[str, Any]]] = []
    for snapshot in snapshots:
        try:
            day = date.fromisoformat(str(snapshot.get("date")))
        except (TypeError, ValueError):
            continue
        ordered.append((day, snapshot))
    ordered.sort(key=lambda pair: pair[0])

    cumulative = {key: 0 for key in METRIC_KEYS}
    cumulative_activity = 0
    active_dates: list[date] = []
    unlocked: dict[str, dict[str, Any]] = {}

    definitions = (
        ("first-signal", "FIRST SIGNAL", "📡", lambda: cumulative_activity >= 1),
        ("100-commits", "100+ COMMITS", "🏗️", lambda: cumulative["commits"] >= 100),
        ("10-prs", "10+ PRS", "🚢", lambda: cumulative["prs_opened"] >= 10),
        ("10-issues-done", "10+ ISSUES DONE", "✅", lambda: cumulative["issues_completed"] >= 10),
        ("1k-activity", "1K ACTIVITY", "⚡", lambda: cumulative_activity >= 1000),
    )

    for day, snapshot in ordered:
        metrics = snapshot.get("metrics") or {}
        for key in METRIC_KEYS:
            cumulative[key] += int(metrics.get(key, 0) or 0)
        total = snapshot_total(snapshot)
        cumulative_activity += total
        if total > 0:
            active_dates.append(day)

        for key, label, icon, condition in definitions:
            if key not in unlocked and condition():
                unlocked[key] = {
                    "key": key,
                    "label": label,
                    "icon": icon,
                    "unlocked_on": day.isoformat(),
                }

        streak, streak_end = longest_streak(active_dates)
        if streak >= 7 and "7-day-streak" not in unlocked:
            unlocked["7-day-streak"] = {
                "key": "7-day-streak",
                "label": "7 DAY STREAK",
                "icon": "🔥",
                "unlocked_on": (streak_end or day).isoformat(),
            }

    order = ("first-signal", "100-commits", "10-prs", "10-issues-done", "7-day-streak", "1k-activity")
    return [unlocked[key] for key in order if key in unlocked]


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    return start, day.replace(day=monthrange(day.year, day.month)[1])


def previous_month(day: date) -> date:
    return (day.replace(day=1) - timedelta(days=1)).replace(day=1)


def report_path(root: Path, period: str) -> Path:
    return root / f"{period}.json"


def write_report(path: Path, report: dict[str, Any], now: datetime) -> dict[str, Any]:
    old: dict[str, Any] | None = None
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old = None

    old_semantic = {k: v for k, v in (old or {}).items() if k != "generated_at"}
    if old is not None and old_semantic == report:
        return old

    payload = dict(report)
    payload["generated_at"] = now.isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def refresh_reports(
    snapshots: list[dict[str, Any]],
    today: date,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_week: dict[str, Any] | None = None
    for anchor in (today, today - timedelta(days=7)):
        start, end = week_bounds(anchor)
        iso_year, iso_week, _ = anchor.isocalendar()
        period = f"{iso_year}-W{iso_week:02d}"
        report = aggregate_snapshots(snapshots, start, end, period)
        saved = write_report(report_path(WEEKLY_ROOT, period), report, now)
        if anchor == today:
            current_week = saved

    current_month: dict[str, Any] | None = None
    for anchor in (today, previous_month(today)):
        start, end = month_bounds(anchor)
        period = anchor.strftime("%Y-%m")
        report = aggregate_snapshots(snapshots, start, end, period)
        saved = write_report(report_path(MONTHLY_ROOT, period), report, now)
        if anchor.year == today.year and anchor.month == today.month:
            current_month = saved

    if current_week is None or current_month is None:
        raise RuntimeError("Could not build current history reports")
    return current_week, current_month


def read_head_json(path: str) -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        return payload if isinstance(payload, dict) else None
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None


def semantic_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "generated_at"}


def write_state(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    previous = read_head_json("data/profile-signal-state.json")
    payload = dict(state)
    if previous is not None and semantic_state(previous) == semantic_state(payload):
        payload["generated_at"] = previous.get("generated_at", now.isoformat(timespec="seconds"))
    else:
        payload["generated_at"] = now.isoformat(timespec="seconds")
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def history_state(
    state: dict[str, Any],
    snapshots: list[dict[str, Any]],
    weekly: dict[str, Any],
    monthly: dict[str, Any],
) -> dict[str, Any]:
    active_dates: list[date] = []
    for snapshot in snapshots:
        if snapshot_total(snapshot) <= 0:
            continue
        try:
            active_dates.append(date.fromisoformat(str(snapshot.get("date"))))
        except (TypeError, ValueError):
            continue

    streak, _ = longest_streak(active_dates)
    tracked_from = str(snapshots[0].get("date")) if snapshots else None
    result = dict(state)
    result["schema_version"] = 4
    result["dev_recap"] = {
        "tracked_from": tracked_from,
        "tracked_days": len(snapshots),
        "active_days": len(set(active_dates)),
        "longest_streak": streak,
        "weekly": weekly,
        "monthly": monthly,
        "achievements": achievement_engine(snapshots),
    }
    return result


def render_recap(state: Mapping[str, Any]) -> str:
    recap = state.get("dev_recap") or {}
    weekly = recap.get("weekly") or {}
    monthly = recap.get("monthly") or {}
    week_metrics = weekly.get("metrics") or {}
    month_metrics = monthly.get("metrics") or {}
    week_coverage = weekly.get("coverage") or {}
    month_coverage = monthly.get("coverage") or {}
    achievements = list(recap.get("achievements") or [])
    tracked_from = html.escape(str(recap.get("tracked_from") or "not available"))

    achievement_markup = " ".join(
        f"<code>{html.escape(str(item.get('icon', '🏅')))} {html.escape(str(item.get('label', 'ACHIEVEMENT')))}</code>"
        for item in achievements
    )
    if not achievement_markup:
        achievement_markup = "<sub>No tracked achievements unlocked yet.</sub>"

    ci = state.get("ci_signal") or {}
    ci_rate = ci.get("pass_rate")
    ci_text = "CI · no evaluated signal"
    if ci_rate is not None:
        ci_text = (
            f"CI · {int(ci_rate)}% · "
            f"{int(ci.get('passed', 0) or 0)}/{int(ci.get('evaluated', 0) or 0)} passed"
        )

    return f'''{RECAP_START}
## DEV RECAP // Tracked history

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(week_coverage.get("active_days", 0) or 0)}</strong><br/><sub>ACTIVE DAYS · THIS WEEK</sub></td>
    <td width="25%" align="center"><strong>{int(week_metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS · THIS WEEK</sub></td>
    <td width="25%" align="center"><strong>{int(week_metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS OPENED · THIS WEEK</sub></td>
    <td width="25%" align="center"><strong>{int(week_metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE · THIS WEEK</sub></td>
  </tr>
</table>

<p align="center"><sub>{html.escape(str(weekly.get("period", "")))} · tracked since {tracked_from} · {html.escape(ci_text)}</sub></p>

<details>
<summary><strong>MONTHLY BUILD REPORT + ACHIEVEMENTS</strong></summary>

<br/>

<table>
  <tr>
    <td width="20%" align="center"><strong>{int(month_coverage.get("active_days", 0) or 0)}</strong><br/><sub>ACTIVE DAYS</sub></td>
    <td width="20%" align="center"><strong>{int(month_metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS</sub></td>
    <td width="20%" align="center"><strong>{int(month_metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS OPENED</sub></td>
    <td width="20%" align="center"><strong>{int(month_metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE</sub></td>
    <td width="20%" align="center"><strong>{int(month_metrics.get("activity_total", 0) or 0)}</strong><br/><sub>ACTIVITY</sub></td>
  </tr>
</table>

<p><strong>{html.escape(str(monthly.get("period", "")))} // tracked report</strong></p>

<p>{achievement_markup}</p>

<p><sub>Achievements and reports are based only on Profile Signal tracked public history, not lifetime GitHub totals.</sub></p>
</details>
{RECAP_END}'''


def replace_marker_block(text: str, block: str) -> str:
    if RECAP_START in text and RECAP_END in text:
        start = text.index(RECAP_START)
        end = text.index(RECAP_END, start) + len(RECAP_END)
        return text[:start] + block + text[end:]

    if BUILD_LOGIC_HEADING not in text:
        raise RuntimeError("Could not find BUILD LOGIC heading for DEV RECAP insertion")
    return text.replace(
        BUILD_LOGIC_HEADING,
        f"{block}\n\n---\n\n{BUILD_LOGIC_HEADING}",
        1,
    )


def update_readme(state: Mapping[str, Any]) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    README_PATH.write_text(replace_marker_block(text, render_recap(state)), encoding="utf-8")


def main() -> None:
    now = datetime.now(TZ)
    snapshots = load_all_snapshots()
    if not snapshots:
        raise RuntimeError("No tracked daily activity snapshots are available")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("Profile Signal state is not a JSON object")

    weekly, monthly = refresh_reports(snapshots, now.date(), now)
    state = write_state(history_state(state, snapshots, weekly, monthly), now)
    update_readme(state)

    recap = state["dev_recap"]
    print(
        "Profile Signal history refreshed:",
        weekly.get("period"),
        monthly.get("period"),
        f"tracked_days={recap.get('tracked_days')}",
        f"achievements={len(recap.get('achievements') or [])}",
    )


if __name__ == "__main__":
    main()
