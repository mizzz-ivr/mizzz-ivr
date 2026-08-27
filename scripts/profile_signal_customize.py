from __future__ import annotations

import argparse
import fnmatch
import html
import json
import re
from datetime import datetime
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

STATUS_LABELS = {
    "BUILDING": "開発中",
    "ACTIVE": "稼働中",
    "QUIET": "待機中",
    "SHIPPING": "リリース中",
}
WEATHER_LABELS = {
    "STORM": "高稼働",
    "FLOW": "集中",
    "BREEZY": "通常",
    "REST DAY": "休息",
}
HEALTH_LABELS = {
    "HEALTHY": "安定",
    "WATCH": "注意",
    "ATTENTION": "要確認",
    "ACTIVE": "稼働中",
}
STREAM_LABELS = {
    "PUSH": "PUSH",
    "PR": "PR",
    "ISSUE": "ISSUE",
    "RELEASE": "RELEASE",
}


def load_ignore_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


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
    date_text = str(state.get("date") or "")
    try:
        day = datetime.fromisoformat(date_text).date()
    except ValueError:
        return {}
    path = root / "data" / "activity" / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


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
    status_label = STATUS_LABELS.get(str(status.get("label")), str(status.get("label") or "待機中"))
    weather_label = WEATHER_LABELS.get(str(weather.get("label")), str(weather.get("label") or "通常"))
    timezone = str(state.get("timezone") or "Asia/Tokyo")
    last_at = format_activity_time(status.get("last_activity_at"), timezone)
    return f'''{MARKERS["live"][0]}
## 開発ステータス

<table>
  <tr>
    <td width="33%" align="center"><strong>{html.escape(str(status.get("symbol") or "○"))} {html.escape(status_label)}</strong><br/><sub>最終公開アクティビティ · {last_at} JST</sub></td>
    <td width="34%" align="center"><strong>{html.escape(str(weather.get("icon") or "🌙"))} {html.escape(weather_label)}</strong><br/><sub>本日の公開アクション · {int(state.get("activity_total", 0) or 0)}</sub></td>
    <td width="33%" align="center"><strong>🔥 {int(state.get("streak", 0) or 0)}日連続</strong><br/><sub>公開GitHubアクティビティ</sub></td>
  </tr>
</table>
{MARKERS["live"][1]}'''


def render_today(snapshot: dict[str, Any], state: dict[str, Any]) -> str:
    metrics = snapshot.get("metrics") or {}
    date_text = html.escape(str(snapshot.get("date") or state.get("date") or ""))
    return f'''{MARKERS["today"][0]}
## 今日の活動

<p align="center"><sub>{date_text} JST · 公開GitHubアクティビティ</sub></p>

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(metrics.get("commits", 0) or 0)}</strong><br/><sub>コミット</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PR作成</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_created", 0) or 0)}</strong><br/><sub>Issue作成</sub></td>
    <td width="25%" align="center"><strong>{int(metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>Issue完了</sub></td>
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
            stack = "<sub>技術情報は次回フル更新時に取得</sub>"
        body = f'''<table>
  <tr>
    <td width="62%" valign="top"><strong><a href="{repo_url}">{repo}</a></strong><br/><sub>加重アクティビティ {int(focus.get("share", 0) or 0)}% · スコア {int(focus.get("score", 0) or 0)} · {int(focus.get("events", 0) or 0)}イベント</sub></td>
    <td width="38%" valign="top"><strong>主な技術</strong><br/>{stack}</td>
  </tr>
</table>'''
    return f'''{MARKERS["focus"][0]}
## 現在のフォーカス

{body}
{MARKERS["focus"][1]}'''


def render_pulse() -> str:
    return f'''{MARKERS["pulse"][0]}
## 開発パルス // 直近7日

<p align="center">
  <img src="./assets/dev-pulse.svg" width="100%" alt="直近7日間の公開GitHubアクティビティ" />
</p>
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
            health_label = HEALTH_LABELS.get(str(health.get("label")), str(health.get("label") or "稼働中"))
            ci = item.get("ci") or {}
            pass_rate = ci.get("pass_rate")
            ci_text = "CI情報なし" if pass_rate is None else f"CI成功率 {pass_rate}%"
            last_at = format_activity_time(item.get("last_activity_at"), str(state.get("timezone") or "Asia/Tokyo"))
            cells.append(
                f'<td width="33%" valign="top"><strong>{index:02d} · <a href="{url}">{repo}</a></strong><br/>'
                f'<sub>{int(item.get("share", 0) or 0)}% · {html.escape(health_label)} · {html.escape(ci_text)}<br/>最終活動 · {last_at} JST</sub></td>'
            )
        while len(cells) < 3:
            cells.append('<td width="33%" valign="top"><sub>—</sub></td>')
        content = f'<table><tr>{"".join(cells)}</tr></table>'
    return f'''{MARKERS["building"][0]}
## 現在動いているリポジトリ

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
            title = html.escape(str(item.get("title") or "公開アクティビティ"))
            label = html.escape(STREAM_LABELS.get(str(item.get("label")), str(item.get("label") or "ACTIVITY")))
            at = format_activity_time(item.get("at"), timezone)
            rendered.append(
                f'<tr><td width="10%"><code>{at}</code></td><td width="14%"><code>{label}</code></td>'
                f'<td><strong><a href="{repo_url}">{repo}</a></strong> — <a href="{url}">{title}</a></td></tr>'
            )
        rows = "\n    ".join(rendered)
    return f'''{MARKERS["stream"][0]}
## 最近の公開アクティビティ

<table>
  <tbody>
    {rows}
  </tbody>
</table>
{MARKERS["stream"][1]}'''


def render_recap(state: dict[str, Any]) -> str:
    recap = state.get("dev_recap") or {}
    weekly = recap.get("weekly") or {}
    monthly = recap.get("monthly") or {}
    weekly_metrics = weekly.get("metrics") or {}
    monthly_metrics = monthly.get("metrics") or {}
    return f'''{MARKERS["recap"][0]}
## 開発サマリー // 記録履歴

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(recap.get("active_days", 0) or 0)}</strong><br/><sub>活動日</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("commits", 0) or 0)}</strong><br/><sub>今週のコミット</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>今週のPR</sub></td>
    <td width="25%" align="center"><strong>{int(weekly_metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>今週のIssue完了</sub></td>
  </tr>
</table>

<details>
<summary><strong>月次サマリー</strong></summary>

<br/>

<table>
  <tr>
    <td width="25%" align="center"><strong>{int(monthly_metrics.get("commits", 0) or 0)}</strong><br/><sub>コミット</sub></td>
    <td width="25%" align="center"><strong>{int(monthly_metrics.get("prs_opened", 0) or 0)}</strong><br/><sub>PR</sub></td>
    <td width="25%" align="center"><strong>{int(monthly_metrics.get("issues_completed", 0) or 0)}</strong><br/><sub>Issue完了</sub></td>
    <td width="25%" align="center"><strong>{int(monthly_metrics.get("activity_total", 0) or 0)}</strong><br/><sub>総アクティビティ</sub></td>
  </tr>
</table>
</details>
{MARKERS["recap"][1]}'''


def localize_pulse_svg(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    replacements = {
        "Developer activity pulse for the last seven days": "直近7日間の開発アクティビティ",
        "Seven day public GitHub activity totals, with today's commit, pull request and issue counts.": "直近7日間の公開GitHubアクティビティと本日のコミット・PR・Issue数。",
        "DEV PULSE · LAST 7 DAYS": "開発パルス · 直近7日",
        "activity = commits + PRs opened + issues created + issues done": "活動量 = コミット + PR作成 + Issue作成 + Issue完了",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    path.write_text(text, encoding="utf-8")


def customize(root: Path, readme_path: Path, state_path: Path, ignore_path: Path) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    patterns = load_ignore_patterns(ignore_path)
    state = filter_state(state, patterns)
    snapshot = load_today_snapshot(root, state)
    text = readme_path.read_text(encoding="utf-8")
    for name, block in (
        ("live", render_live(state)),
        ("today", render_today(snapshot, state)),
        ("focus", render_focus(state)),
        ("pulse", render_pulse()),
        ("building", render_building(state)),
        ("stream", render_stream(state)),
        ("recap", render_recap(state)),
    ):
        text = replace_marker(text, name, block)
    readme_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    localize_pulse_svg(root / "assets" / "dev-pulse.svg")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Localize and filter Profile Signal consumer output")
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
    print(
        "Customized Profile Signal:",
        f"focus={(customized.get('current_focus') or {}).get('repo', 'none')}",
        f"ignored={len(customized.get('repository_ignore_patterns') or [])}",
    )


if __name__ == "__main__":
    main()
