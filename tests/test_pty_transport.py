import os
from pathlib import Path
import shutil
import shlex
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.interfaces.pty_transport import PTYSession


def until(session, marker, timeout=3):
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = session.read(0.1)
        if chunk:
            output.extend(chunk)
            if marker in output:
                return bytes(output)
        elif chunk == b"":
            break
    raise AssertionError(f"PTY marker not received: {marker!r}, output={bytes(output)!r}")


@unittest.skipUnless(os.name == "posix", "PTY transport is POSIX-only")
class PTYTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)

    def test_child_has_real_terminal_and_requested_dimensions(self):
        code = "import os,fcntl,termios,struct; print('TTY',os.isatty(0),os.isatty(1),struct.unpack('HHHH',fcntl.ioctl(0,termios.TIOCGWINSZ,b'\\0'*8))[:2],flush=True)"
        with PTYSession([sys.executable, "-c", code], rows=31, columns=109) as session:
            self.assertIn(b"TTY True True (31, 109)", until(session, b"(31, 109)"))
            self.assertEqual(session.wait(), 0)
            self.assertFalse(session.editable_buffer_available)

    def test_explicit_bytes_resize_and_exit_status(self):
        code = "import fcntl,termios,struct; print('READY',flush=True); input(); print('SIZE',struct.unpack('HHHH',fcntl.ioctl(0,termios.TIOCGWINSZ,b'\\0'*8))[:2],flush=True); raise SystemExit(7)"
        with PTYSession([sys.executable, "-c", code]) as session:
            until(session, b"READY")
            session.resize(40, 120)
            session.write(b"user explicitly presses enter\n")
            self.assertIn(b"SIZE (40, 120)", until(session, b"SIZE (40, 120)"))
            self.assertEqual(session.wait(), 7)

    def test_control_c_reaches_foreground_child(self):
        code = "import signal,time; signal.signal(signal.SIGINT,lambda *a: exit(23)); print('READY',flush=True); time.sleep(30)"
        with PTYSession([sys.executable, "-c", code]) as session:
            until(session, b"READY")
            session.write(b"\x03")
            self.assertEqual(session.wait(), 23)

    def test_close_reaps_child_and_is_idempotent(self):
        session = PTYSession([sys.executable, "-c", "import time; print('READY',flush=True); time.sleep(30)"])
        until(session, b"READY")
        session.close()
        session.close()
        self.assertIsNotNone(session.poll())
        with self.assertRaises(ChildProcessError):
            os.waitpid(session.pid, os.WNOHANG)

    def test_exec_failure_and_invalid_arguments(self):
        with PTYSession(["/nonexistent/assist-test-shell"]) as session:
            until(session, b"could not be started")
            self.assertEqual(session.wait(), 127)
        for argv in ([], [""], ["bad\0argument"]):
            with self.assertRaises(ValueError):
                PTYSession(argv)
        with self.assertRaises(ValueError):
            PTYSession([sys.executable], rows=0)

    def test_available_shells_use_transport_without_claiming_buffer_support(self):
        # This is transport coverage, not validation of shell editing adapters.
        for name in ("bash", "zsh", "fish", "sh"):
            executable = shutil.which(name)
            if executable is None:
                continue
            with self.subTest(shell=name), PTYSession([executable, "-c", "printf 'SHELL_OK\\n'"]) as session:
                until(session, b"SHELL_OK")
                self.assertEqual(session.wait(), 0)
                self.assertFalse(session.editable_buffer_available)

    @unittest.skipUnless(shutil.which("bash"), "Interactive Bash fixture requires Bash")
    def test_transport_does_not_append_enter_or_submit_an_editable_command(self):
        with tempfile.TemporaryDirectory(dir="/tmp/opencode", prefix="assist-pty-buffer-") as root:
            target = Path(root) / "explicit-enter-only"
            env = {**os.environ, "PS1": "ASSIST_TEST_PROMPT> ", "PROMPT_COMMAND": "", "TERM": "xterm"}
            with PTYSession([shutil.which("bash"), "--noprofile", "--norc", "-i"], env=env) as session:
                until(session, b"ASSIST_TEST_PROMPT>")
                session.write(("printf fixture > " + shlex.quote(str(target))).encode())
                time.sleep(0.1)
                self.assertFalse(target.exists(), "Transport must not implicitly submit input")
                session.write(b"\n")  # Explicit user Enter, not a preview action.
                until(session, b"ASSIST_TEST_PROMPT>")
                self.assertEqual(target.read_text(), "fixture")
                session.write(b"exit\n")
                self.assertEqual(session.wait(), 0)


if __name__ == "__main__":
    unittest.main()
