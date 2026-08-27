from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import profile_signal_customize as custom


class ProfileSignalCustomizeTest(unittest.TestCase):
    def test_ignore_parser_supports_comments_blank_and_glob(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".profile-signalignore"
            path.write_text("# comment\n\nmizzz-ivr/tech-writing\nivRooom/archive-*\n", encoding="utf-8")
            patterns = custom.load_ignore_patterns(path)
        self.assertEqual(patterns, ["mizzz-ivr/tech-writing", "ivRooom/archive-*"])
        self.assertTrue(custom.repository_is_ignored("mizzz-ivr/tech-writing", patterns))
        self.assertTrue(custom.repository_is_ignored("ivRooom/archive-old", patterns))
        self.assertFalse(custom.repository_is_ignored("ivRooom/Herta", patterns))

    def test_filter_state_promotes_next_repository_when_focus_is_ignored(self) -> None:
        state = {
            "current_focus": {"repo": "mizzz-ivr/tech-writing", "score": 90, "share": 40, "events": 20, "stack": ["Python"]},
            "now_building": [
                {"repo": "mizzz-ivr/tech-writing", "score": 90, "share": 40, "events": 20},
                {"repo": "ivRooom/Herta", "score": 80, "share": 30, "events": 15},
            ],
            "activity_stream": [
                {"repo": "mizzz-ivr/tech-writing", "title": "article"},
                {"repo": "ivRooom/Herta", "title": "merge"},
            ],
        }
        filtered = custom.filter_state(state, ["mizzz-ivr/tech-writing"])
        self.assertEqual(filtered["current_focus"]["repo"], "ivRooom/Herta")
        self.assertEqual([item["repo"] for item in filtered["now_building"]], ["ivRooom/Herta"])
        self.assertEqual([item["repo"] for item in filtered["activity_stream"]], ["ivRooom/Herta"])

    def test_long_term_summary_aggregates_year_and_tracked_lifetime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for day, commits in (("2025-12-31", 2), ("2026-01-01", 3), ("2026-08-27", 5)):
                path = root / "data" / "activity" / day[:4] / day[5:7] / f"{day}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({
                    "date": day,
                    "metrics": {
                        "commits": commits,
                        "prs_opened": 1,
                        "issues_created": 1,
                        "issues_completed": 1,
                    },
                }), encoding="utf-8")
            summary = custom.long_term_summary(root, {"date": "2026-08-27"})
        self.assertEqual(summary["year"], 2026)
        self.assertEqual(summary["yearly"]["metrics"]["commits"], 8)
        self.assertEqual(summary["yearly"]["tracked_days"], 2)
        self.assertEqual(summary["lifetime"]["metrics"]["commits"], 10)
        self.assertEqual(summary["lifetime"]["tracked_days"], 3)
        self.assertEqual(summary["lifetime"]["first_date"], "2025-12-31")

    def test_customize_renders_hybrid_profile_and_long_term_recap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            readme = root / "README.md"
            state_path = root / "data/profile-signal-state.json"
            ignore = root / ".profile-signalignore"
            activity = root / "data/activity/2026/08/2026-08-27.json"
            readme.parent.mkdir(parents=True, exist_ok=True)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            activity.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text("\n\n".join(f"{start}\nold\n{end}" for start, end in custom.MARKERS.values()), encoding="utf-8")
            ignore.write_text("mizzz-ivr/tech-writing\n", encoding="utf-8")
            activity.write_text(json.dumps({
                "date": "2026-08-27",
                "metrics": {"commits": 1, "prs_opened": 2, "issues_created": 3, "issues_completed": 4},
            }), encoding="utf-8")
            state = {
                "schema_version": 4,
                "date": "2026-08-27",
                "timezone": "Asia/Tokyo",
                "status": {"label": "BUILDING", "symbol": "●", "last_activity_at": "2026-08-27T09:00:00Z"},
                "code_weather": {"label": "STORM", "icon": "🌩️"},
                "activity_total": 10,
                "streak": 3,
                "current_focus": {"repo": "mizzz-ivr/tech-writing", "score": 90, "share": 50, "events": 5, "stack": ["Python"]},
                "now_building": [{"repo": "ivRooom/Herta", "score": 80, "share": 30, "events": 4, "health": {"label": "HEALTHY"}, "ci": {"pass_rate": 100}}],
                "activity_stream": [{"repo": "ivRooom/Herta", "label": "PR", "title": "PR #1をマージ", "at": "2026-08-27T09:00:00Z"}],
                "ci_signal": {"label": "HEALTHY", "pass_rate": 100, "passed": 4, "evaluated": 4, "repos_with_signal": 1},
                "dev_recap": {
                    "tracked_from": "2026-08-27",
                    "weekly": {"metrics": {"commits": 1, "prs_opened": 2, "issues_completed": 4}},
                    "monthly": {"metrics": {"commits": 1, "prs_opened": 2, "issues_completed": 4, "activity_total": 10}},
                },
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            custom.customize(root, readme, state_path, ignore)
            rendered = readme.read_text(encoding="utf-8")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("## CURRENT FOCUS // What is moving now", rendered)
            self.assertIn("weighted activity", rendered)
            self.assertIn("## TODAY // Activity overview", rendered)
            self.assertIn("### QUALITY SIGNAL // Last 7 days", rendered)
            self.assertIn("YEARLY SUMMARY // 2026", rendered)
            self.assertIn("LIFETIME SUMMARY // Tracked history", rendered)
            self.assertNotIn("加重アクティビティ", rendered)
            self.assertNotIn("mizzz-ivr/tech-writing", rendered)
            self.assertEqual(persisted["current_focus"]["repo"], "ivRooom/Herta")
            self.assertEqual(persisted["tracked_summary"]["lifetime"]["tracked_days"], 1)


if __name__ == "__main__":
    unittest.main()
