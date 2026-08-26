from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / ".profile-signal" / "src" / "orchestrator.py"
spec = importlib.util.spec_from_file_location("profile_signal_action", ORCHESTRATOR)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load Profile Signal orchestrator")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfileSignalActionTests(unittest.TestCase):
    def test_minimal_preset(self) -> None:
        config = module.deep_merge(module.DEFAULT_CONFIG, {"preset": "minimal"})
        widgets = module.resolve_widgets(config)
        self.assertTrue(widgets["live_signal"])
        self.assertTrue(widgets["current_focus"])
        self.assertFalse(widgets["today"])
        self.assertFalse(widgets["dev_recap"])

    def test_widget_override(self) -> None:
        config = module.deep_merge(
            module.DEFAULT_CONFIG,
            {"preset": "minimal", "widgets": {"today": {"enabled": True}}},
        )
        self.assertTrue(module.resolve_widgets(config)["today"])

    def test_terminal_preset_defaults_to_terminal_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile-signal.yml"
            path.write_text(
                "version: 1\npreset: terminal\nprofile:\n  username: octocat\n",
                encoding="utf-8",
            )
            config = module.load_config(path)
        self.assertEqual(config["theme"], "terminal")

    def test_public_only_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile-signal.yml"
            path.write_text(
                "version: 1\nprivacy:\n  public_only: false\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.load_config(path)

    def test_apply_blocks_auto_inserts_before_anchor(self) -> None:
        enabled = {name: False for name in module.WIDGET_ORDER}
        enabled["today"] = True
        blocks = {name: module.empty_marker(name) for name in module.WIDGET_ORDER}
        blocks["today"] = (
            "<!-- DAILY-ACTIVITY:START -->\nTODAY\n<!-- DAILY-ACTIVITY:END -->"
        )
        text = "hero\n\n## NOW // What I build\n"
        updated = module.apply_blocks(
            text,
            blocks,
            enabled,
            auto_insert=True,
            insert_before="## NOW // What I build",
            empty_disabled=True,
        )
        self.assertIn("TODAY", updated)
        self.assertLess(updated.index("TODAY"), updated.index("## NOW // What I build"))

    def test_disabled_widget_keeps_marker_pair_but_empties_content(self) -> None:
        enabled = {name: False for name in module.WIDGET_ORDER}
        blocks = {name: module.empty_marker(name) for name in module.WIDGET_ORDER}
        text = (
            "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:START -->\nold\n"
            "<!-- PROFILE-SIGNAL:LIVE-SIGNAL:END -->"
        )
        updated = module.apply_blocks(
            text,
            blocks,
            enabled,
            auto_insert=True,
            insert_before="",
            empty_disabled=True,
        )
        self.assertNotIn("old", updated)
        self.assertIn("PROFILE-SIGNAL:LIVE-SIGNAL:START", updated)
        self.assertIn("PROFILE-SIGNAL:LIVE-SIGNAL:END", updated)

    def test_packaged_runtime_matches_working_scripts(self) -> None:
        for name in (
            "update-profile-activity.py",
            "profile_signal.py",
            "update-profile-signal.py",
            "profile_signal_operations.py",
            "profile_signal_history.py",
        ):
            packaged = (ROOT / ".profile-signal" / "scripts" / name).read_text(encoding="utf-8")
            working = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertEqual(packaged, working, f"packaged runtime drifted: {name}")

    def test_packaged_runtime_is_self_contained(self) -> None:
        source_root = module.locate_source_root(ROOT / ".profile-signal")
        self.assertEqual(source_root, ROOT / ".profile-signal")


if __name__ == "__main__":
    unittest.main()
