from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".profile-signal" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import preset_runtime  # noqa: E402


class ProfileSignalV02PresetTests(unittest.TestCase):
    def test_v02_preset_pack_contract(self) -> None:
        registry = preset_runtime.load_registry(ROOT / ".profile-signal")

        self.assertEqual(
            set(registry["compact"]["widgets"]),
            {"today", "current_focus"},
        )
        self.assertEqual(registry["compact"]["theme"], "minimal")

        self.assertEqual(
            set(registry["developer"]["widgets"]),
            {
                "live_signal",
                "current_focus",
                "dev_pulse",
                "now_building",
                "activity_stream",
            },
        )

        self.assertEqual(
            set(registry["activity"]["widgets"]),
            {"today", "dev_pulse", "activity_stream", "dev_recap"},
        )

        self.assertEqual(
            set(registry["oss"]["widgets"]),
            {
                "live_signal",
                "current_focus",
                "now_building",
                "activity_stream",
                "dev_recap",
            },
        )

    def test_new_presets_do_not_change_v01_contract(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
