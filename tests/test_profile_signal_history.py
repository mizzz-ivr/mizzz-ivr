from __future__ import annotations

import unittest
from datetime import date

from scripts.profile_signal_history import (
    achievement_engine,
    aggregate_snapshots,
    longest_streak,
    render_recap,
)


class ProfileSignalHistoryTests(unittest.TestCase):
    def snapshot(
        self,
        day: str,
        commits: int = 0,
        prs: int = 0,
        created: int = 0,
        done: int = 0,
    ) -> dict[str, object]:
        return {
            "date": day,
            "metrics": {
                "commits": commits,
                "prs_opened": prs,
                "issues_created": created,
                "issues_completed": done,
            },
        }

    def test_aggregate_snapshots_sums_only_period(self) -> None:
        snapshots = [
            self.snapshot("2026-08-24", commits=5),
            self.snapshot("2026-08-25", commits=10, prs=2, done=1),
            self.snapshot("2026-08-26", commits=20, prs=3, created=1, done=2),
        ]
        report = aggregate_snapshots(
            snapshots,
            date(2026, 8, 25),
            date(2026, 8, 31),
            "2026-W35",
        )
        self.assertEqual(report["coverage"]["tracked_days"], 2)
        self.assertEqual(report["coverage"]["active_days"], 2)
        self.assertEqual(report["metrics"]["commits"], 30)
        self.assertEqual(report["metrics"]["prs_opened"], 5)
        self.assertEqual(report["metrics"]["issues_completed"], 3)
        self.assertEqual(report["metrics"]["activity_total"], 39)

    def test_longest_streak_stops_at_gap(self) -> None:
        streak, end = longest_streak(
            [
                date(2026, 8, 20),
                date(2026, 8, 21),
                date(2026, 8, 23),
                date(2026, 8, 24),
                date(2026, 8, 25),
            ]
        )
        self.assertEqual(streak, 3)
        self.assertEqual(end, date(2026, 8, 25))

    def test_achievement_engine_uses_tracked_history(self) -> None:
        snapshots = [
            self.snapshot("2026-08-20", commits=60, prs=5),
            self.snapshot("2026-08-21", commits=50, prs=5),
        ]
        achievements = achievement_engine(snapshots)
        keys = [item["key"] for item in achievements]
        self.assertEqual(keys, ["first-signal", "100-commits", "10-prs"])
        self.assertEqual(achievements[1]["unlocked_on"], "2026-08-21")

    def test_achievement_engine_unlocks_seven_day_streak(self) -> None:
        snapshots = [
            self.snapshot(f"2026-08-{day:02d}", commits=1)
            for day in range(20, 27)
        ]
        achievements = achievement_engine(snapshots)
        streak = next(item for item in achievements if item["key"] == "7-day-streak")
        self.assertEqual(streak["unlocked_on"], "2026-08-26")

    def test_render_recap_keeps_monthly_and_achievements_collapsed(self) -> None:
        state = {
            "ci_signal": {"pass_rate": 90, "passed": 9, "evaluated": 10},
            "dev_recap": {
                "tracked_from": "2026-08-25",
                "weekly": {
                    "period": "2026-W35",
                    "coverage": {"active_days": 2},
                    "metrics": {"commits": 100, "prs_opened": 5, "issues_completed": 3},
                },
                "monthly": {
                    "period": "2026-08",
                    "coverage": {"active_days": 2},
                    "metrics": {
                        "commits": 100,
                        "prs_opened": 5,
                        "issues_completed": 3,
                        "activity_total": 110,
                    },
                },
                "achievements": [
                    {"icon": "📡", "label": "FIRST SIGNAL", "unlocked_on": "2026-08-25"}
                ],
            },
        }
        rendered = render_recap(state)
        self.assertIn("PROFILE-SIGNAL:RECAP:START", rendered)
        self.assertIn("DEV RECAP // Tracked history", rendered)
        self.assertIn("<details>", rendered)
        self.assertIn("MONTHLY BUILD REPORT + ACHIEVEMENTS", rendered)
        self.assertIn("FIRST SIGNAL", rendered)
        self.assertIn("tracked since 2026-08-25", rendered)


if __name__ == "__main__":
    unittest.main()
