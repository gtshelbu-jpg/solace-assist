import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="assist-cli-", dir="/tmp/opencode")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "catalog.sqlite3"
        self.env = {**os.environ, "HOME": str(self.root), "PYTHONPATH": str(ROOT / "src")}

    def command(self, *args):
        return subprocess.run([sys.executable, "-m", "solace_assist.interfaces.cli", "--db", str(self.db), *args],
                              capture_output=True, text=True, env=self.env)

    def test_search_show_categories_and_info(self):
        result = self.command("search", "analyze firmware", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("binwalk", [r["id"] for r in json.loads(result.stdout)])
        result = self.command("show", "readelf", "--json")
        self.assertEqual(json.loads(result.stdout)["tool_packages"], ["binutils"])
        self.assertEqual(self.command("category", "wireless").returncode, 0)
        self.assertEqual(json.loads(self.command("info", "--json").stdout)["tools"], 14)

    def test_persistent_personal_commands(self):
        self.assertEqual(self.command("favorite", "nmap").returncode, 0)
        self.assertEqual(self.command("note", "nmap", "--text", "my local reference").returncode, 0)
        self.assertEqual(self.command("tag", "nmap", "lab").returncode, 0)
        item = json.loads(self.command("show", "nmap", "--json").stdout)
        self.assertTrue(item["favorite"])
        self.assertEqual(item["note"], "my local reference")
        self.assertEqual(item["tags"], ["lab"])
        self.assertEqual(self.command("favorite", "nmap", "--remove").returncode, 0)
        self.assertEqual(self.command("note", "nmap", "--clear").returncode, 0)

    def test_missing_tools_and_nonterminal_shell_fail_honestly(self):
        self.assertNotEqual(self.command("show", "does-not-exist").returncode, 0)
        result = self.command("shell")
        self.assertEqual(result.returncode, 1)
        self.assertIn("real terminal", result.stderr)
        self.assertEqual(self.command("search", "--limit", "100000").returncode, 1)

    def test_sync_empty_local_source_needs_no_network_or_root(self):
        result = self.command("sync", "--local-dir", str(self.root / "empty"), "--no-installed", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})

    def test_reviewed_template_commands_are_preview_only(self):
        rows = json.loads(self.command("templates", "--tool", "readelf", "--json").stdout)
        self.assertEqual(len(rows), 2)
        result = self.command("preview", "readelf-header", "--arg", "file=a sample.elf", "--shell", "bash", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["argv"], ["readelf", "-h", "a sample.elf"])
        self.assertFalse(preview["execution"])
        result = self.command("preview", "nmap-services", "--arg", "target=192.0.2.10", "--arg", "ports=22,443", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["execution"])
        self.assertEqual(self.command("preview", "readelf-header", "--arg", "file=a", "--arg", "file=b").returncode, 1)


if __name__ == "__main__": unittest.main()
