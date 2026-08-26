from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from scripts.profile_signal import (
    activity_total,
    calculate_streak,
    code_weather,
    current_focus,
    dev_status,
    relative_age,
    score_event,
)


class ProfileSignalTests(unittest.TestCase):
    def test_activity_total(self) -> None:
        snapshot = {
            "metrics": {
                "commits": 10,
                "prs_opened": 2,
                "issues_created": 1,
                "issues_completed": 3,
            }
        }
        self.assertEqual(activity_total(snapshot), 16)

    def test_weather_thresholds(self) -> None:
        self.assertEqual(code_weather(0)["label"], "REST DAY")
        self.assertEqual(code_weather(5)["label"], "LIGHT CODING")
        self.assertEqual(code_weather(20)["label"], "ACTIVE")
        self.assertEqual(code_weather(50)["label"], "HEAVY CODING")
        self.assertEqual(code_weather(51)["label"], "STORM")

    def test_dev_status(self) -> None:
        now = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)
        self.assertEqual(dev_status("2026-08-26T08:30:00Z", now)["label"], "BUILDING")
        self.assertEqual(dev_status("2026-08-26T05:00:00Z", now)["label"], "RECENTLY ACTIVE")
        self.assertEqual(dev_status("2026-08-25T20:00:00Z", now)["label"], "OFFLINE")
        self.assertEqual(dev_status("2026-08-24T08:00:00Z", now)["label"], "QUIET")

    def test_relative_age(self) -> None:
        self.assertEqual(relative_age(20), "just now")
        self.assertEqual(relative_age(600), "10m ago")
        self.assertEqual(relative_age(7200), "2h ago")
        self.assertEqual(relative_age(172800), "2d ago")

    def test_streak_stops_at_gap(self) -> None:
        today = date(2026, 8, 26)
        active = {
            date(2026, 8, 26),
            date(2026, 8, 25),
            date(2026, 8, 23),
        }
        self.assertEqual(calculate_streak(active, today), 2)

    def test_event_scoring_and_focus(self) -> None:
        events = [
            {
                "type": "PushEvent",
                "repo": {"name": "a/one"},
                "payload": {"size": 5},
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "b/two"},
                "payload": {"action": "opened"},
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "b/two"},
                "payload": {"action": "closed", "pull_request": {"merged": True}},
            },
        ]
        self.assertEqual(score_event(events[0]), 5)
        focus = current_focus(events)
        self.assertIsNotNone(focus)
        assert focus is not None
        self.assertEqual(focus["repo"], "b/two")
        self.assertEqual(focus["score"], 10)
        self.assertEqual(focus["share"], 67)


if __name__ == "__main__":
    unittest.main()
