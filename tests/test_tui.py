from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from textual.widgets import Checkbox, DataTable, Input
    from solace_assist.interfaces.tui import ToolExplorer
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from solace_assist.core.catalog import Catalog


@unittest.skipUnless(HAS_TEXTUAL, "Install the optional tui extra to run UI tests")
class TUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="assist-tui-", dir="/tmp/opencode")
        self.addCleanup(self.temp.cleanup)
        self.catalog = Catalog(Path(self.temp.name) / "catalog.sqlite3")

    async def test_keyboard_search_categories_favorites_and_installed_filter(self):
        app = ToolExplorer(self.catalog)
        with patch("subprocess.run", side_effect=AssertionError("browsing must not execute anything")):
            async with app.run_test(size=(140, 42)) as pilot:
                await pilot.pause(0.3)
                self.assertEqual(app.query_one("#results", DataTable).row_count, 14)
                app.query_one("#search", Input).value = "enumerate smb"
                await pilot.pause(0.4)
                self.assertEqual(app.query_one("#results", DataTable).row_count, 2)
                self.assertIn(app.selected_id, {"smbclient", "smbmap"})
                selected = app.selected_id
                app.query_one("#results", DataTable).focus()
                await pilot.press("f")
                await pilot.pause(0.3)
                self.assertTrue(self.catalog.show(selected)["favorite"])
                app.query_one("#favorites", Checkbox).value = True
                await pilot.pause(0.3)
                self.assertEqual(app.query_one("#results", DataTable).row_count, 1)
                app.query_one("#installed", Checkbox).value = True
                await pilot.pause(0.3)
                self.assertEqual(app.query_one("#results", DataTable).row_count, 0)

    async def test_narrow_terminal_detail_navigation(self):
        app = ToolExplorer(self.catalog)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.3)
            self.assertTrue(app.has_class("narrow"))
            app.query_one("#results", DataTable).focus()
            await pilot.press("enter")
            await pilot.pause(0.2)
            self.assertTrue(app.has_class("detail-open"))
            await pilot.press("escape")
            self.assertFalse(app.has_class("detail-open"))

    async def test_category_sidebar_uses_the_core_filter(self):
        app = ToolExplorer(self.catalog)
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.3)
            await pilot.press("ctrl+g", "home", "down", "enter")
            await pilot.pause(0.3)
            self.assertEqual(app.category, "firmware")
            self.assertEqual(app.query_one("#results", DataTable).row_count, 1)
            self.assertEqual(app.selected_id, "binwalk")


if __name__ == "__main__": unittest.main()
