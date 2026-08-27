from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_engineering_dna as dna


class EngineeringDnaTest(unittest.TestCase):
    def sample_data(self) -> dict:
        return {
            "assignment_fit": [
                {"label": "Full-stack Product Development", "score": 100},
                {"label": "Realtime AI / Voice", "score": 92},
                {"label": "Platform / Developer Tooling", "score": 88},
                {"label": "DevOps / Observability", "score": 76},
            ],
            "practices": [
                {"name": "security-by-design"},
                {"name": "automated-testing"},
                {"name": "least-privilege"},
                {"name": "fail-close"},
                {"name": "accessibility-first"},
                {"name": "observability"},
                {"name": "release-automation"},
            ],
            "ownership": [
                {"name": "security"},
                {"name": "testing"},
            ],
        }

    def test_scores_are_derived_from_evidence(self) -> None:
        scores = dict(dna.engineering_dna_scores(self.sample_data()))
        self.assertEqual(scores["FULL STACK"], 100)
        self.assertEqual(scores["REALTIME AI"], 92)
        self.assertEqual(scores["PLATFORM / TOOLING"], 88)
        self.assertEqual(scores["DEVOPS / OPS"], 76)
        self.assertEqual(scores["SECURITY / QUALITY"], 90)

    def test_svg_is_valid_and_describes_public_evidence(self) -> None:
        svg = dna.render_svg(dna.engineering_dna_scores(self.sample_data()))
        ET.fromstring(svg)
        self.assertIn("ENGINEERING DNA", svg)
        self.assertIn("PUBLIC EVIDENCE PROFILE", svg)
        self.assertIn("SECURITY / QUALITY", svg)
        self.assertIn("Evidence coverage, not proficiency", svg)

    def test_upsert_section_inserts_once_and_then_replaces(self) -> None:
        source = "# Profile\n\n## PUBLIC BUILDS\n\nbody\n"
        section = dna.render_section(japanese=True)
        first = dna.upsert_section(source, section, before_heading="PUBLIC BUILDS")
        second = dna.upsert_section(first, section, before_heading="PUBLIC BUILDS")
        self.assertEqual(second.count(dna.SECTION_START), 1)
        self.assertEqual(second.count(dna.SECTION_END), 1)
        self.assertIn("assets/engineering-dna.svg", second)

    def test_write_outputs_updates_both_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            readme = root / "README.md"
            readme_en = root / "README.en.md"
            output = root / "assets/engineering-dna.svg"
            readme.write_text("# JP\n\n## PUBLIC BUILDS\n", encoding="utf-8")
            readme_en.write_text("# EN\n\n## SELECTED PROJECTS\n", encoding="utf-8")
            dna.write_outputs(self.sample_data(), readme=readme, readme_en=readme_en, output=output)
            self.assertTrue(output.exists())
            self.assertIn("ENGINEERING DNA", readme.read_text(encoding="utf-8"))
            self.assertIn("ENGINEERING DNA", readme_en.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
