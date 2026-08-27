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

    def test_customize_renders_japanese_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            readme = root / "README.md"
            state_path = root / "data/profile-signal-state.json"
            ignore = root / ".profile-signalignore"
            activity = root / "data/activity/2026/08/2026-08-27.json"
            svg = root / "assets/dev-pulse.svg"
            readme.parent.mkdir(parents=True, exist_ok=True)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            activity.parent.mkdir(parents=True, exist_ok=True)
            svg.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text("\n\n".join(f"{start}\nold\n{end}" for start, end in custom.MARKERS.values()), encoding="utf-8")
            ignore.write_text("mizzz-ivr/tech-writing\n", encoding="utf-8")
            activity.write_text(json.dumps({"date": "2026-08-27", "metrics": {"commits": 1, "prs_opened": 2, "issues_created": 3, "issues_completed": 4}}), encoding="utf-8")
            svg.write_text("<svg><text>DEV PULSE · LAST 7 DAYS</text></svg>", encoding="utf-8")
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
                "activity_stream": [{"repo": "ivRooom/Herta", "label": "PR", "title": "merged", "at": "2026-08-27T09:00:00Z"}],
                "dev_recap": {"active_days": 1, "weekly": {"metrics": {}}, "monthly": {"metrics": {}}},
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            custom.customize(root, readme, state_path, ignore)
            rendered = readme.read_text(encoding="utf-8")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("## 現在のフォーカス", rendered)
            self.assertIn("## 今日の活動", rendered)
            self.assertNotIn("mizzz-ivr/tech-writing", rendered)
            self.assertEqual(persisted["current_focus"]["repo"], "ivRooom/Herta")
            self.assertIn("開発パルス · 直近7日", svg.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
