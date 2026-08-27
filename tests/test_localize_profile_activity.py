from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import localize_profile_activity as localize


class LocalizeProfileActivityTest(unittest.TestCase):
    def test_known_event_titles_are_localized(self) -> None:
        cases = {
            "1 commit pushed to main": "mainへ1コミットをPush",
            "3 commits pushed to feature/foo": "feature/fooへ3コミットをPush",
            "PR merged #347": "PR #347をマージ",
            "Opened PR #42": "PR #42を作成",
            "Opened issue #23": "Issue #23を作成",
            "Closed issue #56": "Issue #56を完了",
            "Released v1.2.0": "v1.2.0をリリース",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(localize.localize_event_title(source), expected)

    def test_unknown_event_title_is_preserved(self) -> None:
        self.assertEqual(localize.localize_event_title("Starred repository"), "Starred repository")

    def test_only_activity_stream_anchor_text_is_changed(self) -> None:
        readme = """before PR merged #999
<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->
<a href="https://github.com/x/y">x/y</a> — <a href="https://github.com/x/y">PR merged #12</a>
<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->
after PR merged #999
"""
        rendered = localize.localize_readme(readme)
        self.assertIn(">PR #12をマージ</a>", rendered)
        self.assertEqual(rendered.count("PR merged #999"), 2)
        self.assertIn(">x/y</a>", rendered)


if __name__ == "__main__":
    unittest.main()
