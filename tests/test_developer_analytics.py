from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import developer_analytics as da


class DeveloperAnalyticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "version": 1,
            "profile": {"github_login": "octocat", "display_name": "Octo Cat"},
            "projects": [
                {
                    "repo": "octocat/hello-world",
                    "public": True,
                    "title": "Hello",
                    "technologies": ["TypeScript", "React"],
                    "domains": ["web"],
                    "capabilities": ["frontend"],
                    "practices": ["pr-based"],
                    "ownership": ["implementation"],
                    "evidence": [{"label": "README", "url": "https://github.com/octocat/hello-world"}],
                },
                {
                    "repo": "octocat/api",
                    "public": True,
                    "title": "API",
                    "technologies": ["TypeScript", "PostgreSQL"],
                    "domains": ["backend"],
                    "capabilities": ["backend-api"],
                    "practices": ["ci-cd", "automated-testing"],
                    "ownership": ["implementation", "testing"],
                    "evidence": [{"label": "README", "url": "https://github.com/octocat/api"}],
                },
            ],
            "assignment_profiles": [
                {
                    "id": "fullstack",
                    "label": "Full-stack",
                    "signals": [
                        {"technology": "TypeScript"},
                        {"capability": "frontend"},
                        {"capability": "backend-api"},
                        {"practice": "ci-cd"},
                    ],
                }
            ],
        }

    def test_config_rejects_non_public_project(self) -> None:
        invalid = json.loads(json.dumps(self.config))
        invalid["projects"][0]["public"] = False
        with self.assertRaises(da.ConfigError):
            da.validate_config(invalid)

    def test_delivery_signal_detection(self) -> None:
        signals = da.detect_delivery_signals(
            [
                ".github/workflows/ci.yml",
                "tests/test_api.py",
                "docs/architecture.md",
                "docker-compose.yml",
                "supabase/migrations/001.sql",
                "src/logger.ts",
            ]
        )
        self.assertTrue(signals["ci_cd"])
        self.assertTrue(signals["tests"])
        self.assertTrue(signals["documentation"])
        self.assertTrue(signals["containerization"])
        self.assertTrue(signals["schema_migrations"])
        self.assertTrue(signals["observability"])

    def test_offline_aggregation_and_assignment_fit(self) -> None:
        projects = [da.collect_project_offline(project) for project in self.config["projects"]]
        analytics = da.build_analytics(
            self.config,
            projects,
            generated_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
            collection_mode="offline-config",
        )
        typescript = next(row for row in analytics["skills"] if row["name"] == "TypeScript")
        self.assertEqual(typescript["project_count"], 2)
        self.assertEqual(analytics["assignment_fit"][0]["score"], 100)

    def test_readme_block_replacement_is_idempotent(self) -> None:
        block = f"{da.README_START}\nhello\n{da.README_END}"
        original = "before\n\n## PUBLIC BUILDS // Featured\nafter\n"
        first = da.replace_readme_block(original, block)
        second = da.replace_readme_block(first, block)
        self.assertEqual(first, second)
        self.assertEqual(first.count(da.README_START), 1)
        self.assertEqual(first.count(da.README_END), 1)

    def test_outputs_generate_skill_sheet_and_snapshot(self) -> None:
        projects = [da.collect_project_offline(project) for project in self.config["projects"]]
        analytics = da.build_analytics(
            self.config,
            projects,
            generated_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
            collection_mode="offline-config",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            readme = root / "README.md"
            readme.write_text("intro\n\n## PUBLIC BUILDS // Featured\nbody\n", encoding="utf-8")
            da.write_outputs(
                analytics,
                output=root / "data/latest.json",
                report=root / "reports/developer.md",
                skill_sheet=root / "SKILL_SHEET.md",
                readme=readme,
                snapshot_dir=root / "data/snapshots",
            )
            self.assertTrue((root / "SKILL_SHEET.md").exists())
            self.assertIn("Skill Sheet", (root / "SKILL_SHEET.md").read_text(encoding="utf-8"))
            self.assertIn(da.README_START, readme.read_text(encoding="utf-8"))
            self.assertEqual(len(list((root / "data/snapshots").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
