"""Private short-lived helper IPC. No raw command buffers or shell output stored."""

import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from solace_assist.core.templates import preview


def directory(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Helper directory must be a private, owned real directory")
    return path


def read(path, name):
    path = directory(path) / name
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 65536:
            raise ValueError("Unsafe helper state file")
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError("Helper state is too large")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Helper state must be an object")
    return result


def write(path, name, data):
    path = directory(path)
    raw = json.dumps(data).encode()
    if len(raw) > 65536:
        raise ValueError("Helper state is too large")
    fd, temp = tempfile.mkstemp(prefix=".state-", dir=path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.replace(temp, path / name)
    finally:
        Path(temp).unlink(missing_ok=True)


def context(path, buffer):
    # This is a conservative executable hint, not parsing a shell program. Never
    # persist the full buffer (which could contain credentials), flags or values.
    executable = None
    if len(buffer) <= 65536 and not any(ord(c) < 32 or ord(c) == 127 for c in buffer):
        match = re.match(r"^\s*(?:sudo\s+)?([A-Za-z0-9_./+-]+)(?=\s|$)", buffer)
        if match:
            executable = Path(match[1]).name
    write(path, "context.json", {"executable": executable, "updated": time.time_ns(),
                                  "capability": "bash-readline-explicit-key"})


def queue(path, template_id, arguments, authorized=False):
    ready = read(path, "ready.json")
    if not ready or ready.get("shell") != "bash":
        raise ValueError("Command staging needs the session's Bash Readline adapter; other shells are read-only")
    result = preview(template_id, arguments, "bash")
    write(path, "pending.json", {"template": template_id, "arguments": arguments})
    return result


def consume(path):
    pending = read(path, "pending.json")
    if pending is None:
        return None
    if set(pending) not in ({"template", "arguments"}, {"template", "arguments", "authorized"}):
        raise ValueError("Invalid staged preview")
    if "authorized" in pending and type(pending["authorized"]) is not bool:
        raise ValueError("Invalid legacy staged preview")
    result = preview(pending["template"], pending["arguments"], "bash")
    command = result["command"]
    # Defense in depth at the transport boundary: never return Enter/escapes.
    if not command or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in command):
        raise ValueError("Unsafe insertion text")
    (directory(path) / "pending.json").unlink()
    return command
