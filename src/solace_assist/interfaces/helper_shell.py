"""Opt-in real shell + helper panes on an isolated tmux PTY server."""

from importlib.resources import files
from contextlib import contextmanager
import os
import importlib.util
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile

from solace_assist.interfaces import helper_state
from solace_assist.interfaces.palette import load_palette, system_palette_path


@contextmanager
def shutdown_signals():
    def interrupted(signum, frame):
        raise InterruptedError("Interactive helper interrupted; its private session was closed")
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def shell_spec(executable=None):
    executable = executable or os.environ.get("SHELL") or pwd.getpwuid(os.getuid()).pw_shell
    resolved = shutil.which(executable)
    if not resolved or not os.path.isabs(resolved):
        raise ValueError("Choose an installed shell executable, not a shell command string")
    return resolved, Path(resolved).name == "bash"


def start(catalog, executable=None):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Interactive helper mode needs a real terminal")
    tmux = shutil.which("tmux")
    if not tmux:
        raise ValueError("Interactive helper mode needs tmux; the ordinary catalog works without it")
    if importlib.util.find_spec("textual") is None:
        raise ValueError("Interactive helper mode needs the optional Textual TUI dependency")
    shell, bash = shell_spec(executable)
    runtime = os.environ.get("XDG_RUNTIME_DIR") or None
    if runtime and (not Path(runtime).is_dir() or not os.access(runtime, os.W_OK)):
        runtime = None
    with shutdown_signals(), tempfile.TemporaryDirectory(prefix="sbtools-helper-", dir=runtime) as temp:
        root = Path(temp)
        socket = str(root / "tmux.sock")
        helper_state.write(root, "session.json", {"shell": shell, "bash": bash, "database": str(catalog.path)})
        (root / "bashrc").write_text(files("solace_assist").joinpath("data/helper.bash").read_text())
        env = {**os.environ, "SBTOOLS_HELPER_SESSION": str(root), "SBTOOLS_HELPER_PYTHON": sys.executable}
        # An existing tmux server/config is never reused or altered.
        env.pop("TMUX", None)
        base = [tmux, "-S", socket, "-f", "/dev/null"]
        def run(*args, **kwargs):
            return subprocess.run([*base, *args], env=env, check=True, **kwargs)
        size = shutil.get_terminal_size((140, 42))
        try:
            run("new-session", "-d", "-s", "assist", "-x", str(size.columns), "-y", str(size.lines),
                sys.executable, "-m", "solace_assist.interfaces.helper_shell", "worker")
            run("set-option", "-g", "default-terminal", "tmux-256color")
            run("set-option", "-g", "history-limit", "0")  # No retained shell scrollback in this server.
            run("set-option", "-g", "status-right-length", "150")
            run("set-option", "-g", "status-right", "Ctrl+B arrows: pane | Ctrl+G: context | Ctrl+X Ctrl+I: insert | exit: close")
            colors = load_palette(system_palette_path())
            if colors:
                run("set-option", "-g", "status-style", f"bg={colors['background']},fg={colors['accent']}")
            run("split-window", "-h", "-p", "48", "-t", "assist:0", sys.executable, "-m", "solace_assist.interfaces.cli",
                "--db", str(catalog.path), "_helper", str(root))
            run("select-pane", "-t", "assist:0.0")
            result = subprocess.run([*base, "attach-session", "-t", "assist"], env=env)
            exited = helper_state.read(root, "exit.json")
            code = exited.get("status", result.returncode) if exited else result.returncode
            return code if code >= 0 else 128 - code
        finally:
            subprocess.run([*base, "kill-server"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def worker():
    root = Path(os.environ["SBTOOLS_HELPER_SESSION"])
    session = helper_state.read(root, "session.json")
    argv = [session["shell"], "--rcfile", str(root / "bashrc"), "-i"] if session["bash"] else [session["shell"], "-i"]
    try:
        result = subprocess.run(argv, check=False)
        helper_state.write(root, "exit.json", {"status": result.returncode})
    finally:
        subprocess.run(["tmux", "-S", str(root / "tmux.sock"), "kill-session", "-t", "assist"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__" and sys.argv[1:] == ["worker"]:
    worker()
