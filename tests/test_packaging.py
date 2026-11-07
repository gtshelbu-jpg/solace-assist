import configparser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_native_menu_entry_opens_catalog_not_shell_or_tool(self):
        desktop = configparser.ConfigParser(interpolation=None)
        desktop.read(ROOT / "packaging/solace-assist.desktop")
        entry = desktop["Desktop Entry"]
        self.assertEqual(entry["Exec"], "sbtools")
        self.assertEqual(entry["TryExec"], "sbtools")
        self.assertEqual(entry["Terminal"], "true")
        recipe = (ROOT / "packaging/arch/PKGBUILD.in").read_text()
        self.assertIn('"$pkgdir/usr/share/applications/solace-assist.desktop"', recipe)


if __name__ == "__main__":
    unittest.main()
