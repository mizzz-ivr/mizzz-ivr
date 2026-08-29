from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import profile_signal_customize as custom


class ProfileSignalLayoutTest(unittest.TestCase):
    def test_normalize_dashboard_tables_expands_plain_tables(self) -> None:
        source = '<table>one</table>\n<table><tr><td>two</td></tr></table>'
        rendered = custom.normalize_dashboard_tables(source)

        self.assertEqual(rendered.count('<table width="100%">'), 2)
        self.assertNotIn("<table>", rendered)

    def test_replace_marker_applies_full_width_layout(self) -> None:
        start, end = custom.MARKERS["live"]
        readme = f"{start}\nold\n{end}"
        block = f"{start}\n<table><tr><td>signal</td></tr></table>\n{end}"

        rendered = custom.replace_marker(readme, "live", block)

        self.assertIn('<table width="100%">', rendered)
        self.assertNotIn("\n<table>\n", rendered)


if __name__ == "__main__":
    unittest.main()
