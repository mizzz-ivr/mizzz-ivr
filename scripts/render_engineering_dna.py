from __future__ import annotations

import argparse
import html
import math
import re
from pathlib import Path
from typing import Any

from render_developer_profile import load_render_data

SECTION_START = "<!-- ENGINEERING-DNA:START -->"
SECTION_END = "<!-- ENGINEERING-DNA:END -->"

ASSIGNMENT_AXES = (
    ("FULL STACK", "Full-stack Product Development"),
    ("REALTIME AI", "Realtime AI / Voice"),
    ("PLATFORM / TOOLING", "Platform / Developer Tooling"),
    ("DEVOPS / OPS", "DevOps / Observability"),
)

QUALITY_SIGNALS = (
    ("practice", "security-by-design"),
    ("practice", "automated-testing"),
    ("practice", "least-privilege"),
    ("practice", "fail-close"),
    ("practice", "accessibility-first"),
    ("practice", "observability"),
    ("practice", "release-automation"),
    ("practice", "ci-cd"),
    ("ownership", "security"),
    ("ownership", "testing"),
)


def _available_names(data: dict[str, Any], key: str) -> set[str]:
    return {str(row.get("name") or "").lower() for row in (data.get(key) or [])}


def engineering_dna_scores(data: dict[str, Any]) -> list[tuple[str, int]]:
    fit_by_label = {
        str(row.get("label") or ""): max(0, min(100, int(row.get("score", 0) or 0)))
        for row in (data.get("assignment_fit") or [])
    }
    scores = [(label, fit_by_label.get(source_label, 0)) for label, source_label in ASSIGNMENT_AXES]

    practices = _available_names(data, "practices")
    ownership = _available_names(data, "ownership")
    matched = 0
    for category, signal in QUALITY_SIGNALS:
        haystack = practices if category == "practice" else ownership
        if signal in haystack:
            matched += 1
    quality_score = round(matched / len(QUALITY_SIGNALS) * 100) if QUALITY_SIGNALS else 0
    scores.append(("SECURITY / QUALITY", quality_score))
    return scores


def _point(cx: float, cy: float, radius: float, fraction: float, index: int) -> tuple[float, float]:
    angle = math.radians(-90 + index * 72)
    return cx + math.cos(angle) * radius * fraction, cy + math.sin(angle) * radius * fraction


def _points(values: list[float], *, cx: float, cy: float, radius: float) -> str:
    return " ".join(
        f"{x:.1f},{y:.1f}"
        for index, value in enumerate(values)
        for x, y in [_point(cx, cy, radius, value, index)]
    )


def render_svg(scores: list[tuple[str, int]]) -> str:
    if len(scores) != 5:
        raise ValueError("ENGINEERING DNA requires exactly five axes")

    width, height = 920, 420
    cx, cy, radius = 460.0, 210.0, 125.0
    ring_polygons = []
    for level in (0.25, 0.5, 0.75, 1.0):
        ring_polygons.append(f'<polygon class="grid" points="{_points([level] * 5, cx=cx, cy=cy, radius=radius)}" />')

    axes = []
    labels = []
    for index, (label, score) in enumerate(scores):
        x, y = _point(cx, cy, radius, 1.0, index)
        axes.append(f'<line class="axis" x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" />')

        lx, ly = _point(cx, cy, radius, 1.33, index)
        anchor = "middle"
        if lx < cx - 20:
            anchor = "end"
        elif lx > cx + 20:
            anchor = "start"
        labels.append(
            f'<text class="axis-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">'
            f'<tspan x="{lx:.1f}" dy="0">{html.escape(label)}</tspan>'
            f'<tspan class="score" x="{lx:.1f}" dy="18">{score}% evidence</tspan>'
            '</text>'
        )

    polygon = _points([score / 100 for _, score in scores], cx=cx, cy=cy, radius=radius)
    value_points = []
    for index, (_, score) in enumerate(scores):
        x, y = _point(cx, cy, radius, score / 100, index)
        value_points.append(f'<circle class="point" cx="{x:.1f}" cy="{y:.1f}" r="4.5" />')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Engineering DNA public evidence profile</title>
  <desc id="desc">Five-axis public evidence profile generated from Developer Analytics. This is evidence coverage, not a proficiency score.</desc>
  <style>
    .title {{ fill: #24292f; font: 700 16px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: .08em; }}
    .subtitle {{ fill: #57606a; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .grid {{ fill: none; stroke: #d0d7de; stroke-width: 1; }}
    .axis {{ stroke: #d0d7de; stroke-width: 1; }}
    .profile {{ fill: #8b5cf6; fill-opacity: .20; stroke: #8b5cf6; stroke-width: 3; stroke-linejoin: round; }}
    .point {{ fill: #8b5cf6; }}
    .axis-label {{ fill: #24292f; font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: .03em; }}
    .score {{ fill: #6e7781; font-weight: 500; letter-spacing: 0; }}
    .note {{ fill: #6e7781; font: 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    @media (prefers-color-scheme: dark) {{
      .title, .axis-label {{ fill: #f0f6fc; }}
      .subtitle, .score, .note {{ fill: #8c959f; }}
      .grid, .axis {{ stroke: #30363d; }}
      .profile {{ fill: #a78bfa; fill-opacity: .20; stroke: #a78bfa; }}
      .point {{ fill: #a78bfa; }}
    }}
  </style>
  <text class="title" x="24" y="30">ENGINEERING DNA · PUBLIC EVIDENCE PROFILE</text>
  <text class="subtitle" x="24" y="50">Developer Analyticsから自動生成した公開Evidenceの5軸プロファイル</text>
  {''.join(ring_polygons)}
  {''.join(axes)}
  <polygon class="profile" points="{polygon}" />
  {''.join(value_points)}
  {''.join(labels)}
  <text class="note" x="460" y="402" text-anchor="middle">Evidence coverage, not proficiency · source: public GitHub repositories and engineering practices</text>
</svg>
'''


def render_section(*, japanese: bool) -> str:
    note = (
        '公開Repository / Engineering Practice / Assignment Evidenceから自動生成。詳細は <a href="./reports/developer-analytics.md">Developer Analytics</a>。'
        if japanese
        else 'Generated from public repositories, engineering practices and assignment evidence. See <a href="./reports/developer-analytics.en.md">Developer Analytics</a> for details.'
    )
    return "\n".join([
        SECTION_START,
        "## ENGINEERING DNA // Public evidence profile",
        "",
        '<p align="center"><img src="./assets/engineering-dna.svg" width="100%" alt="Engineering DNA public evidence profile" /></p>',
        "",
        f'<p align="center"><sub>{note}</sub></p>',
        SECTION_END,
    ])


def upsert_section(text: str, section: str, *, before_heading: str) -> str:
    if SECTION_START in text and SECTION_END in text:
        pattern = re.compile(re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END), re.DOTALL)
        return pattern.sub(section, text, count=1)

    marker = f"## {before_heading}"
    index = text.find(marker)
    if index < 0:
        raise ValueError(f"README insertion heading not found: {before_heading}")
    prefix = text[:index].rstrip()
    suffix = text[index:].lstrip()
    return f"{prefix}\n\n{section}\n\n---\n\n{suffix}"


def write_outputs(
    data: dict[str, Any],
    *,
    readme: Path,
    readme_en: Path,
    output: Path,
) -> list[tuple[str, int]]:
    scores = engineering_dna_scores(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(scores), encoding="utf-8")

    readme.write_text(
        upsert_section(readme.read_text(encoding="utf-8"), render_section(japanese=True), before_heading="PUBLIC BUILDS").rstrip() + "\n",
        encoding="utf-8",
    )
    readme_en.write_text(
        upsert_section(readme_en.read_text(encoding="utf-8"), render_section(japanese=False), before_heading="SELECTED PROJECTS").rstrip() + "\n",
        encoding="utf-8",
    )
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Render ENGINEERING DNA from Developer Analytics evidence")
    parser.add_argument("--data", type=Path, default=Path("data/developer-analytics/latest.json"))
    parser.add_argument("--config", type=Path, default=Path(".github/developer-analytics.yml"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--readme-en", type=Path, default=Path("README.en.md"))
    parser.add_argument("--output", type=Path, default=Path("assets/engineering-dna.svg"))
    args = parser.parse_args()

    data = load_render_data(args.data, args.config)
    scores = write_outputs(data, readme=args.readme, readme_en=args.readme_en, output=args.output)
    print("Rendered ENGINEERING DNA:", ", ".join(f"{label}={score}%" for label, score in scores))


if __name__ == "__main__":
    main()
