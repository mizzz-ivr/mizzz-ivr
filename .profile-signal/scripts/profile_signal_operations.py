#!/usr/bin/env python3
"""Add repository health and CI signals to Profile Signal state and widgets."""

from __future__ import annotations

import html
import json
import os
import subprocess
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from profile_signal import aggregate_ci_signals, ci_summary, repository_health

LOGIN = os.getenv("GITHUB_LOGIN", "mizzz-ivr")
TZ_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
STATE_PATH = ROOT / "data" / "profile-signal-state.json"

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = f"{LOGIN}-profile-signal-operations"
CI_RUNS_PER_REPO = 10

PULSE_START = "<!-- PROFILE-SIGNAL:PULSE:START -->"
PULSE_END = "<!-- PROFILE-SIGNAL:PULSE:END -->"
BUILDING_START = "<!-- PROFILE-SIGNAL:NOW-BUILDING:START -->"
BUILDING_END = "<!-- PROFILE-SIGNAL:NOW-BUILDING:END -->"


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


def encoded_repo(repo: str) -> str:
    if "/" not in repo:
        raise ValueError(f"Invalid repository name: {repo}")
    owner, name = repo.split("/", 1)
    return f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}"


def fetch_repository_metadata(repo: str) -> dict[str, Any]:
    payload = request_json(f"{API_BASE}/repos/{encoded_repo(repo)}")
    return payload if isinstance(payload, dict) else {}


def fetch_workflow_runs(repo: str) -> list[dict[str, Any]]:
    url = (
        f"{API_BASE}/repos/{encoded_repo(repo)}/actions/runs"
        f"?per_page={CI_RUNS_PER_REPO}&status=completed"
    )
    payload = request_json(url)
    if not isinstance(payload, dict):
        return []
    runs = payload.get("workflow_runs") or []
    return [item for item in runs if isinstance(item, dict)]


def enrich_now_building(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    ci_signals: list[dict[str, Any]] = []

    for raw_item in state.get("now_building") or []:
        item = dict(raw_item)
        repo = str(item.get("repo") or "")
        metadata: dict[str, Any] = {}
        runs: list[dict[str, Any]] = []

        try:
            metadata = fetch_repository_metadata(repo)
        except (RuntimeError, ValueError) as exc:
            print(f"warning: repository metadata unavailable for {repo}: {exc}")

        try:
            runs = fetch_workflow_runs(repo)
        except (RuntimeError, ValueError) as exc:
            print(f"warning: workflow runs unavailable for {repo}: {exc}")

        ci = ci_summary(runs, now, window_days=7)
        health = repository_health(metadata, ci, now, quiet_days=30)
        item["ci"] = ci
        item["health"] = health
        enriched.append(item)
        ci_signals.append(ci)

    result = dict(state)
    result["schema_version"] = 3
    result["now_building"] = enriched
    result["ci_signal"] = aggregate_ci_signals(ci_signals)
    return result


def read_head_state() -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            ["git", "show", "HEAD:data/profile-signal-state.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        return payload if isinstance(payload, dict) else None
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None


def semantic_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "generated_at"}


def write_state(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    previous = read_head_state()
    payload = dict(state)
    if previous is not None and semantic_state(previous) == semantic_state(payload):
        payload["generated_at"] = previous.get("generated_at", now.isoformat(timespec="seconds"))
    else:
        payload["generated_at"] = now.isoformat(timespec="seconds")

    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


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


def render_pulse(state: dict[str, Any]) -> str:
    signal = state.get("ci_signal") or {}
    rate = signal.get("pass_rate")
    rate_display = "—" if rate is None else f"{int(rate)}%"
    evaluated = int(signal.get("evaluated", 0) or 0)
    passed = int(signal.get("passed", 0) or 0)
    repos = int(signal.get("repos_with_signal", 0) or 0)
    label = html.escape(str(signal.get("label", "NO SIGNAL")))
    symbol = html.escape(str(signal.get("symbol", "○")))

    return f'''{PULSE_START}
## DEV PULSE // Last 7 days

<p align="center">
  <img src="./assets/dev-pulse.svg" width="100%" alt="7 day public GitHub development pulse" />
</p>

<table>
  <tr>
    <td width="25%" align="center"><strong>{symbol} {label}</strong><br/><sub>CI SIGNAL · last 7 days</sub></td>
    <td width="25%" align="center"><strong>{rate_display}</strong><br/><sub>PASS RATE</sub></td>
    <td width="25%" align="center"><strong>{passed} / {evaluated}</strong><br/><sub>PASSED / EVALUATED</sub></td>
    <td width="25%" align="center"><strong>{repos}</strong><br/><sub>REPOS WITH CI</sub></td>
  </tr>
</table>

<p align="center"><sub>GitHub Actions · completed runs from active repositories · cancelled / skipped / neutral runs are excluded from pass rate</sub></p>
{PULSE_END}'''


def ci_display(ci: dict[str, Any]) -> str:
    evaluated = int(ci.get("evaluated", 0) or 0)
    passed = int(ci.get("passed", 0) or 0)
    if evaluated == 0:
        return "CI · no evaluated signal"
    return f"CI · {passed}/{evaluated} passed · {int(ci.get('pass_rate', 0) or 0)}%"


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
            health = item.get("health") or {}
            health_label = html.escape(str(health.get("label", "ACTIVE")))
            health_symbol = html.escape(str(health.get("symbol", "●")))
            ci = html.escape(ci_display(item.get("ci") or {}))
            cards.append(
                f'<td width="33%" valign="top"><strong>{index:02d} · <a href="{url}">{repo}</a></strong><br/>'
                f'<sub>{share}% weighted activity · score {score} · {events} events<br/>'
                f'{health_symbol} {health_label} · {ci}<br/>last activity · {active}</sub></td>'
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

<p align="center"><sub>Ranked by weighted public GitHub activity · health combines repository recency with recent GitHub Actions signal</sub></p>
{BUILDING_END}'''


def replace_marker_block(text: str, start_marker: str, end_marker: str, block: str) -> str:
    if start_marker not in text or end_marker not in text:
        raise RuntimeError(f"Missing README marker pair: {start_marker} / {end_marker}")
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + block + text[end:]


def update_readme(state: dict[str, Any]) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    text = replace_marker_block(text, PULSE_START, PULSE_END, render_pulse(state))
    text = replace_marker_block(text, BUILDING_START, BUILDING_END, render_now_building(state))
    README_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    now = datetime.now(TZ)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("Profile Signal state is not a JSON object")

    state = write_state(enrich_now_building(state, now), now)
    update_readme(state)
    signal = state.get("ci_signal") or {}
    print(
        "Profile Signal operations refreshed:",
        signal.get("label"),
        f"pass_rate={signal.get('pass_rate')}",
        f"repos={signal.get('repos_with_signal')}",
    )


if __name__ == "__main__":
    main()
