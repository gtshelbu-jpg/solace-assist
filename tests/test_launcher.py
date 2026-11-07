from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.core.catalog import Catalog
from solace_assist.interfaces import launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-launcher-")
        self.addCleanup(self.temp.cleanup)
        self.catalog = Catalog(Path(self.temp.name) / "catalog.sqlite3")

    def test_ranked_selection_opens_only_catalog_documentation(self):
        def menu(args, **kwargs):
            if "--inputonly" in args:
                return subprocess.CompletedProcess(args, 0, "enumerate smb\n", "")
            self.assertIn("smbclient", kwargs["input"].lower())
            return subprocess.CompletedProcess(args, 0, kwargs["input"].splitlines()[0] + "\n", "")
        with patch.object(launcher.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(launcher.subprocess, "run", side_effect=menu), \
             patch.object(launcher.subprocess, "Popen") as start:
            self.assertEqual(launcher.launch(self.catalog), 0)
        argv = start.call_args.args[0]
        self.assertEqual(argv[:4], ["xdg-terminal-exec", "--app-id=org.solace.sbtools", "-e", "sbtools"])
        self.assertEqual(argv[4:7], ["--db", str(self.catalog.path), "browse"])
        self.assertIn(argv[-1], {"smbclient", "smbmap"})
        self.assertNotIn("shell", start.call_args.kwargs)

    def test_arbitrary_selection_never_becomes_a_command(self):
        with patch.object(launcher.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(launcher, "choose", return_value="nmap; touch /tmp/not-a-command"), \
             patch.object(launcher.subprocess, "Popen") as start:
            with self.assertRaisesRegex(ValueError, "offered result"):
                launcher.launch(self.catalog, "nmap")
        start.assert_not_called()

    def test_cancel_missing_backend_and_empty_results_never_launch(self):
        with patch.object(launcher.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "standalone"):
                launcher.launch(self.catalog)
        with patch.object(launcher.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(launcher, "choose", return_value=None), \
             patch.object(launcher.subprocess, "Popen") as start:
            self.assertEqual(launcher.launch(self.catalog), 0)
            self.assertEqual(launcher.launch(self.catalog, "unfindablewordsxyz"), 0)
        start.assert_not_called()

    def test_oversized_query_is_rejected_before_opening_results(self):
        with patch.object(launcher.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(launcher.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                launcher.launch(self.catalog, "x" * 513)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
