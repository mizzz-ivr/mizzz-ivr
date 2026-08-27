from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

SCHEMA_VERSION = 1
README_START = "<!-- DEVELOPER-ANALYTICS:START -->"
README_END = "<!-- DEVELOPER-ANALYTICS:END -->"
LEVELS = ((75, "STRONG"), (55, "REPEATED"), (35, "ESTABLISHED"), (0, "EMERGING"))
PRACTICE_MAP = {
    "ci_cd": "ci-cd",
    "tests": "automated-testing",
    "documentation": "documentation",
    "containerization": "containerization",
    "schema_migrations": "schema-migrations",
    "infrastructure_as_code": "infrastructure-as-code",
    "security_process": "security-process",
    "observability": "observability",
    "release_automation": "release-automation",
}


class ConfigError(ValueError):
    pass


class GitHubAPIError(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def age_days(value: str | None, now: datetime) -> int | None:
    parsed = parse_dt(value)
    return None if parsed is None else max(0, (now - parsed).days)


def recency_points(days: int | None) -> int:
    if days is None:
        return 0
    for limit, points in ((30, 20), (90, 15), (180, 10), (365, 5)):
        if days <= limit:
            return points
    return 1


def level(score: int) -> str:
    return next(label for threshold, label in LEVELS if score >= threshold)


def normalize_repo(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ConfigError(f"invalid repository: {value!r}")
    return value


def validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != 1:
        raise ConfigError("developer analytics config version must be 1")
    if not str((config.get("profile") or {}).get("github_login") or "").strip():
        raise ConfigError("profile.github_login is required")
    projects = config.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ConfigError("projects must be a non-empty list")
    seen: set[str] = set()
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ConfigError(f"projects[{index}] must be an object")
        repo = normalize_repo(str(project.get("repo") or ""))
        if repo in seen:
            raise ConfigError(f"duplicate project repository: {repo}")
        seen.add(repo)
        if project.get("public") is not True:
            raise ConfigError(f"{repo}: committed analytics requires public: true")
        for key in ("technologies", "domains", "capabilities", "practices", "ownership"):
            value = project.get(key, [])
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ConfigError(f"{repo}: {key} must be a list of non-empty strings")
        for evidence in project.get("evidence", []):
            if not isinstance(evidence, dict) or not evidence.get("label") or not str(evidence.get("url", "")).startswith("https://github.com/"):
                raise ConfigError(f"{repo}: evidence requires label and GitHub URL")
    assignment_ids: set[str] = set()
    for assignment in config.get("assignment_profiles", []):
        assignment_id = str(assignment.get("id") or "").strip()
        if not assignment_id or assignment_id in assignment_ids:
            raise ConfigError("assignment profile ids must be unique and non-empty")
        assignment_ids.add(assignment_id)
        signals = assignment.get("signals", [])
        if not isinstance(signals, list) or not signals:
            raise ConfigError(f"{assignment_id}: signals must be non-empty")
        for signal in signals:
            if not isinstance(signal, dict) or len(signal) != 1:
                raise ConfigError(f"{assignment_id}: each signal must have one category")
            category, value = next(iter(signal.items()))
            if category not in {"technology", "domain", "capability", "practice", "ownership"} or not isinstance(value, str) or not value.strip():
                raise ConfigError(f"{assignment_id}: invalid signal {signal!r}")


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_config(config)
    return config


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"https://api.github.com{path}" + (f"?{query}" if query else "")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "mizzz-developer-analytics/1.0", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GitHubAPIError(f"GET {path}: HTTP {exc.code}: {body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise GitHubAPIError(f"GET {path}: {exc}") from exc

    def repo(self, repo: str) -> dict[str, Any]:
        return self.get(f"/repos/{repo}")

    def languages(self, repo: str) -> dict[str, int]:
        result = self.get(f"/repos/{repo}/languages")
        return result if isinstance(result, dict) else {}

    def tree(self, repo: str, branch: str) -> list[str]:
        result = self.get(f"/repos/{repo}/git/trees/{urllib.parse.quote(branch, safe='')}", {"recursive": 1})
        return [str(item["path"]) for item in result.get("tree", []) if item.get("type") == "blob" and item.get("path")]

    def search_count(self, query: str) -> int:
        return int(self.get("/search/issues", {"q": query, "per_page": 1}).get("total_count") or 0)

    def latest_authored_commit(self, repo: str, login: str) -> dict[str, Any] | None:
        try:
            result = self.get(f"/repos/{repo}/commits", {"author": login, "per_page": 1})
        except GitHubAPIError as exc:
            if "HTTP 409" in str(exc):
                return None
            raise
        return result[0] if isinstance(result, list) and result else None


def detect_delivery_signals(paths: Iterable[str]) -> dict[str, bool]:
    paths = [path.lower() for path in paths]
    contains = lambda *patterns: any(any(pattern in path for pattern in patterns) for path in paths)
    return {
        "ci_cd": any(path.startswith(".github/workflows/") for path in paths),
        "tests": contains("tests/", "test/", "__tests__", ".test.", ".spec.", "pytest.ini", "vitest", "playwright"),
        "documentation": any(path == "readme.md" or path.startswith("docs/") for path in paths),
        "containerization": contains("dockerfile", "docker-compose", "compose.yml", "compose.yaml"),
        "schema_migrations": contains("migrations/", "migration/", "prisma/migrations", "supabase/migrations"),
        "infrastructure_as_code": contains("terraform", ".tf", "deploy/", "infra/", "wrangler.toml", "netlify.toml", "vercel.json"),
        "security_process": contains("security.md", "dependabot.yml", "codeql", "authz", "rbac"),
        "observability": contains("observability", "logger", "logging", "health", "monitor", "metrics", "telemetry"),
        "release_automation": contains("release.yml", "release.yaml", "releases.yml", "releases.yaml", "semantic-release", "changesets"),
    }


def commit_date(commit: dict[str, Any] | None) -> str | None:
    data = (commit or {}).get("commit") or {}
    return (data.get("author") or {}).get("date") or (data.get("committer") or {}).get("date")


def collect_project(client: GitHubClient, configured: dict[str, Any], login: str, now: datetime) -> dict[str, Any]:
    repo = normalize_repo(configured["repo"])
    metadata = client.repo(repo)
    if metadata.get("private"):
        raise GitHubAPIError(f"{repo}: private repository refused")
    if metadata.get("fork") and not configured.get("allow_fork", False):
        raise GitHubAPIError(f"{repo}: fork refused as original evidence")
    branch = str(metadata.get("default_branch") or "main")
    delivery = detect_delivery_signals(client.tree(repo, branch))
    latest = commit_date(client.latest_authored_commit(repo, login))
    last_evidence_at = latest or metadata.get("pushed_at")
    recency = age_days(last_evidence_at, now)
    contributions = {
        "prs_opened": client.search_count(f"repo:{repo} is:pr author:{login}"),
        "prs_merged": client.search_count(f"repo:{repo} is:pr is:merged author:{login}"),
        "issues_opened": client.search_count(f"repo:{repo} is:issue author:{login}"),
        "issues_closed": client.search_count(f"repo:{repo} is:issue is:closed author:{login}"),
    }
    contribution_points = min(25, contributions["prs_merged"] * 2 + contributions["prs_opened"] + contributions["issues_closed"] + contributions["issues_opened"] // 2)
    delivery_points = min(20, sum(delivery.values()) * 3)
    score = min(100, 20 + recency_points(recency) + contribution_points + delivery_points)
    detected = sorted(PRACTICE_MAP[key] for key, enabled in delivery.items() if enabled)
    configured_practices = sorted(set(configured.get("practices", [])))
    return {
        "repo": repo,
        "title": configured.get("title") or metadata.get("name") or repo,
        "url": metadata.get("html_url") or f"https://github.com/{repo}",
        "description": configured.get("summary") or metadata.get("description") or "",
        "featured": bool(configured.get("featured")),
        "archived": bool(metadata.get("archived")),
        "primary_language": metadata.get("language"),
        "languages": client.languages(repo),
        "technologies": sorted(set(configured.get("technologies", []))),
        "domains": sorted(set(configured.get("domains", []))),
        "capabilities": sorted(set(configured.get("capabilities", []))),
        "practices": sorted(set(configured_practices + detected)),
        "configured_practices": configured_practices,
        "detected_practices": detected,
        "ownership": sorted(set(configured.get("ownership", []))),
        "delivery_signals": delivery,
        "contributions": contributions,
        "last_evidence_at": last_evidence_at,
        "recency_days": recency,
        "recency_source": "authored_commit" if latest else "repository_push",
        "evidence_score": score,
        "evidence_level": level(score),
        "evidence": configured.get("evidence", []),
    }


def collect_project_offline(configured: dict[str, Any]) -> dict[str, Any]:
    practices = sorted(set(configured.get("practices", [])))
    score = min(100, 20 + len(configured.get("technologies", [])) * 2 + len(practices) * 2 + len(configured.get("evidence", [])) * 4)
    return {
        "repo": normalize_repo(configured["repo"]), "title": configured.get("title") or configured["repo"].split("/")[-1],
        "url": f"https://github.com/{configured['repo']}", "description": configured.get("summary") or "", "featured": bool(configured.get("featured")),
        "archived": False, "primary_language": None, "languages": {}, "technologies": sorted(set(configured.get("technologies", []))),
        "domains": sorted(set(configured.get("domains", []))), "capabilities": sorted(set(configured.get("capabilities", []))),
        "practices": practices, "configured_practices": practices, "detected_practices": [], "ownership": sorted(set(configured.get("ownership", []))),
        "delivery_signals": {}, "contributions": {"prs_opened": 0, "prs_merged": 0, "issues_opened": 0, "issues_closed": 0},
        "last_evidence_at": None, "recency_days": None, "recency_source": "not_collected", "evidence_score": score,
        "evidence_level": level(score), "evidence": configured.get("evidence", []),
    }


def aggregate(projects: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project in projects:
        for value in project.get(key, []):
            grouped[value].append(project)
    rows = []
    for name, items in grouped.items():
        recency = min((item["recency_days"] for item in items if item.get("recency_days") is not None), default=None)
        merged = sum(item["contributions"]["prs_merged"] for item in items)
        closed = sum(item["contributions"]["issues_closed"] for item in items)
        variety = len({practice for item in items for practice in item.get("practices", [])})
        score = min(100, min(40, len(items) * 10) + recency_points(recency) + min(25, merged * 2 + closed) + min(15, variety * 2))
        dates = [parse_dt(item.get("last_evidence_at")) for item in items]
        latest = max((date for date in dates if date), default=None)
        rows.append({"name": name, "score": score, "level": level(score), "project_count": len(items), "projects": sorted(item["repo"] for item in items), "last_evidence_at": latest.isoformat().replace("+00:00", "Z") if latest else None, "recency_days": recency, "merged_prs": merged, "closed_issues": closed, "delivery_variety": variety})
    return sorted(rows, key=lambda row: (-row["score"], -row["project_count"], row["name"].lower()))


def assignment_fit(config: dict[str, Any], projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = {"technology": "technologies", "domain": "domains", "capability": "capabilities", "practice": "practices", "ownership": "ownership"}
    available = {category: {str(value).lower() for project in projects for value in project.get(key, [])} for category, key in mapping.items()}
    rows = []
    for assignment in config.get("assignment_profiles", []):
        matched, missing = [], []
        for signal in assignment["signals"]:
            category, value = next(iter(signal.items()))
            record = {"category": category, "value": value}
            (matched if value.lower() in available[category] else missing).append(record)
        total = len(matched) + len(missing)
        rows.append({"id": assignment["id"], "label": assignment.get("label") or assignment["id"], "score": round(len(matched) / total * 100) if total else 0, "matched": matched, "missing": missing, "note": assignment.get("note") or ""})
    return sorted(rows, key=lambda row: (-row["score"], row["label"].lower()))


def build_analytics(config: dict[str, Any], projects: list[dict[str, Any]], *, generated_at: datetime, collection_mode: str, errors: list[str] | None = None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    dimensions = {name: aggregate(projects, key) for name, key in {"skills": "technologies", "domains": "domains", "capabilities": "capabilities", "practices": "practices", "ownership": "ownership"}.items()}
    current = {row["name"]: row["score"] for row in dimensions["skills"]}
    before = {row.get("name"): row.get("score", 0) for row in (previous or {}).get("skills", []) if row.get("name")}
    changed = [{"name": name, "from": before[name], "to": score, "delta": score - before[name]} for name, score in current.items() if name in before and before[name] != score]
    changed.sort(key=lambda item: (-abs(item["delta"]), item["name"].lower()))
    summary = {
        "tracked_projects": len(projects), "active_projects_90d": sum(1 for p in projects if p.get("recency_days") is not None and p["recency_days"] <= 90),
        "technologies": len(dimensions["skills"]), "domains": len(dimensions["domains"]), "capabilities": len(dimensions["capabilities"]), "practices": len(dimensions["practices"]),
        "merged_prs_observed": sum(p["contributions"]["prs_merged"] for p in projects), "closed_issues_observed": sum(p["contributions"]["issues_closed"] for p in projects),
    }
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": generated_at.isoformat().replace("+00:00", "Z"), "scope": "public-github-evidence", "collection_mode": collection_mode,
        "profile": config["profile"], "summary": summary,
        "projects": sorted(projects, key=lambda p: (-int(p["featured"]), -p["evidence_score"], p["repo"].lower())), **dimensions,
        "assignment_fit": assignment_fit(config, projects),
        "trend": {"previous_snapshot_at": (previous or {}).get("generated_at"), "new_skills": sorted(set(current) - set(before)) if previous else [], "changed_skills": changed[:15]},
        "data_quality": {"errors": errors or [], "limitations": [
            "This measures public GitHub evidence, not total professional experience or proficiency.",
            "No public evidence means not observed; it must not be interpreted as no experience.",
            "Repository push recency is used only when a user-authored commit cannot be observed.",
            "Private repositories and confidential project metadata are intentionally excluded from committed outputs.",
        ]},
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    clean = [[str(cell).replace("|", "\\|").replace("\n", " ") for cell in row] for row in rows]
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |", *("| " + " | ".join(row) + " |" for row in clean)])


def recency(row: dict[str, Any]) -> str:
    days = row.get("recency_days")
    return "not observed" if days is None else ("today" if days == 0 else f"{days}d ago")


def render_readme_block(data: dict[str, Any]) -> str:
    skills, domains, practices, fits = data["skills"][:8], data["domains"][:6], data["practices"][:8], data["assignment_fit"][:4]
    stamp = data["generated_at"].replace("T", " ").replace("Z", " UTC")
    note = f"Manual Developer Analytics snapshot · {stamp} · public evidence only" if data["collection_mode"] == "github-api" else f"Bootstrap snapshot · {stamp} · curated public evidence; live recency/PR counts are collected on manual run"
    return "\n".join([
        README_START, "## ENGINEERING PROFILE // Public evidence", "",
        "公開Repositoryの実装・PR/Issue・構成ファイル・継続利用から、現在の技術傾向と開発スタイルを整理しています。  ",
        "**Evidence Scoreは能力点ではなく、公開GitHub上で確認できる証拠の強さです。**", "", "### Core technology signals", "",
        table(["Technology", "Evidence", "Projects", "Latest"], [[r["name"], r["level"], r["project_count"], recency(r)] for r in skills]), "",
        "### Engineering range", "", " ".join(f"`{r['name']}`" for r in domains), "", "### How I ship", "", " ".join(f"`{r['name']}`" for r in practices), "",
        "### Assignment fit // Evidence coverage", "", table(["Area", "Coverage", "Matched", "Gap"], [[r["label"], f"{r['score']}%", len(r["matched"]), len(r["missing"])] for r in fits]), "",
        f'<p align="center"><sub>{note} · <a href="./SKILL_SHEET.md">SKILL_SHEET.md</a> · <a href="./reports/developer-analytics.md">Detailed analytics</a></sub></p>', README_END,
    ])


def render_report(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = ["# Developer Analytics", "", f"Generated: `{data['generated_at']}` · mode: `{data['collection_mode']}`", "", "> Public GitHub evidence only. Not a proficiency, years-of-experience, or productivity score.", "", "## Coverage", "", table(["Metric", "Value"], [["Tracked public projects", summary["tracked_projects"]], ["Active projects (90d)", summary["active_projects_90d"]], ["Technologies", summary["technologies"]], ["Domains", summary["domains"]], ["Capabilities", summary["capabilities"]], ["Engineering practices", summary["practices"]], ["Merged PRs observed", summary["merged_prs_observed"]], ["Closed issues observed", summary["closed_issues_observed"]]]), ""]
    for heading, key in (("Technology evidence", "skills"), ("Engineering practices", "practices"), ("Delivery ownership", "ownership")):
        lines += [f"## {heading}", "", table(["Signal", "Score", "Evidence", "Projects", "Latest"], [[r["name"], r["score"], r["level"], r["project_count"], recency(r)] for r in data[key]]), ""]
    lines += ["## Assignment fit", "", table(["Assignment", "Coverage", "Matched", "Missing"], [[r["label"], f"{r['score']}%", ", ".join(i["value"] for i in r["matched"]), ", ".join(i["value"] for i in r["missing"]) or "-"] for r in data["assignment_fit"]]), "", "## Project evidence", "", table(["Project", "Evidence", "Recency", "Merged PRs", "Issues done", "Signals"], [[f"[{p['repo']}]({p['url']})", f"{p['evidence_score']} / {p['evidence_level']}", f"{p['recency_days']}d" if p.get("recency_days") is not None else "not observed", p["contributions"]["prs_merged"], p["contributions"]["issues_closed"], ", ".join(p["detected_practices"][:6] or p["configured_practices"][:6])] for p in data["projects"]]), "", "## Data quality / interpretation", "", *(f"- {item}" for item in data["data_quality"]["limitations"])]
    if data["data_quality"]["errors"]:
        lines += ["", "### Collection errors", "", *(f"- `{item}`" for item in data["data_quality"]["errors"])]
    return "\n".join(lines).rstrip() + "\n"


def render_skill_sheet(data: dict[str, Any]) -> str:
    profile, skills, practices, ownership, fits = data["profile"], data["skills"], data["practices"], data["ownership"], data["assignment_fit"]
    projects = [p for p in data["projects"] if p.get("featured")] or data["projects"][:6]
    strong = [r for r in skills if r["level"] in {"STRONG", "REPEATED"}][:12] or skills[:10]
    lines = [
        "# Skill Sheet — いゔる。 / mizzz", "", f"> 生成日時: `{data['generated_at']}` / Source: Public GitHub Evidence / Mode: `{data['collection_mode']}`  ",
        "> フリーランス・受託・案件アサイン時に再利用できる公開Evidenceベースのスキルシートです。", "", "## 基本情報", "",
        f"- **Name / Handle:** {profile.get('display_name', '')}", f"- **GitHub:** https://github.com/{profile['github_login']}", f"- **Website:** {profile.get('website', '')}", f"- **Contact:** {profile.get('contact', '')}", f"- **Role:** {profile.get('headline', '')}", "",
        "## エンジニアリング概要", "", profile.get("summary", ""), "", "### 公開Evidenceが特に強い技術", "", " / ".join(f"**{r['name']}**" for r in strong), "", "## 技術Evidence", "",
        table(["Technology", "Evidence", "Score", "Projects", "Latest public evidence"], [[r["name"], r["level"], r["score"], r["project_count"], recency(r)] for r in skills[:20]]), "",
        "> `Evidence Score` は公開GitHub上で確認できる証拠の量・広がり・新しさを表す指標です。能力値・習熟度・経験年数ではありません。", "", "## 開発手法 / Engineering Practices", "",
        table(["Practice", "Evidence", "Projects"], [[r["name"], r["level"], ", ".join(r["projects"][:5])] for r in practices[:18]]), "", "## Delivery / Ownership Evidence", "",
        table(["Area", "Evidence", "Projects"], [[r["name"], r["level"], ", ".join(r["projects"][:5])] for r in ownership[:14]]), "", "## 案件タイプ別 Public Evidence Coverage", "",
        table(["Area", "Coverage", "Public evidence gap"], [[r["label"], f"{r['score']}%", ", ".join(i["value"] for i in r["missing"]) or "Configured signal setでは不足なし"] for r in fits]), "",
        "> Coverageは採用適合度ではなく、設定した技術・Capability・Practiceを公開Repositoryでどれだけ証明できるかを示します。", "", "## Selected Public Projects", "",
    ]
    for p in projects:
        lines += [f"### [{p['title']}]({p['url']})", "", p["description"] or "Public project evidence.", "", f"- **Domains:** {', '.join(p['domains']) or '-'}", f"- **Technologies:** {', '.join(p['technologies']) or '-'}", f"- **Capabilities:** {', '.join(p['capabilities']) or '-'}", f"- **Ownership:** {', '.join(p['ownership']) or '-'}", f"- **Observed delivery / practices:** {', '.join(p['practices']) or '-'}"]
        lines += [f"- **Evidence:** [{e['label']}]({e['url']})" for e in p.get("evidence", [])[:4]] + [""]
    lines += ["## 利用時の注意", "", "- 公開して問題ないGitHub Evidenceだけに限定しています。", "- Private Repository、顧客情報、秘密情報、非公開案件のRepository名は出力しません。", "- 公開Evidenceが無い項目は **未経験** ではなく **GitHub上では未観測** と扱います。", "- 営業提出時には守秘義務に反しない職務経歴・担当期間・契約条件を必要に応じて別途追記してください。", "- このSkill Sheetは手動実行時だけ再生成され、定期scheduleでは更新しません。"]
    return "\n".join(lines).rstrip() + "\n"


def replace_readme_block(readme: str, block: str) -> str:
    if README_START in readme or README_END in readme:
        if readme.count(README_START) != 1 or readme.count(README_END) != 1:
            raise ConfigError("README must contain exactly one Developer Analytics marker pair")
        start, end = readme.index(README_START), readme.index(README_END) + len(README_END)
        return readme[:start] + block + readme[end:]
    marker = "## PUBLIC BUILDS // Selected evidence" if "## PUBLIC BUILDS // Selected evidence" in readme else "## PUBLIC BUILDS // Featured"
    if marker not in readme:
        raise ConfigError("README missing Developer Analytics insertion point")
    position = readme.index(marker)
    return f"{readme[:position].rstrip()}\n\n---\n\n{block}\n\n---\n\n{readme[position:].lstrip()}"


def read_previous(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (json.JSONDecodeError, OSError):
        return None


def write_outputs(data: dict[str, Any], *, output: Path, report: Path, skill_sheet: Path, readme: Path | None, snapshot_dir: Path | None) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    for path in (output, report, skill_sheet):
        path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    report.write_text(render_report(data), encoding="utf-8")
    skill_sheet.write_text(render_skill_sheet(data), encoding="utf-8")
    if readme:
        readme.write_text(replace_readme_block(readme.read_text(encoding="utf-8"), render_readme_block(data)).rstrip() + "\n", encoding="utf-8")
    if snapshot_dir:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        stamp = data["generated_at"].replace("-", "").replace(":", "").replace("T", "-")
        (snapshot_dir / f"{stamp}.json").write_text(payload, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.validate_only:
        print(f"Validated {len(config['projects'])} public analytics projects and {len(config.get('assignment_profiles', []))} assignment profiles")
        return 0
    now, previous, errors, projects = now_utc(), read_previous(args.output), [], []
    if args.offline:
        projects = [collect_project_offline(project) for project in config["projects"]]
        mode = "offline-config"
    else:
        client, login = GitHubClient(os.environ.get("GITHUB_TOKEN")), config["profile"]["github_login"]
        for project in config["projects"]:
            try:
                projects.append(collect_project(client, project, login, now))
            except Exception as exc:
                errors.append(f"{project.get('repo')}: {exc}")
                if args.strict:
                    raise
        mode = "github-api"
    if not projects:
        raise GitHubAPIError("no project evidence could be collected")
    data = build_analytics(config, projects, generated_at=now, collection_mode=mode, errors=errors, previous=previous)
    write_outputs(data, output=args.output, report=args.report, skill_sheet=args.skill_sheet, readme=args.readme, snapshot_dir=None if args.no_snapshot else args.snapshot_dir)
    print(f"Generated Developer Analytics: projects={len(projects)} skills={len(data['skills'])} practices={len(data['practices'])} assignments={len(data['assignment_fit'])}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate public evidence-backed Developer Analytics and Markdown skill sheet")
    p.add_argument("--config", type=Path, default=Path(".github/developer-analytics.yml"))
    p.add_argument("--output", type=Path, default=Path("data/developer-analytics/latest.json"))
    p.add_argument("--report", type=Path, default=Path("reports/developer-analytics.md"))
    p.add_argument("--skill-sheet", type=Path, default=Path("SKILL_SHEET.md"))
    p.add_argument("--readme", type=Path, default=Path("README.md"))
    p.add_argument("--snapshot-dir", type=Path, default=Path("data/developer-analytics/snapshots"))
    p.add_argument("--offline", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-snapshot", action="store_true")
    p.add_argument("--validate-only", action="store_true")
    return p


if __name__ == "__main__":
    try:
        raise SystemExit(run(parser().parse_args()))
    except (ConfigError, GitHubAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
