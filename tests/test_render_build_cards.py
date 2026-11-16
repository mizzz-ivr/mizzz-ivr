import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_build_cards as cards


PROJECT = {
    "repo": "ivRooom/Herta",
    "public": True,
    "featured": True,
    "title": "Herta",
    "summary": "Discord Community Operating System。NestJS API / Next.js Studio / Discord Bot / BullMQ Worker / Plugin Runtimeを含むモノレポ。",
    "technologies": ["TypeScript", "Node.js", "NestJS", "Next.js", "React", "PostgreSQL"],
}


class RenderBuildCardsTest(unittest.TestCase):
    def test_wrap_text_counts_full_width_glyphs(self) -> None:
        lines = cards.wrap_text("あ" * 40, max_units=58, max_lines=3)
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(lines[0]), 29)

    def test_wrap_text_truncates_with_ellipsis(self) -> None:
        lines = cards.wrap_text("あ" * 200, max_units=58, max_lines=3)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))

    def test_render_card_is_valid_svg_with_content(self) -> None:
        svg = cards.render_card(PROJECT, "#0969da")
        ET.fromstring(svg)
        self.assertIn("Herta", svg)
        self.assertIn("github.com/ivRooom/Herta", svg)
        self.assertIn("TypeScript", svg)
        self.assertIn("#0969da", svg)

    def test_chip_layout_stops_before_overflow(self) -> None:
        chips = cards._chip_layout(["A" * 40] * 6, max_width=400)
        self.assertLess(len(chips), 6)
        for _name, x, width in chips:
            self.assertLessEqual(x + width, 400)

    def test_section_links_cards_and_is_idempotent(self) -> None:
        projects = [dict(PROJECT, repo=repo) for repo in cards.CURATED_REPOS]
        section = cards.render_section(projects)
        self.assertIn("./assets/build-herta.svg", section)
        self.assertIn("https://github.com/ivRooom/ivrm-dashboard", section)
        readme = f"# Profile\n\n{section}\n\n---\n\n## DEV RECAP\nbody\n"
        replaced = cards.replace_section(readme, section)
        self.assertEqual(replaced, readme)
        self.assertIn("## DEV RECAP", replaced)

    def test_replace_section_swaps_old_table(self) -> None:
        projects = [dict(PROJECT, repo=repo) for repo in cards.CURATED_REPOS]
        section = cards.render_section(projects)
        old = "# Profile\n\n## PUBLIC BUILDS\n\n<table><tr><td>old</td></tr></table>\n\n---\n\n## DEV RECAP\n"
        replaced = cards.replace_section(old, section)
        self.assertNotIn("old", replaced)
        self.assertIn("build-herta.svg", replaced)
        self.assertTrue(replaced.endswith("## DEV RECAP\n"))

    def test_load_projects_uses_real_config(self) -> None:
        root = Path(__file__).resolve().parents[1]
        projects = cards.load_projects(root / ".github" / "developer-analytics.yml")
        self.assertEqual([p["repo"] for p in projects], cards.CURATED_REPOS)


if __name__ == "__main__":
    unittest.main()
