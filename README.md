# Solace Assist — offline tool explorer MVP

An independent security-tool catalog with one SQLite FTS5 database shared by a
CLI and keyboard-driven Textual TUI. It runs without Solace, BlackArch, Hyprland,
Elephant, a particular terminal emulator, an AI model or a network service.

**Alpha software, not a released distribution package.** The PTY shell, command
templates, package installation actions and Elephant integration are future
milestones. `sbtools shell` is deliberately not implemented rather than pretending
a text widget is a real shell. No shell startup file or desktop shortcut changes.

## Run locally

Python 3.11+ with SQLite FTS5 is required. Use a project virtual environment; never
install into Arch's system Python with global pip:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[tui]'
.venv/bin/sbtools
```

For CLI only, install `-e .` without the optional `tui` extra. Textual 8.2.8 was
used for the initial UI validation; older/newer untested versions may differ.

```bash
.venv/bin/sbtools search "enumerate smb"
.venv/bin/sbtools search "analyze firmware"
.venv/bin/sbtools show binwalk
.venv/bin/sbtools category wireless
.venv/bin/sbtools installed
.venv/bin/sbtools info --json
```

The first run seeds 14 **purpose/task references** with upstream documentation
links. They are not assertions that packages are available or installed, and are
not verified usage guides. No flags or command examples are inferred. Imported
package metadata is labelled separately from curated purpose descriptions.

## Explicit metadata synchronization

```bash
# Read existing local Pacman sync caches and installed metadata; never pacman -Sy.
.venv/bin/sbtools sync
# Import a separately acquired BlackArch/Pacman metadata snapshot without enabling a repo.
.venv/bin/sbtools sync --repo-db /path/to/blackarch.db --repository blackarch --no-installed
# Fast refresh without installed executable-file discovery:
.venv/bin/sbtools sync --no-executables
```

No command downloads data, installs packages, imports signing keys or configures
repositories. Source synchronization reads `.db` archive members without extracting
files and uses only `pacman -Q`/`pacman -Ql` for installed status/file metadata.
The metadata adapters do not execute tool help commands or assume one executable
per package. A tool/package may have multiple executable/source/version records.

**Metadata provenance is explicit:** local caches inherit the administrator's
Pacman workflow; imported archives are not independently signature-verified by
Assist. This is discovery data, never authorization to install/execute a binary.
Package installation remains with the user's verified package-management process.
No unsigned-package bypass or repository trust change exists in this application.

Offline browsing uses the last imported snapshot. Installed status can be stale;
`info` reports the last installed refresh time. On non-Arch systems the bundled
catalog and explicit metadata imports work, but automatic installed detection is
currently Pacman-only. Additional distro adapters are not silently simulated.

## Personal knowledge

```bash
.venv/bin/sbtools favorite nmap
.venv/bin/sbtools note nmap --text 'My own observation'
.venv/bin/sbtools note nmap --stdin < my-note.md
.venv/bin/sbtools tag nmap lab
.venv/bin/sbtools search --favorites --tag lab
```

Favorites, notes, tags and recently viewed tool IDs are stored locally in
`$XDG_DATA_HOME/solace-assist/catalog.sqlite3` (normally
`~/.local/share/solace-assist/catalog.sqlite3`). The database is private mode 0600;
catalog refresh does not erase personal tables. Nothing is sent externally.
Do not put credentials in tool notes or commit database files.

Override storage **before the subcommand**, useful for disposable tests:

```bash
.venv/bin/sbtools --db /tmp/assist-demo.sqlite3 search "decode radio signals"
```

## TUI navigation

- Type in the search bar; task words use the same FTS/curated keywords as the CLI.
- Tab between categories, results and filters; Ctrl+G focuses categories.
- F toggles a favorite while results have focus.
- Ctrl+R explicitly synchronizes local metadata in a background worker.
- Enter on a result opens its detail page on narrow terminals; Esc returns.
- Ctrl+Q quits. Browsing and selection never launch a tool.

Search is bounded/debounced, and worker results are generation-checked so stale
queries do not replace newer results. Narrow 80-column terminals have a separate
detail view; larger terminals show categories/results/details side by side.
Notes/tags can be edited through the CLI and are visible in tool details.

## Architecture and validation

`core/catalog.py` owns data, ranking, provenance and personal state. `sources/`
contains read-only importers. `interfaces/` contains the CLI and optional TUI.
Editable seed material lives in `src/solace_assist/data/catalog.json` and is shipped
as package data, not duplicated into an independent launcher catalog.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover task search, import rollback, archive boundaries, privacy, persistence,
5,000-record performance, read-only Pacman calls, CLI commands and headless TUI
interaction at wide/narrow sizes. Real local metadata and a BlackArch snapshot
were also indexed into a disposable database; this does not validate tool binaries,
package signatures, every tool's documentation or physical terminal compatibility.

## Shell independence and later milestones

Normal terminals/login shells remain unchanged. PTY transport, terminal rendering,
syntax parsing and editable-buffer adapters are separate responsibilities. No
Zsh-only assisted-shell release or silent shell switch is acceptable. Bash, Zsh,
Fish and generic/unknown-shell fallback need explicit integration tests. An
unsupported grammar gets documentation/manual context, not guessed quoting or
reconstructed buffers from terminal output. Commands must never auto-submit.

Next: verified command guides/templates, then a thin optional Elephant adapter;
real assisted-shell mode remains its own engineering milestone. Black does not
depend on Assist to boot. Root/source/documentation licensing must be settled
before public releases; no license is invented for inherited material here.
