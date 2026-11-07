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
                self.assertEqual(app.query_one("#results", DataTable).row_count, 8)
                app.query_one("#search", Input).value = "enumerate smb"
                await pilot.pause(0.4)
                self.assertEqual(app.query_one("#results", DataTable).row_count, len(self.catalog.search("enumerate smb", guided=True)))
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

    async def test_system_palette_follows_symlink_switch_without_resetting_search(self):
        root = Path(self.temp.name)
        current = root / "current"
        for name, accent in (("black", "#b4a1e8"), ("blue", "#3b6aa5")):
            folder = root / name
            folder.mkdir()
            (folder / "colors.toml").write_text('background = "#101017"\nforeground = "#dddde7"\naccent = "' + accent + '"\n')
        current.symlink_to(root / "black", target_is_directory=True)
        app = ToolExplorer(self.catalog, palette_path=current / "colors.toml")
        with patch("subprocess.run", side_effect=AssertionError("theming must not execute commands")):
            async with app.run_test(size=(140, 42)) as pilot:
                await pilot.pause(0.3)
                self.assertEqual(app.current_theme.primary, "#b4a1e8")
                self.assertEqual(app.screen.styles.background.hex, "#101017")
                app.query_one("#search", Input).value = "enumerate smb"
                await pilot.pause(0.4)
                current.unlink()
                current.symlink_to(root / "blue", target_is_directory=True)
                await pilot.pause(1.2)
                self.assertEqual(app.current_theme.primary, "#3b6aa5")
                self.assertEqual(app.query_one("#search", Input).value, "enumerate smb")
                self.assertIn(app.selected_id, {"smbclient", "smbmap"})
                (root / "blue/colors.toml").write_text("partially written invalid data")
                app.refresh_system_theme()
                self.assertEqual(app.current_theme.primary, "#3b6aa5")

    async def test_standalone_fallback_without_solace(self):
        app = ToolExplorer(self.catalog, palette_path=Path(self.temp.name) / "missing.toml")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.2)
            self.assertEqual(app.current_theme.background, "#101514")
            self.assertEqual(app.query_one("#results", DataTable).row_count, 8)

    async def test_launcher_detail_opens_requested_tool_on_narrow_screen(self):
        app = ToolExplorer(self.catalog, initial_tool="smbclient", initial_query="smbclient")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.5)
            self.assertEqual(app.selected_id, "smbclient")
            self.assertTrue(app.has_class("detail-open"))
            await pilot.press("escape")
            self.assertFalse(app.has_class("detail-open"))


if __name__ == "__main__": unittest.main()
