"""Render FEATURED BUILDS SVG cards for the profile README.

Generates one SVG card per curated public build (``assets/build-<slug>.svg``)
from ``.github/developer-analytics.yml`` and rewrites the ``## PUBLIC BUILDS``
section of the README as a 2x2 table of linked card images. Card data
(title / summary / technologies) always comes from the analytics config; this
script only owns the curation order and the card layout, in the same spirit
as ``render_engineering_dna.py`` owning the Engineering DNA SVG.

Run by the Developer Analytics workflow after the other renderers so the
cards refresh together with the analytics snapshot.
"""

from __future__ import annotations

import argparse
import html
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

# PUBLIC BUILDS curation: the four builds showcased on the profile, in
# display order. Data for each entry is read from the analytics config.
CURATED_REPOS = [
    "ivRooom/Herta",
    "mizzz-ivr/roomate-voice",
    "mizzz-ivr/ivmz-home",
    "ivRooom/ivrm-dashboard",
]
ACCENTS = ["#0969da", "#8250df", "#1a7f37", "#bf8700"]

CARD_WIDTH = 440
CARD_HEIGHT = 176
FONT_STACK = "-apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif"


def text_units(text: str) -> float:
    """Approximate rendered width: full-width glyphs count 2, others 1."""
    return sum(2.0 if unicodedata.east_asian_width(char) in ("W", "F") else 1.0 for char in text)


def wrap_text(text: str, max_units: float, max_lines: int) -> list[str]:
    """Greedy word-aware wrapping; a single over-long word falls back to
    character wrapping. Adds an ellipsis when content is left over."""
    words = text.replace("\n", " ").split(" ")
    lines: list[str] = []
    current = ""
    truncated = False
    index = 0
    while index < len(words):
        word = words[index]
        candidate = f"{current} {word}".strip() if current else word
        if text_units(candidate) <= max_units:
            current = candidate
            index += 1
            continue
        if current:
            lines.append(current)
            current = ""
            if len(lines) == max_lines:
                truncated = True
                break
            continue
        while text_units(word) > max_units:
            cut = 0
            while cut < len(word) and text_units(word[: cut + 1]) <= max_units:
                cut += 1
            lines.append(word[:cut])
            word = word[cut:]
            if len(lines) == max_lines:
                truncated = bool(word) or index < len(words) - 1
                break
        current = word
        index += 1
        if len(lines) == max_lines:
            truncated = truncated or bool(current) or index < len(words)
            break
    if not truncated and current and len(lines) < max_lines:
        lines.append(current)
    elif current and len(lines) >= max_lines:
        truncated = True
    if not truncated and len(lines) >= 2 and text_units(lines[-1]) < 12 and " " not in lines[-1]:
        # Avoid a tiny orphan line when a long unbroken word was char-wrapped:
        # re-split the last two lines evenly.
        tail = lines[-2] + lines[-1]
        half = text_units(tail) / 2
        cut = 0
        accrued = 0.0
        while cut < len(tail):
            step = 2.0 if unicodedata.east_asian_width(tail[cut]) in ("W", "F") else 1.0
            if accrued + step > half:
                break
            accrued += step
            cut += 1
        if 0 < cut < len(tail):
            lines[-2], lines[-1] = tail[:cut], tail[cut:]
    if truncated and lines:
        lines[-1] = lines[-1].rstrip("、。 ") + "…"
    return lines[:max_lines]


def _chip_layout(technologies: list[str], max_width: float = 400.0) -> list[tuple[str, float, float]]:
    chips: list[tuple[str, float, float]] = []
    x = 0.0
    for name in technologies:
        width = text_units(name) * 6.4 + 16
        if x + width > max_width:
            break
        chips.append((name, x, width))
        x += width + 8
    return chips


def render_card(project: dict[str, Any], accent: str) -> str:
    title = html.escape(str(project.get("title") or project.get("repo") or ""))
    repo = str(project.get("repo") or "")
    summary_lines = wrap_text(str(project.get("summary") or ""), max_units=58, max_lines=3)
    technologies = [str(name) for name in project.get("technologies") or []][:6]
    chips = _chip_layout(technologies)
    summary_svg = "\n".join(
        f'  <text class="summary" x="20" y="{88 + index * 19}">{html.escape(line)}</text>'
        for index, line in enumerate(summary_lines)
    )
    chips_svg = "\n".join(
        f'  <g transform="translate({20 + x:.0f},140)"><rect width="{width:.0f}" height="20" rx="10" class="chip-bg"/>'
        f'<text class="chip" x="{width / 2:.0f}" y="14" text-anchor="middle">{html.escape(name)}</text></g>'
        for name, x, width in chips
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{title} — build card</title>
  <desc id="desc">{html.escape(str(project.get("summary") or ""))}</desc>
  <style>
    .title {{ fill: #1f2328; font: 700 20px {FONT_STACK}; }}
    .repo {{ fill: #57606a; font: 12px {FONT_STACK}; }}
    .summary {{ fill: #24292f; font: 13px {FONT_STACK}; }}
    .chip {{ fill: #0969da; font: 600 11px {FONT_STACK}; }}
    .chip-bg {{ fill: #ddf4ff; }}
  </style>
  <defs>
    <clipPath id="card-clip"><rect x="1" y="1" width="{CARD_WIDTH - 2}" height="{CARD_HEIGHT - 2}" rx="12"/></clipPath>
  </defs>
  <rect x="1" y="1" width="{CARD_WIDTH - 2}" height="{CARD_HEIGHT - 2}" rx="12" fill="#ffffff" stroke="#d0d7de"/>
  <g clip-path="url(#card-clip)"><rect x="0" y="0" width="{CARD_WIDTH}" height="6" fill="{accent}"/></g>
  <text class="title" x="20" y="46">{title}</text>
  <text class="repo" x="20" y="66">github.com/{html.escape(repo)}</text>
{summary_svg}
{chips_svg}
</svg>
'''


def slug_for(repo: str) -> str:
    return repo.split("/", 1)[-1].lower()


def load_projects(config_path: Path) -> list[dict[str, Any]]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    by_repo = {str(project.get("repo")): project for project in config.get("projects") or []}
    projects = []
    for repo in CURATED_REPOS:
        project = by_repo.get(repo)
        if project is None:
            raise ValueError(f"Curated repo missing from analytics config: {repo}")
        if project.get("public") is not True:
            raise ValueError(f"Curated repo is not public in analytics config: {repo}")
        projects.append(project)
    return projects


def render_section(projects: list[dict[str, Any]]) -> str:
    cells = []
    for project in projects:
        repo = str(project.get("repo") or "")
        title = html.escape(str(project.get("title") or repo))
        summary = html.escape(str(project.get("summary") or "")[:90])
        cells.append(
            f'    <td width="50%" valign="top"><a href="https://github.com/{repo}">'
            f'<img src="./assets/build-{slug_for(repo)}.svg" width="100%" alt="{title} — {summary}" /></a></td>'
        )
    rows = "\n".join(
        "  <tr>\n" + "\n".join(cells[index : index + 2]) + "\n  </tr>" for index in range(0, len(cells), 2)
    )
    return f"## PUBLIC BUILDS\n\n<table>\n{rows}\n</table>"


def replace_section(readme: str, section: str) -> str:
    heading = re.compile(r"^## PUBLIC BUILDS\s*$", re.MULTILINE)
    match = heading.search(readme)
    if match is None:
        raise ValueError("README missing PUBLIC BUILDS heading")
    rest = readme[match.end() :]
    boundary = re.compile(r"\n---\n|\n## ", re.MULTILINE)
    end_match = boundary.search(rest)
    if end_match is None:
        return readme[: match.start()] + section + "\n"
    segment = rest[end_match.start() :].lstrip("\n")
    return readme[: match.start()] + section + "\n\n" + segment


def main() -> None:
    parser = argparse.ArgumentParser(description="Render PUBLIC BUILDS SVG cards")
    parser.add_argument("--config", type=Path, default=Path(".github/developer-analytics.yml"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--assets", type=Path, default=Path("assets"))
    args = parser.parse_args()
    projects = load_projects(args.config)
    args.assets.mkdir(parents=True, exist_ok=True)
    for index, project in enumerate(projects):
        slug = slug_for(str(project.get("repo") or ""))
        (args.assets / f"build-{slug}.svg").write_text(
            render_card(project, ACCENTS[index % len(ACCENTS)]), encoding="utf-8"
        )
    readme = args.readme.read_text(encoding="utf-8")
    args.readme.write_text(replace_section(readme, render_section(projects)), encoding="utf-8")
    print("Build cards rendered:", ", ".join(slug_for(str(p.get("repo") or "")) for p in projects))


if __name__ == "__main__":
    main()
