import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.interfaces.palette import load_palette, system_palette_path


class PaletteTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-palette-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "colors.toml"

    def test_minimal_palette_and_light_mode(self):
        self.path.write_text('background = "#fafafa"\nforeground = "#111111"\naccent = "#B4A1E8"\n')
        colors = load_palette(self.path)
        self.assertEqual(colors["primary"], "#b4a1e8")
        self.assertEqual(colors["surface"], "#fafafa")
        self.assertFalse(colors["dark"])

    def test_missing_malformed_oversized_and_css_injection_are_ignored(self):
        self.assertIsNone(load_palette(self.path))
        for body in ('invalid toml', 'background = "red; display: none"', '# ' + 'x' * 65536, 'background = 42'):
            self.path.write_text(body)
            self.assertIsNone(load_palette(self.path))
        self.path.write_bytes(b'\xff')
        self.assertIsNone(load_palette(self.path))

    def test_semantic_palette_slots_and_xdg_location(self):
        self.path.write_text('mode = "dark"\nbackground = "#101017"\nforeground = "#dddde7"\naccent = "#b4a1e8"\nlighter_bg = "#1c1b25"\ncolor1 = "#d88796"\ncolor2 = "#a1bdad"\ncolor3 = "#d0ba8a"\n')
        colors = load_palette(self.path)
        self.assertEqual(colors["error"], "#d88796")
        self.assertEqual(colors["panel"], "#1c1b25")
        self.assertTrue(colors["dark"])
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name}):
            self.assertEqual(system_palette_path(), Path(self.temp.name) / "solace/current/theme/colors.toml")


if __name__ == "__main__":
    unittest.main()
