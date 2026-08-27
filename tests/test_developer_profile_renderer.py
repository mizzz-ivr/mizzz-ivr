from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_developer_profile as renderer


class DeveloperProfileRendererTest(unittest.TestCase):
    def sample_data(self) -> dict:
        return {
            "generated_at": "2026-08-27T00:00:00Z",
            "profile": {
                "github_login": "mizzz-ivr",
                "headline": "Product-minded Full Stack Developer",
                "website": "https://ivmz.ivrm.jp",
                "contact": "ivmz@ivrm.jp",
            },
            "summary": {"tracked_projects": 2, "active_projects_90d": 2},
            "skills": [
                {"name": "TypeScript", "project_count": 2, "level": "REPEATED", "recency_days": 0},
                {"name": "React", "project_count": 2, "level": "REPEATED", "recency_days": 0},
                {"name": "Docker", "project_count": 1, "level": "ESTABLISHED", "recency_days": 1},
            ],
            "domains": [{"name": "web-product", "project_count": 1}],
            "capabilities": [
                {"name": "full-stack", "project_count": 2},
                {"name": "backend-api", "project_count": 1},
            ],
            "practices": [
                {"name": "repository-driven-development", "project_count": 2},
                {"name": "automated-testing", "project_count": 1},
            ],
            "ownership": [],
            "assignment_fit": [
                {"label": "Full-stack Product Development", "score": 100, "missing": []},
                {"label": "DevOps / Observability", "score": 86, "missing": [{"value": "observability"}]},
            ],
            "projects": [
                {
                    "repo": "ivRooom/Herta",
                    "title": "Herta",
                    "url": "https://github.com/ivRooom/Herta",
                    "description": "Discord Community Platform",
                    "featured": True,
                    "technologies": ["TypeScript", "React", "Docker"],
                    "evidence_level": "STRONG",
                },
                {
                    "repo": "mizzz-ivr/ivmz-home",
                    "title": "ivmz-home",
                    "url": "https://github.com/mizzz-ivr/ivmz-home",
                    "description": "Portfolio Platform",
                    "featured": True,
                    "technologies": ["TypeScript", "React"],
                    "evidence_level": "REPEATED",
                },
            ],
        }

    def test_readme_block_uses_english_headings_and_logo_badges(self) -> None:
        block = renderer.render_readme_block_ja(self.sample_data())
        self.assertIn("## ENGINEERING PROFILE", block)
        self.assertIn("### CORE TECHNOLOGIES", block)
        self.assertIn("### HOW I BUILD", block)
        self.assertIn("logo=typescript", block)
        self.assertNotIn("エンジニアリングプロフィール", block)
        self.assertNotIn("Evidence Scoreは能力点", block)

    def test_skill_sheet_is_concise_hybrid_and_bilingual(self) -> None:
        ja = renderer.render_skill_sheet_ja(self.sample_data())
        en = renderer.render_skill_sheet_en(self.sample_data())
        self.assertIn("# SKILL SHEET", ja)
        self.assertIn("## STRENGTHS", ja)
        self.assertIn("プロダクト志向のフルスタックエンジニア", ja)
        self.assertIn("[English](./SKILL_SHEET.en.md)", ja)
        self.assertNotIn("## 技術Evidence", ja)
        self.assertIn("# SKILL SHEET", en)
        self.assertLess(len(ja.splitlines()), 90)

    def test_report_uses_english_headings_with_japanese_notes(self) -> None:
        report = renderer.render_report_ja(self.sample_data())
        self.assertIn("# DEVELOPER ANALYTICS", report)
        self.assertIn("## TECHNOLOGY EVIDENCE", report)
        self.assertIn("## ENGINEERING PRACTICES", report)
        self.assertIn("集計対象は公開GitHub", report)

    def test_write_outputs_creates_language_variants(self) -> None:
        data = self.sample_data()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            readme = root / "README.md"
            readme.write_text(f"before\n{renderer.README_START}\nold\n{renderer.README_END}\nafter\n", encoding="utf-8")
            renderer.write_outputs(
                data,
                readme=readme,
                readme_en=root / "README.en.md",
                skill_ja=root / "SKILL_SHEET.md",
                skill_en=root / "SKILL_SHEET.en.md",
                report_ja=root / "reports/developer-analytics.md",
                report_en=root / "reports/developer-analytics.en.md",
            )
            self.assertIn("## ENGINEERING PROFILE", readme.read_text(encoding="utf-8"))
            self.assertTrue((root / "README.en.md").exists())
            self.assertTrue((root / "SKILL_SHEET.en.md").exists())
            self.assertTrue((root / "reports/developer-analytics.en.md").exists())
            self.assertIn("# DEVELOPER ANALYTICS", (root / "reports/developer-analytics.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
