from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from scripts.profile_signal import (
    activity_stream,
    activity_total,
    calculate_streak,
    code_weather,
    current_focus,
    dev_status,
    ranked_repositories,
    relative_age,
    score_event,
    summarize_event,
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
                "created_at": "2026-08-26T08:00:00Z",
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "b/two"},
                "payload": {"action": "opened"},
                "created_at": "2026-08-26T08:10:00Z",
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "b/two"},
                "payload": {"action": "closed", "pull_request": {"merged": True}},
                "created_at": "2026-08-26T08:20:00Z",
            },
        ]
        self.assertEqual(score_event(events[0]), 5)
        focus = current_focus(events)
        self.assertIsNotNone(focus)
        assert focus is not None
        self.assertEqual(focus["repo"], "b/two")
        self.assertEqual(focus["score"], 10)
        self.assertEqual(focus["share"], 67)
        self.assertEqual(focus["last_activity_at"], "2026-08-26T08:20:00Z")

    def test_ranked_repositories_returns_top_three_with_share(self) -> None:
        events = [
            {"type": "PushEvent", "repo": {"name": "a/one"}, "payload": {"size": 8}},
            {"type": "PushEvent", "repo": {"name": "b/two"}, "payload": {"size": 4}},
            {
                "type": "PullRequestEvent",
                "repo": {"name": "c/three"},
                "payload": {"action": "closed", "pull_request": {"merged": True}},
            },
            {"type": "IssuesEvent", "repo": {"name": "d/four"}, "payload": {"action": "opened"}},
        ]
        ranked = ranked_repositories(events, limit=3)
        self.assertEqual([item["repo"] for item in ranked], ["a/one", "c/three", "b/two"])
        self.assertEqual([item["score"] for item in ranked], [8, 6, 4])
        self.assertEqual(ranked[0]["share"], 40)
        self.assertEqual(len(ranked), 3)

    def test_summarize_event_for_merged_pr(self) -> None:
        event = {
            "type": "PullRequestEvent",
            "repo": {"name": "owner/repo"},
            "created_at": "2026-08-26T10:00:00Z",
            "payload": {
                "action": "closed",
                "pull_request": {
                    "number": 42,
                    "merged": True,
                    "html_url": "https://github.com/owner/repo/pull/42",
                },
            },
        }
        summary = summarize_event(event)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["label"], "PR")
        self.assertEqual(summary["title"], "Merged PR #42")
        self.assertEqual(summary["repo"], "owner/repo")

    def test_activity_stream_filters_and_orders(self) -> None:
        events = [
            {
                "type": "WatchEvent",
                "repo": {"name": "skip/star"},
                "created_at": "2026-08-26T12:00:00Z",
                "payload": {},
            },
            {
                "type": "IssuesEvent",
                "repo": {"name": "a/one"},
                "created_at": "2026-08-26T10:00:00Z",
                "payload": {"action": "opened", "issue": {"number": 7}},
            },
            {
                "type": "PushEvent",
                "repo": {"name": "b/two"},
                "created_at": "2026-08-26T11:00:00Z",
                "payload": {"size": 3, "ref": "refs/heads/main"},
            },
        ]
        stream = activity_stream(events, limit=4)
        self.assertEqual(len(stream), 2)
        self.assertEqual(stream[0]["label"], "PUSH")
        self.assertEqual(stream[0]["repo"], "b/two")
        self.assertEqual(stream[1]["title"], "Opened issue #7")


if __name__ == "__main__":
    unittest.main()
