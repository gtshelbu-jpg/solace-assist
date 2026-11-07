# Solace Assist — offline tool explorer MVP

An independent security-tool catalog with one SQLite FTS5 database shared by a
CLI and keyboard-driven Textual TUI. It runs without Solace, BlackArch, Hyprland,
Elephant, a particular terminal emulator, an AI model or a network service.

**Alpha software, not a production binary distribution.** `sbtools shell` is now
an opt-in interactive-helper prototype with a real tmux PTY shell and offline
guidance alongside it. Bash has an explicit-key Readline adapter; other shells
remain read-only without being replaced. It is not an AI agent or an automatic
command runner. Package installation actions and an Elephant provider remain
future milestones. No persistent shell startup file or global keyboard-binding changes.
The native Arch package adds a **Solace Assist** application-menu entry that opens
the real offline explorer in a terminal; it does not launch a security tool.

## Run locally

Python 3.11+ with SQLite FTS5 is required. Use a project virtual environment; never
install into Arch's system Python with global pip:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[tui]'
.venv/bin/sbtools
```

For CLI only, install `-e .` without the optional `tui` extra. The TUI requires
Textual 8.2.8 or newer; 8.2.8 is the currently validated version.

```bash
.venv/bin/sbtools search "enumerate smb"
.venv/bin/sbtools search "analyze firmware"
.venv/bin/sbtools show binwalk
.venv/bin/sbtools category wireless
.venv/bin/sbtools installed
.venv/bin/sbtools info --json
```

The catalog includes 14 **purpose/task references**, eight with enriched descriptions,
option explanations and source-checked example guides: Nmap, tcpdump, Wireshark/TShark,
readelf, smbclient, Binwalk, Gobuster and RTL-SDR. Each guide records upstream sources,
review date and version scope. Source review is not runtime validation: review the
examples and installed version before running anything. Assist never executes them.
References are not assertions that packages are available or installed. Imported
package metadata remains labelled separately; no guides are invented for it.

Existing version-1 databases are backed up beside the database before migration,
including committed WAL contents. Bundled content refreshes automatically while
preserving notes, tags, favorites, history and imported snapshots. `info` reports
the migration backup filename. Close older Assist sessions before upgrading.

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

## Optional task-search launcher

On a Walker desktop, open **Solace Assist Search** from the application menu or
run `sbtools launch`. Describe a task, choose a ranked result, and its documentation
opens in the terminal explorer. `sbtools launch enumerate smb` skips the initial
task prompt. The adapter calls the same catalog search as the CLI/TUI, not a
separate launcher database. It requires Walker and `xdg-terminal-exec` only when
invoked; ordinary standalone browsing has neither dependency. Normal application
launcher and terminal shortcuts are not replaced. No Elephant configuration is
modified. Cancellation does nothing; custom result text is never executed.

## Reviewed command previews

Four initial templates cover readelf headers/symbols, offline tcpdump capture-file
inspection, and Nmap service probes on one explicitly authorized IP/port list:

```bash
sbtools templates
sbtools preview readelf-header --arg 'file=a sample.elf' --shell bash
sbtools preview tcpdump-file --arg 'file=existing.pcap' --json
```

Previews never execute, insert, copy or submit commands. Values are typed and
control characters are rejected. The default `generic` mode returns structured
arguments, not guessed shell syntax. Bash/POSIX, Zsh and Fish renderers are
separate; tests round-trip literal arguments through whichever shells are
available. This is not validation of cross-shell editable-buffer adapters.
The network template takes a single IP (no subnet or hostname expansion) and
explicit bounded ports, with no acknowledgment checkbox or flag. Read the bundled guide
and check the actual installed version before manually using any preview.

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

- The explorer starts with **Reviewed guides** selected, not an alphabetical dump
  of all imported packages. Uncheck it to browse metadata-only entries.
- **Start a task / Ctrl+T** offers guided starting workflows; **Build command /
  Ctrl+P** opens a typed form with option explanations and an explicit preview.
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

## Try the interactive helper prototype

Install the optional Textual dependency and tmux, then run from a normal terminal:

```bash
sbtools shell
```

Or open **Solace Assist Helper (Prototype)** from the native application menu.
The left pane is your selected interactive shell, with normal terminal rendering,
job control and programs handled by tmux's real PTYs. The right pane is the themed
offline helper, not a simulated shell widget.

1. In Bash, type `readelf` **without Enter**, then press **Ctrl+G**. The helper
   shows the matching guide. Only a conservative executable hint is shared; the
   command's arguments, credentials and terminal output are not scraped or saved.
2. Switch right with **Ctrl+B, Right**. Use **Ctrl+T** for a task or **Ctrl+P**
   to build a reviewed command. The first argument is focused; **Enter** previews.
3. **Ctrl+Enter** stages directly from the current fields (or use **Stage for shell**).
   Nothing is inserted yet. No extra acknowledgment is required.
4. Switch left with **Ctrl+B, Left**. Clear any existing input yourself. Press
   **Ctrl+X, then Ctrl+I** at the empty prompt. The Bash adapter inserts the
   revalidated single-line preview, **without Enter**. Nonempty input is never
   overwritten. Review/edit it and press Enter yourself if you want to execute it.
5. `exit` or Ctrl+D at an empty shell prompt closes this disposable helper.

Bash startup settings are sourced through a temporary session-only rc wrapper;
your `.bashrc` and login-shell choice are not modified. The two helper bindings
apply only inside this session (Emacs and Vi insertion keymaps). Zsh, Fish, POSIX
sh and unknown shells keep their original executable and get read-only guidance;
no editable buffer or insertion capability is claimed for them. Choose a Bash
session explicitly with `sbtools shell --shell /usr/bin/bash` if desired.

Each helper uses a private tmux server/socket, not an existing tmux server or
configuration. Detaching or closing its terminal ends this disposable session and
its jobs; it is not a persistent job manager. Private runtime state and staged
fields are cleaned on normal exit, HUP or TERM. A forced SIGKILL/system crash may
leave private runtime files until removed or the runtime directory is cleared.
See [interactive-helper boundaries](docs/INTERACTIVE_HELPER.md).

### Appearance

On Solace, the explorer reads the active `solace/current/theme/colors.toml` under
`$XDG_CONFIG_HOME` (normally `~/.config`). Background, text, panel and accent colours
follow that palette, including widget focus/selection and warning/error colours.
It checks for palette changes once per second without resetting search, focus or
personal data. Reopening is not required after changing the system theme.

This bridge is optional and read-only: no Solace command is executed or required.
Without a valid palette, startup uses Assist's standalone dark theme. Invalid or
partially written updates keep the last good palette. Only validated hex colours
and light/dark mode are accepted; palette files cannot supply CSS or commands.

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

The standalone PTY transport remains a separate tested foundation. The prototype
shell UI delegates terminal emulation/job control to tmux and uses Bash Readline
for truthful editing state, never terminal-output reconstruction. Tests cover
actual PTYs, nonempty-buffer preservation, no implicit Enter, explicit execution
of a test stub, private state, generic read-only fallback and server cleanup.

Next: richer source-checked templates, a thin optional Elephant provider and
validated Zsh/Fish editing adapters. This is not a finished cross-shell release. Black does not
depend on Assist to boot. Original code and documentation are MIT licensed; see
LICENSE and NOTICE for third-party boundaries. Native package signing and binary
release validation remain separate milestones.
