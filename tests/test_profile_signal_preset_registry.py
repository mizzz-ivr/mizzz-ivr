from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".profile-signal" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import preset_runtime  # noqa: E402


class ProfileSignalPresetRegistryTests(unittest.TestCase):
    def test_builtin_presets_preserve_v01_widget_contract(self) -> None:
        registry = preset_runtime.load_registry(ROOT / ".profile-signal")
        self.assertEqual(
            set(registry["minimal"]["widgets"]),
            {"live_signal", "current_focus"},
        )
        self.assertEqual(
            set(registry["standard"]["widgets"]),
            {"live_signal", "today", "current_focus", "dev_pulse"},
        )
        self.assertEqual(
            set(registry["full"]["widgets"]),
            set(preset_runtime.orchestrator.WIDGET_ORDER),
        )
        self.assertEqual(
            set(registry["terminal"]["widgets"]),
            set(preset_runtime.orchestrator.WIDGET_ORDER),
        )

    def test_terminal_preset_declares_terminal_theme(self) -> None:
        registry = preset_runtime.load_registry(ROOT / ".profile-signal")
        self.assertEqual(registry["terminal"]["theme"], "terminal")
        self.assertEqual(registry["standard"]["theme"], "signal")

    def test_new_preset_can_be_added_without_runtime_code_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            action_path = Path(directory)
            shutil.copytree(ROOT / ".profile-signal" / "presets", action_path / "presets")
            (action_path / "presets" / "compact.yml").write_text(
                "version: 1\n"
                "id: compact\n"
                "description: Compact test preset.\n"
                "theme: minimal\n"
                "widgets:\n"
                "  - today\n"
                "  - current_focus\n",
                encoding="utf-8",
            )
            registry = preset_runtime.load_registry(action_path)

        self.assertEqual(set(registry["compact"]["widgets"]), {"today", "current_focus"})
        self.assertEqual(registry["compact"]["theme"], "minimal")

    def test_unknown_widget_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            action_path = Path(directory)
            shutil.copytree(ROOT / ".profile-signal" / "presets", action_path / "presets")
            (action_path / "presets" / "broken.yml").write_text(
                "version: 1\n"
                "id: broken\n"
                "theme: signal\n"
                "widgets:\n"
                "  - not_a_widget\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                preset_runtime.load_registry(action_path)

    def test_preset_id_must_match_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            action_path = Path(directory)
            shutil.copytree(ROOT / ".profile-signal" / "presets", action_path / "presets")
            (action_path / "presets" / "wrong-name.yml").write_text(
                "version: 1\n"
                "id: another-name\n"
                "theme: signal\n"
                "widgets:\n"
                "  - today\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                preset_runtime.load_registry(action_path)


if __name__ == "__main__":
    unittest.main()
