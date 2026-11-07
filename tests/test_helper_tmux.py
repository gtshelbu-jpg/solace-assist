import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from solace_assist.interfaces import helper_state
from solace_assist.interfaces.pty_transport import PTYSession

try:
    import textual
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(shutil.which("tmux") and shutil.which("bash") and HAS_TEXTUAL, "tmux/Bash/Textual required for real helper integration")
class TmuxHelperTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)

    def test_full_helper_uses_real_pty_and_exits_without_leaking_server(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="sb-h-") as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            (home / ".bashrc").write_text("PS1='HELPER_TMUX_TEST> '\n")
            env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(ROOT / "src"), "XDG_RUNTIME_DIR": str(root),
                   "SHELL": shutil.which("bash"), "BASH_ENV": "/dev/null", "TERM": "xterm-256color"}
            argv = [sys.executable, "-m", "solace_assist.interfaces.cli", "--db", str(root / "catalog.sqlite3"), "shell"]
            with PTYSession(argv, env=env, rows=45, columns=150) as terminal:
                output = bytearray()
                deadline = time.monotonic() + 12
                session = None
                while time.monotonic() < deadline:
                    chunk = terminal.read(.1)
                    if chunk:
                        output.extend(chunk)
                    candidates = list(root.glob("sbtools-helper-*"))
                    if candidates and (candidates[0] / "ready.json").exists() and b"HELPER_TMUX_TEST>" in output:
                        session = candidates[0]
                        break
                    if chunk == b"":
                        break
                self.assertIsNotNone(session, output.decode(errors="replace")[-3000:])
                socket = session / "tmux.sock"
                panes = subprocess.check_output(["tmux", "-S", str(socket), "list-panes", "-t", "assist", "-F", "#{pane_tty}"], text=True)
                self.assertEqual(len(panes.splitlines()), 2)
                self.assertTrue(all(line.startswith("/dev/pts/") for line in panes.splitlines()))
                terminal.write(b"readelf")
                terminal.write(b"\x07")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not (session / "context.json").exists():
                    terminal.read(.1)
                self.assertEqual(helper_state.read(session, "context.json")["executable"], "readelf")
                terminal.write(b"\x15exit 7\n")
                deadline = time.monotonic() + 8
                while terminal.poll() is None and time.monotonic() < deadline:
                    terminal.read(.1)
                self.assertEqual(terminal.wait(), 7)
            self.assertFalse(session.exists(), "Ephemeral IPC/socket directory must be cleaned on exit")

    def test_other_shell_kept_read_only_and_termination_cleans_private_state(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="sb-h-ro-") as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(ROOT / "src"), "XDG_RUNTIME_DIR": str(root),
                   "SHELL": shutil.which("sh"), "ENV": "/dev/null", "TERM": "xterm-256color"}
            argv = [sys.executable, "-m", "solace_assist.interfaces.cli", "--db", str(root / "catalog.sqlite3"), "shell"]
            with PTYSession(argv, env=env, rows=45, columns=150) as terminal:
                session = None
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    terminal.read(.1)
                    candidates = list(root.glob("sbtools-helper-*"))
                    if candidates and (candidates[0] / "tmux.sock").exists():
                        session = candidates[0]
                        try:
                            panes = subprocess.check_output(["tmux", "-S", str(session / "tmux.sock"), "list-panes", "-t", "assist"], text=True, stderr=subprocess.DEVNULL)
                            if len(panes.splitlines()) == 2:
                                break
                        except subprocess.CalledProcessError:
                            pass
                self.assertIsNotNone(session)
                self.assertFalse((session / "ready.json").exists())
                with self.assertRaises(ValueError):
                    helper_state.queue(session, "readelf-header", {"file": "sample.elf"})
                terminal.close()  # Closing outer terminal sends HUP to controller.
                self.assertIsNotNone(terminal.poll())
            self.assertFalse(session.exists(), "Terminal close must not leave its tmux server or IPC behind")
