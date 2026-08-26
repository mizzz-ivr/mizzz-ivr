from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from scripts.profile_signal import (
    activity_stream,
    activity_total,
    aggregate_ci_signals,
    calculate_streak,
    ci_summary,
    code_weather,
    current_focus,
    dev_status,
    ranked_repositories,
    relative_age,
    repository_health,
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

    def test_ci_summary_marks_latest_failure_attention(self) -> None:
        now = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
        runs = [
            {"status": "completed", "conclusion": "failure", "run_started_at": "2026-08-26T11:00:00Z"},
            {"status": "completed", "conclusion": "success", "run_started_at": "2026-08-26T10:00:00Z"},
            {"status": "completed", "conclusion": "success", "run_started_at": "2026-08-25T10:00:00Z"},
            {"status": "completed", "conclusion": "success", "run_started_at": "2026-08-24T10:00:00Z"},
        ]
        summary = ci_summary(runs, now)
        self.assertEqual(summary["label"], "ATTENTION")
        self.assertEqual(summary["passed"], 3)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["pass_rate"], 75)

    def test_ci_summary_excludes_cancelled_from_pass_rate(self) -> None:
        now = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
        runs = [
            {"status": "completed", "conclusion": "success", "run_started_at": "2026-08-26T10:00:00Z"},
            {"status": "completed", "conclusion": "cancelled", "run_started_at": "2026-08-26T09:00:00Z"},
        ]
        summary = ci_summary(runs, now)
        self.assertEqual(summary["label"], "PASSING")
        self.assertEqual(summary["evaluated"], 1)
        self.assertEqual(summary["ignored"], 1)
        self.assertEqual(summary["pass_rate"], 100)

    def test_repository_health_combines_recency_and_ci(self) -> None:
        now = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
        passing = {"label": "PASSING"}
        attention = {"label": "ATTENTION"}
        active_meta = {"pushed_at": "2026-08-26T11:00:00Z", "archived": False, "disabled": False}
        quiet_meta = {"pushed_at": "2026-06-01T11:00:00Z", "archived": False, "disabled": False}

        self.assertEqual(repository_health(active_meta, passing, now)["label"], "HEALTHY")
        self.assertEqual(repository_health(active_meta, attention, now)["label"], "ATTENTION")
        self.assertEqual(repository_health(quiet_meta, passing, now)["label"], "QUIET")

    def test_aggregate_ci_signals(self) -> None:
        combined = aggregate_ci_signals(
            [
                {"label": "PASSING", "window_days": 7, "passed": 5, "failed": 0, "ignored": 1, "evaluated": 5},
                {"label": "MIXED", "window_days": 7, "passed": 4, "failed": 1, "ignored": 0, "evaluated": 5},
                {"label": "NO SIGNAL", "window_days": 7, "passed": 0, "failed": 0, "ignored": 0, "evaluated": 0},
            ]
        )
        self.assertEqual(combined["label"], "MIXED")
        self.assertEqual(combined["passed"], 9)
        self.assertEqual(combined["failed"], 1)
        self.assertEqual(combined["pass_rate"], 90)
        self.assertEqual(combined["repos_with_signal"], 2)


if __name__ == "__main__":
    unittest.main()
