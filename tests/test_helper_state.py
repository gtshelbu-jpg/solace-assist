import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.interfaces import helper_state
from solace_assist.interfaces.helper_shell import shell_spec
from solace_assist.core.catalog import Catalog


class HelperStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-helper-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_context_never_persists_arguments_credentials_or_output(self):
        helper_state.context(self.root, "sudo nmap --password SECRET 192.0.2.10")
        context = helper_state.read(self.root, "context.json")
        self.assertEqual(context["executable"], "nmap")
        raw = (self.root / "context.json").read_text()
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("192.0.2.10", raw)
        self.assertEqual((self.root / "context.json").stat().st_mode & 0o777, 0o600)
        for buffer in ("$(command)", "nmap; other", "VAR=secret nmap", "nmap\nother"):
            helper_state.context(self.root, buffer)
            self.assertIsNone(helper_state.read(self.root, "context.json")["executable"])

    def test_queue_requires_adapter_and_consume_is_revalidated_single_line(self):
        with self.assertRaises(ValueError):
            helper_state.queue(self.root, "readelf-header", {"file": "a file.elf"})
        helper_state.write(self.root, "ready.json", {"shell": "bash"})
        helper_state.queue(self.root, "readelf-header", {"file": "a file.elf"})
        self.assertTrue((self.root / "pending.json").exists())
        self.assertEqual(helper_state.consume(self.root), "readelf -h 'a file.elf'")
        self.assertIsNone(helper_state.consume(self.root))
        helper_state.write(self.root, "pending.json", {"template": "readelf-header", "arguments": {"file": "a\ncommand"}, "authorized": False})
        with self.assertRaises(ValueError):
            helper_state.consume(self.root)

    def test_symlinks_public_files_and_nonregular_state_are_refused(self):
        target = self.root / "other"
        target.write_text('{}')
        (self.root / "ready.json").symlink_to(target)
        with self.assertRaises(OSError):
            helper_state.read(self.root, "ready.json")
        (self.root / "ready.json").unlink()
        (self.root / "ready.json").write_text('{}')
        with self.assertRaises(ValueError):
            helper_state.read(self.root, "ready.json")
        (self.root / "ready.json").unlink()
        os.mkfifo(self.root / "ready.json", 0o600)
        with self.assertRaises(ValueError):
            helper_state.read(self.root, "ready.json")

    def test_shell_selection_preserved_and_other_grammars_are_read_only(self):
        for executable, capable in (("/bin/bash", True), ("/bin/zsh", False), ("/bin/fish", False), ("/bin/unknown", False)):
            with self.subTest(shell=executable), patch("shutil.which", return_value=executable):
                self.assertEqual(shell_spec(executable), (executable, capable))
        with patch("shutil.which", return_value=None), self.assertRaises(ValueError):
            shell_spec("bash; command")

    def test_guided_filter_and_exact_executable_mapping(self):
        catalog = Catalog(self.root / "catalog.sqlite3")
        self.assertEqual(len(catalog.search(guided=True)), 8)
        self.assertEqual(catalog.tool_for_executable("tshark"), "wireshark")
        self.assertIsNone(catalog.tool_for_executable("nmap; command"))
        self.assertNotEqual(catalog.categories(), catalog.categories(guided=True))
