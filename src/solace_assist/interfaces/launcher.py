"""Optional Walker adapter to the shared catalog. Selection opens docs, not tools."""

import shutil
import subprocess

from solace_assist.core.catalog import text


def choose(args, content=None):
    result = subprocess.run(["walker", "--dmenu", *args], input=content, text=True, capture_output=True)
    if result.returncode != 0:
        if result.returncode in (1, 130):
            return None
        raise ValueError("Walker could not open the tool search; use sbtools search or the explorer instead")
    return result.stdout.strip() or None


def launch(catalog, query=""):
    if not shutil.which("walker") or not shutil.which("xdg-terminal-exec"):
        raise ValueError("Task launcher needs Walker and xdg-terminal-exec; standalone sbtools search and the TUI remain available")
    if not query:
        query = choose(["--inputonly", "-p", "Describe a task — opens documentation, never runs tools"])
        if query is None:
            return 0
    # The normal core enforces query limits, FTS escaping and ranking.
    rows = catalog.search(query, limit=50)
    if not rows:
        choose(["-p", "No matching tools — try a different task"], "No matching tools\n")
        return 0
    labels = {}
    for index, row in enumerate(rows, 1):
        purpose = " ".join(text(row["purpose"], 180).split())
        name = " ".join(text(row["name"], 100).split())
        status = "installed snapshot" if row["installed"] else "catalog" if row["available"] else "reference"
        label = f"{index:02d}  {name} — {purpose} [{status}]"
        labels[label] = row["id"]
    selection = choose(["-p", "Open tool documentation — not execution"], "\n".join(labels) + "\n")
    if selection is None:
        return 0
    # Never treat custom launcher input as a command or reconstructed tool ID.
    if selection not in labels:
        raise ValueError("Select an offered result; arbitrary input is not executed")
    subprocess.Popen(["xdg-terminal-exec", "--app-id=org.solace.sbtools", "-e",
                      "sbtools", "--db", str(catalog.path), "browse", labels[selection]],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return 0
