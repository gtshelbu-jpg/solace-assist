# Interactive-helper prototype boundaries

`sbtools shell` is an explicit, offline, terminal-based prototype. It does not
replace a user's login shell, terminal shortcut or ordinary tmux configuration.
It launches the chosen shell in a dedicated tmux PTY alongside the catalog TUI.
The TUI's tasks and forms use the same catalog and typed templates as the CLI.
No model, remote API, package installation or automatic tool invocation is used.

## Truthful command context

Only the session-local Bash `bind -x` widget reads `READLINE_LINE`. Ctrl+G is an
explicit request for a conservative first-executable hint; supported literal
`sudo command` and path prefixes are recognized without evaluating shell syntax.
Complex/unknown syntax falls back to manual search. The raw buffer is received
through stdin, not command-line arguments, and is discarded. Only the executable
hint and update timestamp are written to the private helper runtime directory.
Terminal output, command history, passwords and program input are not scraped.

## Deliberate insertion, separate from execution

Generating a preview is read-only. Staging is a separate button and writes typed
template arguments, not an arbitrary executable action. The Bash insertion widget
is another explicit action: Ctrl+X then Ctrl+I while Readline owns an empty prompt.
It refuses nonempty buffers, revalidates the reviewed template and arguments,
renders Bash quoting, rejects control characters, and assigns `READLINE_LINE`.
It never uses `eval`, types terminal keys or appends a newline/Enter. Cursor byte
position is set at the end. If a program owns the terminal, the Readline widget
does not run; it cannot inject into a password prompt, editor or running tool.

The user must independently review and press Enter to execute through their own
shell. This also means the user's normal shell history policy still applies to
commands they explicitly execute; Assist does not rewrite that preference.

## Scope and limitations

- Bash is the editing prototype. Zsh, Fish, sh and unknown shells are read-only
  fallbacks, not silently switched shells or guessed editing adapters. Generic
  previews are structured argv unless the user explicitly selects a renderer.
- This does not understand arbitrary shell programs, pipelines, aliases, functions,
  expansions or grammar semantics. Context is a documentation hint, not an audit
  or assertion that a command is safe. No command output is interpreted.
- Template coverage is intentionally limited to reviewed guides; imported package
  metadata is not invented command knowledge. Network templates require explicit
  authorization and bounded scope, but authorization is still the user's duty.
- Context and pending files use owned 0700 directories/0600 regular files, reject
  symlink/nonregular reads, bound sizes and get removed on normal teardown. This
  is same-user IPC, not a security boundary against malicious code under that user.
- Normal exit, terminal HUP and TERM tear down only this private tmux server.
  SIGKILL/crashes cannot guarantee cleanup; this is not secure erasure. Detach
  ends the disposable helper too. Do not use it for irreplaceable long-lived jobs.
- Nested tmux requires normal nested-prefix handling. Start from a plain terminal
  for the simplest first test. Full cross-shell editing support remains future work.

Automated tests use disposable homes, real PTYs and an explicit execution-marker
stub to prove staging/insertion alone never executes. No test probes external
networks or captures traffic. Passing tests do not validate every real shell rc,
terminal emulator, tmux version or physical keyboard configuration.
