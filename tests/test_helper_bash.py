import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from solace_assist.interfaces import helper_state
from solace_assist.interfaces.pty_transport import PTYSession


def until(session, marker, timeout=5):
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = session.read(.1)
        if chunk:
            output.extend(chunk)
            if marker in output:
                return bytes(output)
        elif chunk == b"":
            break
    raise AssertionError("Expected shell marker was not received")


@unittest.skipUnless(shutil.which("bash"), "Bash adapter integration requires Bash")
class HelperBashTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)

    def test_real_readline_context_and_insertion_require_keys_and_user_enter(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-bash-helper-") as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            rc = home / ".bashrc"
            rc.write_text("PS1='ASSIST_ADAPTER_TEST> '\n")
            original = rc.read_bytes()
            session_dir = root / "ipc"
            session_dir.mkdir(mode=0o700)
            stubs = root / "bin"
            stubs.mkdir()
            marker = root / "explicitly-executed"
            stub = stubs / "readelf"
            stub.write_text("#!/bin/bash\nprintf executed > \"$EXECUTION_MARKER\"\nprintf 'EXPLICIT_EXECUTION_ONLY\\n'\n")
            stub.chmod(0o755)
            env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(ROOT / "src"),
                   "SBTOOLS_HELPER_SESSION": str(session_dir), "SBTOOLS_HELPER_PYTHON": sys.executable,
                   "PATH": str(stubs) + ":" + os.environ["PATH"], "EXECUTION_MARKER": str(marker),
                   "TERM": "xterm-256color", "PROMPT_COMMAND": "", "BASH_ENV": "/dev/null"}
            with PTYSession([shutil.which("bash"), "--noprofile", "--rcfile", str(ROOT / "src/solace_assist/data/helper.bash"), "-i"], env=env) as shell:
                until(shell, b"ASSIST_ADAPTER_TEST>")
                self.assertEqual(helper_state.read(session_dir, "ready.json")["shell"], "bash")
                shell.write(b"nmap --password SECRET")
                shell.write(b"\x07")  # Native Readline bind-x, not output parsing.
                deadline = time.monotonic() + 5
                while not (session_dir / "context.json").exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertEqual(helper_state.read(session_dir, "context.json")["executable"], "nmap")
                self.assertNotIn("SECRET", (session_dir / "context.json").read_text())
                helper_state.queue(session_dir, "readelf-header", {"file": "safe fixture.elf"})
                shell.write(b"\x18\x09")
                time.sleep(.15)
                self.assertTrue((session_dir / "pending.json").exists(), "Nonempty buffer must not be replaced")
                self.assertFalse(marker.exists())
                shell.write(b"\x15")  # User clears the buffer.
                shell.write(b"\x18\x09")
                until(shell, b"safe fixture.elf")
                self.assertFalse(marker.exists(), "Insertion must never append Enter")
                self.assertFalse((session_dir / "pending.json").exists())
                shell.write(b"\n")  # Explicit user Enter, only now execute test stub.
                until(shell, b"EXPLICIT_EXECUTION_ONLY")
                self.assertTrue(marker.exists())
                shell.write(b"exit\n")
                self.assertEqual(shell.wait(), 0)
            self.assertEqual(rc.read_bytes(), original)
