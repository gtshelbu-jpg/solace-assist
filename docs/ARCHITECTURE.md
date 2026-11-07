# Interfaces and safety contracts

The core receives explicit requests and returns data: tools, packages, executables,
categories, ranked results, documentation with provenance, and template previews.
No UI maintains its own tool database or package installation implementation.

Metadata records source/repository/version/time and supports many tools/executables
per package. Treat downloaded strings/markup/FTS input as untrusted data. Never
execute upstream help commands during bulk import. Unknown flags stay unknown.

The shell interface must distinguish: shell executable/arguments; supported grammar;
buffer/cursor positions; adapter provenance; and unavailable capabilities. A PTY is
not a terminal emulator and output is not the editable command buffer. Rendering
and shell adapters must be replaceable without changing catalog or template APIs.

All template expansion uses typed arguments and a reviewed shell-specific renderer.
Unsupported grammars get documentation/copyable structured previews, not guessed
quoting or evaluation. Inserts must not include implicit submission. Local IPC
uses user-only permissions; no long-lived service is required for catalog browsing.

Arch packaging may expose separate optional TUI/Elephant components from this one
source project. No Python/Go plugin ABI or desktop dependency belongs in the core.

The initial Walker adapter is `interfaces/launcher.py`: a task prompt, shared-core
ranked search, explicit offered-result selection, and an argument-vector launch of
`sbtools browse`. It never launches the selected executable or interpolates shell
commands. `core/templates.py` offers typed, nonexecuting previews with separate
shell renderers and a structured-only generic mode. `interfaces/pty_transport.py`
is a POSIX transport foundation only; editable-buffer capability is explicitly
false. No public assisted-shell command is enabled by these foundations.
