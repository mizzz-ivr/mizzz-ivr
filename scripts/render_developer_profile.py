from __future__ import annotations

import argparse
import html
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

README_START = "<!-- DEVELOPER-ANALYTICS:START -->"
README_END = "<!-- DEVELOPER-ANALYTICS:END -->"

TECH_LOGOS = {
    "React": "react",
    "TypeScript": "typescript",
    "JavaScript": "javascript",
    "Next.js": "nextdotjs",
    "Node.js": "nodedotjs",
    "NestJS": "nestjs",
    "Python": "python",
    "Flask": "flask",
    "Go": "go",
    "PostgreSQL": "postgresql",
    "Prisma": "prisma",
    "Redis": "redis",
    "Docker": "docker",
    "GitHub Actions": "githubactions",
    "Tailwind CSS": "tailwindcss",
    "Vite": "vite",
    "Playwright": "playwright",
    "Vitest": "vitest",
    "Astro": "astro",
    "Electron": "electron",
    "Supabase": "supabase",
    "Cloudflare Workers": "cloudflareworkers",
    "Netlify": "netlify",
    "Vercel": "vercel",
}

PRACTICE_JA = {
    "repository-driven-development": "Repository中心の開発",
    "security-by-design": "Security by Design",
    "automated-testing": "自動テスト",
    "accessibility-first": "Accessibility",
    "observability": "Observability",
    "least-privilege": "Least Privilege",
    "fail-close": "Fail-close",
    "release-automation": "Release Automation",
    "documentation": "Documentation",
    "containerization": "Containerization",
    "ci-cd": "CI/CD",
}

ASSIGNMENT_JA = {
    "Full-stack Product Development": "Full-stack Product Development",
    "Realtime AI / Voice": "Realtime AI / Voice",
    "Platform / Developer Tooling": "Platform / Developer Tooling",
    "DevOps / Observability": "DevOps / Observability",
    "Discord / Community Systems": "Discord / Community Systems",
}

DOMAIN_JA = {
    "full-stack": "Full Stack",
    "frontend": "Frontend",
    "backend-api": "Backend / API",
    "realtime-ai": "Realtime AI",
    "desktop-app": "Desktop App",
    "developer-platform": "Developer Platform",
    "observability": "Observability",
    "infrastructure": "Infrastructure",
    "community-platform": "Community Platform",
    "developer-tooling": "Developer Tooling",
    "web-product": "Web Product",
}

CATEGORY_TECH = {
    "Frontend": ["TypeScript", "React", "Next.js", "Tailwind CSS", "Astro", "Vite"],
    "Backend": ["Node.js", "NestJS", "Python", "Flask", "Go"],
    "Data": ["PostgreSQL", "Prisma", "Redis", "Supabase", "SQLite"],
    "AI / Community": ["OpenAI Realtime API", "Discord.js", "Discord Voice", "Electron"],
    "DevOps / Infra": ["Docker", "GitHub Actions", "Netlify", "Vercel", "AWS Lightsail", "OCI", "Cloudflare Workers"],
}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def bootstrap_from_config(config: dict[str, Any], generated_at: str) -> dict[str, Any]:
    projects = []
    skill_projects: dict[str, set[str]] = {}
    practices: dict[str, set[str]] = {}
    domains: dict[str, set[str]] = {}
    capabilities: dict[str, set[str]] = {}
    ownership: dict[str, set[str]] = {}

    for project in config.get("projects") or []:
        row = {
            "repo": project["repo"],
            "title": project.get("title") or project["repo"].split("/")[-1],
            "url": f"https://github.com/{project['repo']}",
            "description": project.get("summary") or "",
            "featured": bool(project.get("featured")),
            "technologies": project.get("technologies") or [],
            "domains": project.get("domains") or [],
            "capabilities": project.get("capabilities") or [],
            "practices": project.get("practices") or [],
            "ownership": project.get("ownership") or [],
            "evidence_score": 0,
            "evidence_level": "CURATED",
            "recency_days": None,
            "contributions": {"prs_merged": 0, "issues_closed": 0},
        }
        projects.append(row)
        for tech in row["technologies"]:
            skill_projects.setdefault(tech, set()).add(row["repo"])
        for item in row["practices"]:
            practices.setdefault(item, set()).add(row["repo"])
        for item in row["domains"]:
            domains.setdefault(item, set()).add(row["repo"])
        for item in row["capabilities"]:
            capabilities.setdefault(item, set()).add(row["repo"])
        for item in row["ownership"]:
            ownership.setdefault(item, set()).add(row["repo"])

    def aggregate(values: dict[str, set[str]]) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "name": key,
                    "project_count": len(repos),
                    "projects": sorted(repos),
                    "score": 0,
                    "level": "CURATED",
                    "recency_days": None,
                }
                for key, repos in values.items()
            ),
            key=lambda row: (-row["project_count"], row["name"].lower()),
        )

    available = {
        "technology": {item.lower() for project in projects for item in project["technologies"]},
        "domain": {item.lower() for project in projects for item in project["domains"]},
        "capability": {item.lower() for project in projects for item in project["capabilities"]},
        "practice": {item.lower() for project in projects for item in project["practices"]},
        "ownership": {item.lower() for project in projects for item in project["ownership"]},
    }
    fits = []
    for profile in config.get("assignment_profiles") or []:
        matched = []
        missing = []
        for signal in profile.get("signals") or []:
            category, value = next(iter(signal.items()))
            (matched if str(value).lower() in available[category] else missing).append({"category": category, "value": value})
        total = len(matched) + len(missing)
        fits.append({
            "id": profile["id"],
            "label": profile.get("label") or profile["id"],
            "score": round(len(matched) / total * 100) if total else 0,
            "matched": matched,
            "missing": missing,
        })
    fits.sort(key=lambda row: (-row["score"], row["label"]))

    return {
        "generated_at": generated_at,
        "collection_mode": "curated-config",
        "profile": config.get("profile") or {},
        "summary": {"tracked_projects": len(projects), "active_projects_90d": 0},
        "projects": sorted(projects, key=lambda row: (-int(row["featured"]), row["repo"])),
        "skills": aggregate(skill_projects),
        "domains": aggregate(domains),
        "capabilities": aggregate(capabilities),
        "practices": aggregate(practices),
        "ownership": aggregate(ownership),
        "assignment_fit": fits,
        "data_quality": {"errors": [], "limitations": []},
    }


def load_render_data(data_path: Path, config_path: Path) -> dict[str, Any]:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if data.get("skills") and data.get("projects"):
        return data
    generated_at = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    return bootstrap_from_config(load_yaml(config_path), generated_at)


def tech_badge(name: str) -> str:
    label = urllib.parse.quote(name.replace("-", "--"), safe="")
    logo = TECH_LOGOS.get(name)
    logo_param = f"&logo={urllib.parse.quote(logo, safe='')}" if logo else ""
    src = f"https://img.shields.io/badge/{label}-1F6FEB?style=flat-square{logo_param}&logoColor=white"
    return f'<img src="{src}" alt="{html.escape(name, quote=True)}" />'


def language_nav(ja: str, en: str, *, japanese: bool) -> str:
    ja_text = "**日本語**" if japanese else f"[日本語]({ja})"
    en_text = f"[English]({en})" if japanese else "**English**"
    return f'<p align="right">{ja_text} · {en_text}</p>'


def top_skill_names(data: dict[str, Any], limit: int = 10) -> list[str]:
    return [str(row["name"]) for row in (data.get("skills") or [])[:limit]]


def render_badges(names: list[str]) -> str:
    return '<p align="center">\n  ' + "\n  ".join(tech_badge(name) for name in names) + "\n</p>"


def translate_assignment(label: str) -> str:
    return ASSIGNMENT_JA.get(label, label)


def selected_projects(data: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
    projects = [row for row in data.get("projects") or [] if row.get("featured")]
    return (projects or list(data.get("projects") or []))[:limit]


def tech_category_rows(data: dict[str, Any]) -> list[tuple[str, str]]:
    available = set(top_skill_names(data, 100))
    rows = []
    for label, candidates in CATEGORY_TECH.items():
        values = [item for item in candidates if item in available]
        if values:
            rows.append((label, " / ".join(values[:6])))
    return rows


def render_readme_block_ja(data: dict[str, Any]) -> str:
    techs = top_skill_names(data, 10)
    domain_names = [DOMAIN_JA.get(str(row["name"]), str(row["name"])) for row in (data.get("capabilities") or data.get("domains") or [])[:8]]
    practices = [PRACTICE_JA.get(str(row["name"]), str(row["name"])) for row in (data.get("practices") or [])[:8]]
    fits = data.get("assignment_fit") or []
    fit_rows = "\n".join(f"| {translate_assignment(str(row['label']))} | {int(row.get('score', 0))}% |" for row in fits[:5])
    return "\n".join([
        README_START,
        "## ENGINEERING PROFILE",
        "",
        "### CORE TECHNOLOGIES",
        "",
        render_badges(techs),
        "",
        "### ENGINEERING RANGE",
        "",
        " ".join(f"`{name}`" for name in domain_names),
        "",
        "### HOW I BUILD",
        "",
        " ".join(f"`{name}`" for name in practices),
        "",
        "### ASSIGNMENT FIT",
        "",
        "| Area | Public evidence coverage |",
        "| --- | ---: |",
        fit_rows,
        "",
        '<p align="center"><sub><a href="./SKILL_SHEET.md">Skill Sheet</a> · <a href="./reports/developer-analytics.md">Developer Analytics</a> · <a href="./SKILL_SHEET.en.md">English</a></sub></p>',
        README_END,
    ])


def replace_readme_block(text: str, block: str) -> str:
    if README_START not in text or README_END not in text:
        raise ValueError("README Developer Analytics marker pair is missing")
    start = text.index(README_START)
    end = text.index(README_END, start) + len(README_END)
    return text[:start] + block + text[end:]


def role_ja(profile: dict[str, Any]) -> str:
    headline = str(profile.get("headline") or "Product-minded Full Stack Developer")
    if headline == "Product-minded Full Stack Developer":
        return "プロダクト志向のフルスタックエンジニア"
    return headline


def render_skill_sheet_ja(data: dict[str, Any]) -> str:
    profile = data.get("profile") or {}
    rows = tech_category_rows(data)
    projects = selected_projects(data)
    fits = data.get("assignment_fit") or []
    lines = [
        language_nav("./SKILL_SHEET.md", "./SKILL_SHEET.en.md", japanese=True),
        "# SKILL SHEET — いゔる。 / mizzz",
        "",
        "## PROFILE",
        "",
        f"- **Role:** {role_ja(profile)}",
        "- **Focus:** React / TypeScriptを軸にしたWeb開発、API / DB、Realtime AI、Discord、CI/CD・運用",
        "- **Style:** 実装だけで終わらせず、テスト・Docs・Deploy・運用まで一貫して扱う",
        "",
        "## CORE TECHNOLOGIES",
        "",
        render_badges(top_skill_names(data, 10)),
        "",
        "| Area | Technologies |",
        "| --- | --- |",
    ]
    lines += [f"| {label} | {values} |" for label, values in rows]
    lines += [
        "",
        "## STRENGTHS",
        "",
        "- FrontendからAPI / DB / WorkerまでつなげるFull-stack実装",
        "- Realtime AI・Discord VoiceなどRealtime処理の実装",
        "- 認証・権限・Secret管理・Least Privilegeを含むSecurity設計",
        "- CI / 自動テスト / Docker / Releaseを含むDelivery",
        "- Issue / PR / README / Docsを実装と同時に更新するRepository中心の開発",
        "",
        "## SELECTED PROJECTS",
        "",
        "| Project | Summary | Core Tech |",
        "| --- | --- | --- |",
    ]
    for project in projects:
        tech = " / ".join(project.get("technologies") or [])
        lines.append(f"| [{project.get('title')}]({project.get('url')}) | {project.get('description') or '-'} | {tech[:90]} |")
    lines += ["", "## ASSIGNMENT FIT", "", "| Area | Public evidence |", "| --- | ---: |"]
    lines += [f"| {translate_assignment(str(row['label']))} | {int(row.get('score', 0))}% |" for row in fits[:5]]
    lines += [
        "",
        "## CONTACT",
        "",
        f"- GitHub: https://github.com/{profile.get('github_login', 'mizzz-ivr')}",
        f"- Web: {profile.get('website', 'https://ivmz.ivrm.jp')}",
        f"- Email: {profile.get('contact', 'ivmz@ivrm.jp')}",
        "",
    ]
    return "\n".join(lines)


def render_skill_sheet_en(data: dict[str, Any]) -> str:
    profile = data.get("profile") or {}
    projects = selected_projects(data)
    fits = data.get("assignment_fit") or []
    lines = [
        language_nav("./SKILL_SHEET.md", "./SKILL_SHEET.en.md", japanese=False),
        "# SKILL SHEET — Ivoru / mizzz",
        "",
        "## PROFILE",
        "",
        f"- **Role:** {profile.get('headline', 'Product-minded Full Stack Developer')}",
        "- **Focus:** React / TypeScript web products, APIs / databases, realtime AI, Discord, CI/CD and operations",
        "- **Style:** End-to-end delivery from implementation through testing, documentation, deployment and operations",
        "",
        "## CORE TECHNOLOGIES",
        "",
        render_badges(top_skill_names(data, 10)),
        "",
        "## STRENGTHS",
        "",
        "- Full-stack delivery across frontend, API, database and worker layers",
        "- Realtime AI and Discord Voice integration",
        "- Security-conscious authentication, authorization and secret handling",
        "- CI, automated tests, Docker and release engineering",
        "- Repository-driven development with Issues, PRs, README and Docs kept current",
        "",
        "## SELECTED PROJECTS",
        "",
        "| Project | Summary |",
        "| --- | --- |",
    ]
    for project in projects:
        lines.append(f"| [{project.get('title')}]({project.get('url')}) | {project.get('description') or '-'} |")
    lines += ["", "## ASSIGNMENT FIT", "", "| Area | Coverage |", "| --- | ---: |"]
    lines += [f"| {row['label']} | {int(row.get('score', 0))}% |" for row in fits[:5]]
    lines += [
        "",
        "## CONTACT",
        "",
        f"- GitHub: https://github.com/{profile.get('github_login', 'mizzz-ivr')}",
        f"- Web: {profile.get('website', 'https://ivmz.ivrm.jp')}",
        f"- Email: {profile.get('contact', 'ivmz@ivrm.jp')}",
        "",
    ]
    return "\n".join(lines)


def render_report_ja(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    lines = [
        language_nav("./developer-analytics.md", "./developer-analytics.en.md", japanese=True),
        "# DEVELOPER ANALYTICS",
        "",
        f"Generated: `{data.get('generated_at', '')}`",
        "",
        "## SUMMARY",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Tracked public projects | {summary.get('tracked_projects', len(data.get('projects') or []))} |",
        f"| Active projects (90d) | {summary.get('active_projects_90d', '-')} |",
        f"| Technologies | {len(data.get('skills') or [])} |",
        f"| Engineering practices | {len(data.get('practices') or [])} |",
        "",
        "## TECHNOLOGY EVIDENCE",
        "",
        "| Technology | Evidence | Projects | Latest |",
        "| --- | --- | ---: | --- |",
    ]
    for row in (data.get("skills") or [])[:25]:
        latest = "未観測" if row.get("recency_days") is None else ("today" if row.get("recency_days") == 0 else f"{row['recency_days']}d ago")
        lines.append(f"| {row['name']} | {row.get('level', '-')} | {row.get('project_count', 0)} | {latest} |")
    lines += ["", "## ENGINEERING PRACTICES", "", "| Practice | Projects |", "| --- | ---: |"]
    for row in (data.get("practices") or [])[:20]:
        lines.append(f"| {PRACTICE_JA.get(str(row['name']), str(row['name']))} | {row.get('project_count', 0)} |")
    lines += ["", "## ASSIGNMENT FIT", "", "| Area | Coverage | Missing signal |", "| --- | ---: | --- |"]
    for row in data.get("assignment_fit") or []:
        missing = ", ".join(str(item.get("value")) for item in row.get("missing") or []) or "なし"
        lines.append(f"| {translate_assignment(str(row['label']))} | {int(row.get('score', 0))}% | {missing} |")
    lines += ["", "## PROJECTS", "", "| Project | Evidence | Core Tech |", "| --- | --- | --- |"]
    for project in data.get("projects") or []:
        tech = ", ".join(project.get("technologies") or [])[:120]
        lines.append(f"| [{project.get('repo')}]({project.get('url')}) | {project.get('evidence_level', '-')} | {tech} |")
    lines += [
        "",
        "## NOTES",
        "",
        "- 集計対象は公開GitHub上で確認できる情報のみです。",
        "- Private Repositoryや顧客情報は出力しません。",
        "- 公開Evidenceの不足は未経験を意味しません。",
        "",
    ]
    return "\n".join(lines)


def render_report_en(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    lines = [
        language_nav("./developer-analytics.md", "./developer-analytics.en.md", japanese=False),
        "# DEVELOPER ANALYTICS",
        "",
        f"Generated: `{data.get('generated_at', '')}`",
        "",
        "## SUMMARY",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Tracked public projects | {summary.get('tracked_projects', len(data.get('projects') or []))} |",
        f"| Active projects (90d) | {summary.get('active_projects_90d', '-')} |",
        f"| Technologies | {len(data.get('skills') or [])} |",
        f"| Engineering practices | {len(data.get('practices') or [])} |",
        "",
        "## TECHNOLOGY EVIDENCE",
        "",
        "| Technology | Evidence | Projects | Latest |",
        "| --- | --- | ---: | --- |",
    ]
    for row in (data.get("skills") or [])[:25]:
        latest = "not observed" if row.get("recency_days") is None else ("today" if row.get("recency_days") == 0 else f"{row['recency_days']}d ago")
        lines.append(f"| {row['name']} | {row.get('level', '-')} | {row.get('project_count', 0)} | {latest} |")
    lines += ["", "## ASSIGNMENT FIT", "", "| Area | Coverage | Missing public signal |", "| --- | ---: | --- |"]
    for row in data.get("assignment_fit") or []:
        missing = ", ".join(str(item.get("value")) for item in row.get("missing") or []) or "None"
        lines.append(f"| {row['label']} | {int(row.get('score', 0))}% | {missing} |")
    lines += ["", "## PROJECTS", "", "| Project | Evidence | Technologies |", "| --- | --- | --- |"]
    for project in data.get("projects") or []:
        tech = ", ".join(project.get("technologies") or [])[:120]
        lines.append(f"| [{project.get('repo')}]({project.get('url')}) | {project.get('evidence_level', '-')} | {tech} |")
    lines += [
        "",
        "## NOTES",
        "",
        "- Only public GitHub evidence is included.",
        "- Private repositories and confidential customer information are excluded.",
        "- Missing public evidence does not mean missing experience.",
        "",
    ]
    return "\n".join(lines)


def render_readme_en(data: dict[str, Any]) -> str:
    profile = data.get("profile") or {}
    projects = selected_projects(data)
    project_rows = "\n".join(f"- **[{project.get('title')}]({project.get('url')})** — {project.get('description') or ''}" for project in projects)
    return "\n".join([
        language_nav("./README.md", "./README.en.md", japanese=False),
        '<p align="center"><img src="./assets/profile-hero.png" width="100%" alt="ivmz developer profile" /></p>',
        "",
        "<h1 align=\"center\">Ivoru / mizzz</h1>",
        "",
        '<p align="center"><strong>Product-minded Full Stack Developer</strong><br/>Building web products, realtime AI, Discord systems, APIs, databases and operations end to end.</p>',
        "",
        "## CORE TECHNOLOGIES",
        "",
        render_badges(top_skill_names(data, 10)),
        "",
        "## ENGINEERING RANGE",
        "",
        "`Full Stack` `Web Product` `Realtime AI` `Discord` `Platform / Tooling` `DevOps / Observability`",
        "",
        "## SELECTED PROJECTS",
        "",
        project_rows,
        "",
        "## LINKS",
        "",
        f"- Website: {profile.get('website', 'https://ivmz.ivrm.jp')}",
        "- GitHub: https://github.com/mizzz-ivr",
        "- Community: https://ivrm.jp",
        f"- Contact: {profile.get('contact', 'ivmz@ivrm.jp')}",
        "",
        "For live development activity, see the [Japanese profile](./README.md).",
        "",
    ])


def write_outputs(data: dict[str, Any], *, readme: Path, readme_en: Path, skill_ja: Path, skill_en: Path, report_ja: Path, report_en: Path) -> None:
    readme.write_text(replace_readme_block(readme.read_text(encoding="utf-8"), render_readme_block_ja(data)).rstrip() + "\n", encoding="utf-8")
    readme_en.write_text(render_readme_en(data), encoding="utf-8")
    skill_ja.write_text(render_skill_sheet_ja(data), encoding="utf-8")
    skill_en.write_text(render_skill_sheet_en(data), encoding="utf-8")
    report_ja.parent.mkdir(parents=True, exist_ok=True)
    report_ja.write_text(render_report_ja(data), encoding="utf-8")
    report_en.write_text(render_report_en(data), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Japanese-first developer profile documents and English alternatives")
    parser.add_argument("--data", type=Path, default=Path("data/developer-analytics/latest.json"))
    parser.add_argument("--config", type=Path, default=Path(".github/developer-analytics.yml"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--readme-en", type=Path, default=Path("README.en.md"))
    parser.add_argument("--skill-ja", type=Path, default=Path("SKILL_SHEET.md"))
    parser.add_argument("--skill-en", type=Path, default=Path("SKILL_SHEET.en.md"))
    parser.add_argument("--report-ja", type=Path, default=Path("reports/developer-analytics.md"))
    parser.add_argument("--report-en", type=Path, default=Path("reports/developer-analytics.en.md"))
    args = parser.parse_args()
    data = load_render_data(args.data, args.config)
    write_outputs(data, readme=args.readme, readme_en=args.readme_en, skill_ja=args.skill_ja, skill_en=args.skill_en, report_ja=args.report_ja, report_en=args.report_en)
    print(f"Rendered developer profile: skills={len(data.get('skills') or [])} projects={len(data.get('projects') or [])}")


if __name__ == "__main__":
    main()
