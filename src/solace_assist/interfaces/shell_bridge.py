"""Called only by session-local Readline widgets; no terminal-output scraping."""

import os
import sys

from solace_assist.interfaces import helper_state


def main():
    path = os.environ["SBTOOLS_HELPER_SESSION"]
    action = sys.argv[1]
    if action == "ready":
        helper_state.write(path, "ready.json", {"shell": "bash", "insertion": "explicit-key-empty-buffer-only"})
    elif action == "context":
        helper_state.context(path, sys.stdin.read(65537))
    elif action == "consume":
        command = helper_state.consume(path)
        if command:
            sys.stdout.write(command)  # Intentionally no newline or Enter.
    else:
        raise ValueError("Unknown bridge action")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        # Do not print a buffer, credential, traceback or command at a prompt.
        raise SystemExit(1)
