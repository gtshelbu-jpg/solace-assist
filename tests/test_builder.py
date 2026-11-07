from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.core.catalog import Catalog
from solace_assist.interfaces import helper_state

try:
    from textual.widgets import Input, Button, Checkbox, Select, DataTable
    from solace_assist.interfaces.tui import ToolExplorer
    from solace_assist.interfaces.builder import CommandBuilder
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(HAS_TEXTUAL, "Optional TUI dependency required")
class BuilderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-builder-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = Catalog(self.root / "catalog.sqlite3")

    async def test_builder_requires_valid_preview_then_explicit_stage(self):
        ipc = self.root / "ipc"
        ipc.mkdir(mode=0o700)
        helper_state.write(ipc, "ready.json", {"shell": "bash"})
        app = ToolExplorer(self.catalog, helper_session=ipc, initial_tool="readelf", initial_query="readelf")
        with patch("subprocess.run", side_effect=AssertionError("builder must not execute commands")):
            async with app.run_test(size=(140, 50)) as pilot:
                await pilot.pause(.4)
                await pilot.press("ctrl+p")
                await pilot.pause(.3)
                self.assertIsInstance(app.screen, CommandBuilder)
                self.assertEqual(app.screen.focused.id, "argument-file")
                app.screen.query_one("#argument-file", Input).value = "a sample.elf"
                await pilot.pause(.2)
                self.assertFalse((ipc / "pending.json").exists())
                await pilot.press("enter")
                await pilot.pause(.2)
                self.assertFalse(app.screen.query_one("#builder-stage", Button).disabled)
                self.assertFalse((ipc / "pending.json").exists(), "Preview must not stage automatically")
                await pilot.press("ctrl+enter")
                await pilot.pause(.2)
                self.assertEqual(helper_state.consume(ipc), "readelf -h 'a sample.elf'")
                app.screen.query_one("#argument-file", Input).value = "different.elf"
                await pilot.pause(.2)
                self.assertTrue(app.screen.query_one("#builder-stage", Button).disabled)
                await pilot.press("ctrl+enter")
                await pilot.pause(.2)
                self.assertEqual(helper_state.consume(ipc), "readelf -h different.elf")
                app.screen.query_one("#argument-file", Input).value = ""
                await pilot.pause(.2)
                await pilot.press("ctrl+enter")
                await pilot.pause(.2)
                self.assertFalse((ipc / "pending.json").exists())

    async def test_task_picker_and_all_metadata_toggle(self):
        app = ToolExplorer(self.catalog)
        async with app.run_test(size=(100, 45)) as pilot:
            await pilot.pause(.3)
            self.assertEqual(app.query_one("#results", DataTable).row_count, 8)
            app.query_one("#guided", Checkbox).value = False
            await pilot.pause(.4)
            self.assertEqual(app.query_one("#results", DataTable).row_count, 14)
            await pilot.press("ctrl+t")
            await pilot.pause(.2)
            await pilot.press("enter")
            await pilot.pause(.4)
            self.assertIsInstance(app.screen, CommandBuilder)
            self.assertEqual(app.screen.template_id, "readelf-header")

    async def test_live_context_hints_do_not_execute_or_persist_arguments(self):
        ipc = self.root / "ipc"
        ipc.mkdir(mode=0o700)
        app = ToolExplorer(self.catalog, helper_session=ipc)
        async with app.run_test(size=(100, 45)) as pilot:
            await pilot.pause(.3)
            helper_state.context(ipc, "tshark -r private-capture.pcap")
            app.refresh_context()
            await pilot.pause(.5)
            self.assertEqual(app.selected_id, "wireshark")
            self.assertNotIn("private-capture", (ipc / "context.json").read_text())
        app.refresh_context()  # A queued timer after unmount must be harmless.

    async def test_unknown_shell_network_preview_needs_no_acknowledgment(self):
        app = ToolExplorer(self.catalog)
        async with app.run_test(size=(140, 55)) as pilot:
            await pilot.pause(.3)
            app.push_screen(CommandBuilder(template_id="nmap-services"))
            await pilot.pause(.3)
            screen = app.screen
            self.assertEqual(screen.render_shell, "generic")
            self.assertEqual(screen.focused.id, "argument-target")
            self.assertFalse(screen.query("#builder-authorized"))
            screen.query_one("#argument-target", Input).value = "192.0.2.10"
            screen.query_one("#argument-ports", Input).value = "22,443"
            await pilot.pause(.2)
            await pilot.click("#builder-generate")
            await pilot.pause(.2)
            self.assertIsNotNone(screen.generated)
            self.assertTrue(screen.query_one("#builder-stage", Button).disabled)

    async def test_filters_fit_the_real_narrow_helper_pane(self):
        app = ToolExplorer(self.catalog)
        async with app.run_test(size=(63, 40)) as pilot:
            await pilot.pause(.3)
            for name in ("guided", "installed", "favorites"):
                self.assertLessEqual(app.query_one("#" + name, Checkbox).region.right, 63)
