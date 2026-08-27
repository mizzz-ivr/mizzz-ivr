from __future__ import annotations

import argparse
import fnmatch
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

MARKERS = {
    "live": ("<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->", "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->"),
    "today": ("<!-- DAILY-ACTIVITY:START -->", "<!-- DAILY-ACTIVITY:END -->"),
    "focus": ("<!-- PROFILE-SIGNAL:FOCUS:START -->", "<!-- PROFILE-SIGNAL:FOCUS:END -->"),
    "pulse": ("<!-- PROFILE-SIGNAL:PULSE:START -->", "<!-- PROFILE-SIGNAL:PULSE:END -->"),
    "building": ("<!-- PROFILE-SIGNAL:NOW-BUILDING:START -->", "<!-- PROFILE-SIGNAL:NOW-BUILDING:END -->"),
    "stream": ("<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->", "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->"),
    "recap": ("<!-- PROFILE-SIGNAL:RECAP:START -->", "<!-- PROFILE-SIGNAL:RECAP:END -->"),
}

STREAM_LABELS = {"PUSH": "PUSH", "PR": "PR", "ISSUE": "ISSUE", "RELEASE": "RELEASE"}


def load_ignore_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


def repository_is_ignored(repo: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(repo, pattern) for pattern in patterns)


def filter_state(state: dict[str, Any], patterns: list[str]) -> dict[str, Any]:
    if not patterns:
        return state
    result = dict(state)
    building = [
        dict(item)
        for item in state.get("now_building") or []
        if not repository_is_ignored(str(item.get("repo") or ""), patterns)
    ]
    stream = [
        dict(item)
        for item in state.get("activity_stream") or []
        if not repository_is_ignored(str(item.get("repo") or ""), patterns)
    ]
    focus = state.get("current_focus")
    if focus and repository_is_ignored(str(focus.get("repo") or ""), patterns):
        if building:
            candidate = dict(building[0])
            candidate["stack"] = []
            focus = candidate
        else:
            focus = None
    result["now_building"] = building[:3]
    result["activity_stream"] = stream[:4]
    result["current_focus"] = focus
    result["repository_ignore_patterns"] = patterns
    return result


def marker_pattern(start: str, end: str) -> re.Pattern[str]:
    return re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)


def replace_marker(text: str, name: str, block: str) -> str:
    start, end = MARKERS[name]
    if start not in text or end not in text:
        raise RuntimeError(f"README marker pair missing: {name}")
    return marker_pattern(start, end).sub(block, text, count=1)


def load_today_snapshot(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    try:
        day = date.fromisoformat(str(state.get("date") or ""))
    except ValueError:
        return {}
    path = root / "data" / "activity" / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_activity_snapshots(root: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted((root / "data" / "activity").glob("*/*/*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            date.fromisoformat(str(snapshot.get("date") or ""))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        snapshots.append(snapshot)
    return snapshots


def snapshot_activity_total(snapshot: dict[str, Any]) -> int:
    metrics = snapshot.get("metrics") or {}
    return sum(
        int(metrics.get(key, 0) or 0)
        for key in ("commits", "prs_opened", "issues_created", "issues_completed")
    )


def aggregate_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {"commits": 0, "prs_opened": 0, "issues_created": 0, "issues_completed": 0, "activity_total": 0}
    dates: list[date] = []
    active_days = 0
    for snapshot in snapshots:
        try:
            snapshot_date = date.fromisoformat(str(snapshot.get("date") or ""))
        except ValueError:
            continue
        dates.append(snapshot_date)
        source = snapshot.get("metrics") or {}
        for key in ("commits", "prs_opened", "issues_created", "issues_completed"):
            metrics[key] += int(source.get(key, 0) or 0)
        total = snapshot_activity_total(snapshot)
        metrics["activity_total"] += total
        if total > 0:
            active_days += 1
    return {
        "tracked_days": len(dates),
        "active_days": active_days,
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "metrics": metrics,
    }


def long_term_summary(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    snapshots = load_activity_snapshots(root)
    try:
        current_year = date.fromisoformat(str(state.get("date") or "")).year
    except ValueError:
        current_year = datetime.now().year
    yearly = [s for s in snapshots if str(s.get("date") or "").startswith(f"{current_year}-")]
    return {
        "year": current_year,
        "yearly": aggregate_snapshots(yearly),
        "lifetime": aggregate_snapshots(snapshots),
    }


def format_activity_time(value: str | None, timezone_name: str) -> str:
    if not value:
        return "--:--"
    try:
        timezone = ZoneInfo(timezone_name)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone)
    except (ValueError, TypeError):
        return "--:--"
    now = datetime.now(timezone)
    return parsed.strftime("%H:%M") if parsed.date() == now.date() else parsed.strftime("%m/%d %H:%M")


def render_live(state: dict[str, Any]) -> str:
    status = state.get("status") or {}
    weather = state.get("code_weather") or {}
    timezone = str(state.get("timezone") or "Asia/Tokyo")
    last_at = format_activity_time(status.get("last_activity_at"), timezone)
    return f'''{MARKERS["live"][0]}
## LIVE SIGNAL // Development status

<table>
  <tr>
    <td width="33%" align="center"><strong>{html.escape(str(status.get("symbol") or "○"))} {html.escape(str(status.get("label") or "QUIET"))}</strong><br/><sub>last public activity · {last_at} JST</sub></td>
    <td width="34%" align="center"><strong>{html.escape(str(weather.get("icon") or "🌙"))} {html.escape(str(weather.get("label") or "REST DAY"))}</strong><br/><sub>{int(state.get("activity_total", 0) or 0)} public actions today</sub></td>
    <td width="33%" align="center"><strong>🔥 {int(state.get("streak", 0) or 0)} DAY STREAK</strong><br/><sub>public GitHub activity</sub></td>
  </tr>
</table>
{MARKERS["live"][1]}'''


def render_today(snapshot: dict[str, Any], state: dict[str, Any]) -> str:
    metrics = snapshot.get("metrics") or {}
    date_text = html.escape(str(snapshot.get("date") or state.get("date") or ""))
    return f'''{MARKERS["today"][0]}
## TODAY // Activity overview

<p align="center"><sub>{date_text} JST · public GitHub activity</sub></p>

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS OPENED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_created", 0) or 0)}</strong><br/><sub>ISSUES CREATED</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE</sub></td>
  </tr>
</table>
{MARKERS["today"][1]}'''


def render_focus(state: dict[str, Any]) -> str:
    focus = state.get("current_focus")
    if not focus:
        body = '<p align="center"><sub>現在フォーカス中の公開Repositoryはありません。</sub></p>'
    else:
        repo_raw = str(focus.get("repo") or "unknown")
        repo = html.escape(repo_raw)
        repo_url = html.escape(f"https://github.com/{repo_raw}", quote=True)
        stack = " ".join(f"<code>{html.escape(str(item))}</code>" for item in focus.get("stack") or [])
        if not stack:
            stack = "<sub>technology data will refresh on the next full run</sub>"
        body = f'''<table>
  <tr>
    <td width="62%" valign="top"><strong><a href="{repo_url}">{repo}</a></strong><br/><sub>weighted activity {int(focus.get("share", 0) or 0)}% · score {int(focus.get("score", 0) or 0)} · {int(focus.get("events", 0) or 0)} events</sub></td>
    <td width="38%" valign="top"><strong>CURRENT STACK</strong><br/>{stack}</td>
  </tr>
</table>'''
    return f'''{MARKERS["focus"][0]}
## CURRENT FOCUS // What is moving now

{body}
{MARKERS["focus"][1]}'''


def render_pulse(state: dict[str, Any]) -> str:
    ci = state.get("ci_signal") or {}
    rate = ci.get("pass_rate")
    rate_text = "N/A" if rate is None else f"{int(rate)}%"
    return f'''{MARKERS["pulse"][0]}
## DEV PULSE // Last 7 days

<p align="center">
  <img src="./assets/dev-pulse.svg" width="100%" alt="7 day public GitHub development pulse" />
</p>

### QUALITY SIGNAL // Last 7 days

<table>
  <tr>
    <td width="25%" align="center"><strong>{html.escape(str(ci.get("label") or "NO SIGNAL"))}</strong><br/><sub>CI SIGNAL</sub></td>
    <td width="25%" align="center"><strong>{rate_text}</strong><br/><sub>PASS RATE</sub></td>
    <td width="25%" align="center"><strong>{int(ci.get("passed", 0) or 0)} / {int(ci.get("evaluated", 0) or 0)}</strong><br/><sub>PASSED / EVALUATED</sub></td>
    <td width="25%" align="center"><strong>{int(ci.get("repos_with_signal", 0) or 0)}</strong><br/><sub>REPOS WITH CI</sub></td>
  </tr>
</table>
{MARKERS["pulse"][1]}'''


def render_building(state: dict[str, Any]) -> str:
    repos = list(state.get("now_building") or [])
    if not repos:
        content = '<p align="center"><sub>現在アクティブな公開Repositoryはありません。</sub></p>'
    else:
        cells: list[str] = []
        for index, item in enumerate(repos[:3], 1):
            repo_raw = str(item.get("repo") or "unknown")
            repo = html.escape(repo_raw)
            url = html.escape(f"https://github.com/{repo_raw}", quote=True)
            health = item.get("health") or {}
            ci = item.get("ci") or {}
            pass_rate = ci.get("pass_rate")
            ci_text = "CI N/A" if pass_rate is None else f"CI pass rate {pass_rate}%"
            last_at = format_activity_time(item.get("last_activity_at"), str(state.get("timezone") or "Asia/Tokyo"))
            cells.append(
                f'<td width="33%" valign="top"><strong>{index:02d} · <a href="{url}">{repo}</a></strong><br/>'
                f'<sub>{int(item.get("share", 0) or 0)}% weighted · {html.escape(str(health.get("label") or "ACTIVE"))} · {html.escape(ci_text)}<br/>last activity · {last_at} JST</sub></td>'
            )
        while len(cells) < 3:
            cells.append('<td width="33%" valign="top"><sub>—</sub></td>')
        content = f'<table><tr>{"".join(cells)}</tr></table>'
    return f'''{MARKERS["building"][0]}
## NOW BUILDING // Active repositories

{content}
{MARKERS["building"][1]}'''


def render_stream(state: dict[str, Any]) -> str:
    items = list(state.get("activity_stream") or [])
    if not items:
        rows = '<tr><td colspan="3" align="center"><sub>最近の公開アクティビティはありません。</sub></td></tr>'
    else:
        rendered: list[str] = []
        timezone = str(state.get("timezone") or "Asia/Tokyo")
        for item in items[:4]:
            repo_raw = str(item.get("repo") or "unknown")
            repo = html.escape(repo_raw)
            repo_url = html.escape(f"https://github.com/{repo_raw}", quote=True)
            url = html.escape(str(item.get("url") or repo_url), quote=True)
            title = html.escape(str(item.get("title") or "public activity"))
            label = html.escape(STREAM_LABELS.get(str(item.get("label")), str(item.get("label") or "ACTIVITY")))
            at = format_activity_time(item.get("at"), timezone)
            rendered.append(
                f'<tr><td width="10%"><code>{at}</code></td><td width="14%"><code>{label}</code></td>'
                f'<td><strong><a href="{repo_url}">{repo}</a></strong> — <a href="{url}">{title}</a></td></tr>'
            )
        rows = "\n    ".join(rendered)
    return f'''{MARKERS["stream"][0]}
## ACTIVITY STREAM // Latest public signals

<table>
  <tbody>
    {rows}
  </tbody>
</table>
{MARKERS["stream"][1]}'''


def summary_table(metrics: dict[str, Any], *, include_active_days: int | None = None) -> str:
    cells = []
    if include_active_days is not None:
        cells.append(f'<td width="20%" align="center"><strong>{include_active_days}</strong><br/><sub>ACTIVE DAYS</sub></td>')
        width = "20%"
    else:
        width = "25%"
    cells.extend([
        f'<td width="{width}" align="center"><strong>{int(metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS</sub></td>',
        f'<td width="{width}" align="center"><strong>{int(metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS</sub></td>',
        f'<td width="{width}" align="center"><strong>{int(metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE</sub></td>',
        f'<td width="{width}" align="center"><strong>{int(metrics.get("activity_total", 0) or 0)}</strong><br/><sub>ACTIVITY</sub></td>',
    ])
    return '<table><tr>' + ''.join(cells) + '</tr></table>'


def render_recap(state: dict[str, Any], long_term: dict[str, Any]) -> str:
    recap = state.get("dev_recap") or {}
    weekly = recap.get("weekly") or {}
    monthly = recap.get("monthly") or {}
    weekly_metrics = weekly.get("metrics") or {}
    monthly_metrics = monthly.get("metrics") or {}
    yearly = long_term.get("yearly") or {}
    lifetime = long_term.get("lifetime") or {}
    lifetime_since = lifetime.get("first_date") or recap.get("tracked_from") or "not tracked yet"
    return f'''{MARKERS["recap"][0]}
## DEV RECAP // Tracked history

<table>
  <tr>
    <td width="25%" align="center"><strong>🔥 {int(state.get("streak", 0) or 0)}</strong><br/><sub>DAY STREAK</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("commits", 0) or 0)}</strong><br/><sub>COMMITS · THIS WEEK</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PRS · THIS WEEK</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>ISSUES DONE · THIS WEEK</sub></td>
  </tr>
</table>

<details>
<summary><strong>MONTHLY SUMMARY</strong></summary>
<br/>
{summary_table(monthly_metrics)}
</details>

<details>
<summary><strong>YEARLY SUMMARY // {int(long_term.get("year") or 0)}</strong></summary>
<br/>
{summary_table(yearly.get("metrics") or {}, include_active_days=int(yearly.get("active_days", 0) or 0))}
<p><sub>{int(yearly.get("tracked_days", 0) or 0)} tracked days in {int(long_term.get("year") or 0)}.</sub></p>
</details>

<details>
<summary><strong>LIFETIME SUMMARY // Tracked history</strong></summary>
<br/>
{summary_table(lifetime.get("metrics") or {}, include_active_days=int(lifetime.get("active_days", 0) or 0))}
<p><sub>Profile Signal tracked lifetime · tracked since {html.escape(str(lifetime_since))} · {int(lifetime.get("tracked_days", 0) or 0)} tracked days. GitHub account lifetime totalsではありません。</sub></p>
</details>
{MARKERS["recap"][1]}'''


def customize(root: Path, readme_path: Path, state_path: Path, ignore_path: Path) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    patterns = load_ignore_patterns(ignore_path)
    state = filter_state(state, patterns)
    snapshot = load_today_snapshot(root, state)
    long_term = long_term_summary(root, state)
    state["tracked_summary"] = long_term
    text = readme_path.read_text(encoding="utf-8")
    for name, block in (
        ("live", render_live(state)),
        ("today", render_today(snapshot, state)),
        ("focus", render_focus(state)),
        ("pulse", render_pulse(state)),
        ("building", render_building(state)),
        ("stream", render_stream(state)),
        ("recap", render_recap(state, long_term)),
    ):
        text = replace_marker(text, name, block)
    readme_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Customize Profile Signal consumer output")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--state", type=Path, default=Path("data/profile-signal-state.json"))
    parser.add_argument("--ignore", type=Path, default=Path(".profile-signalignore"))
    args = parser.parse_args()
    root = args.root.resolve()
    readme = args.readme if args.readme.is_absolute() else root / args.readme
    state = args.state if args.state.is_absolute() else root / args.state
    ignore = args.ignore if args.ignore.is_absolute() else root / args.ignore
    customized = customize(root, readme, state, ignore)
    tracked = customized.get("tracked_summary") or {}
    print(
        "Customized Profile Signal:",
        f"focus={(customized.get('current_focus') or {}).get('repo', 'none')}",
        f"ignored={len(customized.get('repository_ignore_patterns') or [])}",
        f"tracked_days={(tracked.get('lifetime') or {}).get('tracked_days', 0)}",
    )


if __name__ == "__main__":
    main()
