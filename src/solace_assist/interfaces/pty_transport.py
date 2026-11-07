"""POSIX PTY transport foundation, not a terminal emulator or shell-buffer adapter.

No template insertion or generated-command submission exists here. Callers must
keep user keystrokes, explicit process arguments, and future buffer adapters
separate. Nothing is inferred from terminal output.
"""

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import termios
import time


class PTYSession:
    editable_buffer_available = False

    def __init__(self, argv, *, env=None, rows=24, columns=80):
        if not argv or not all(isinstance(arg, str) and "\0" not in arg for arg in argv) or not argv[0]:
            raise ValueError("An explicit nonempty executable/argument vector is required")
        self._validate_size(rows, columns)
        self.status = None
        self.closed = False
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            try:
                fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
                os.execvpe(argv[0], argv, os.environ.copy() if env is None else env)
            except BaseException:
                # No Python traceback or accidental return into the parent's UI.
                try:
                    os.write(2, b"Assist PTY: executable could not be started\r\n")
                except OSError:
                    pass
                os._exit(127)

    @staticmethod
    def _validate_size(rows, columns):
        if not all(type(n) is int and 1 <= n <= 1000 for n in (rows, columns)):
            raise ValueError("PTY dimensions must be integers between 1 and 1000")

    def resize(self, rows, columns):
        self._validate_size(rows, columns)
        if self.closed:
            raise ValueError("PTY is closed")
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    def read(self, timeout=0.1):
        """Return bytes, None on timeout, or b'' at EOF. Never parse shell output."""
        if self.closed:
            return b""
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        try:
            return os.read(self.fd, 65536)
        except OSError as error:
            if error.errno == errno.EIO:  # Linux PTY slave has closed.
                return b""
            raise

    def write(self, data):
        """Send explicit caller-provided bytes; no quoting, completion or newline."""
        if self.closed:
            raise ValueError("PTY is closed")
        if not isinstance(data, bytes):
            raise TypeError("PTY writes require bytes")
        view = memoryview(data)
        while view:
            size = os.write(self.fd, view)
            view = view[size:]

    def poll(self):
        if self.status is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.status = os.waitstatus_to_exitcode(status)
        return self.status

    def wait(self, timeout=2):
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError("PTY child has not exited")
            time.sleep(0.01)
        return self.status

    def close(self):
        if self.closed:
            return
        # Closing the master sends HUP to its controlling session. Escalate only
        # our own, unreaped child if it ignores HUP; never signal arbitrary PIDs.
        os.close(self.fd)
        self.closed = True
        if self.poll() is None:
            try:
                self.wait(0.3)
            except TimeoutError:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.wait(2)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
