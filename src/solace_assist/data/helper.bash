# Session-local only; never installed into or appended to the user's startup file.
if [[ -r $HOME/.bashrc ]]; then
  source "$HOME/.bashrc"
fi

__sbtools_context() {
  printf '%s' "$READLINE_LINE" | "$SBTOOLS_HELPER_PYTHON" -m solace_assist.interfaces.shell_bridge context
}

__sbtools_insert() {
  # Do not overwrite existing work, insert into a running program, or submit.
  if [[ -n $READLINE_LINE ]]; then
    printf '\a'
    return
  fi
  local candidate
  if candidate=$("$SBTOOLS_HELPER_PYTHON" -m solace_assist.interfaces.shell_bridge consume) && [[ -n $candidate ]]; then
    READLINE_LINE=$candidate
    local LC_ALL=C
    READLINE_POINT=${#READLINE_LINE}
  else
    printf '\a'
  fi
}

bind -m emacs-standard -x '"\C-g":__sbtools_context'
bind -m emacs-standard -x '"\C-x\C-i":__sbtools_insert'
bind -m vi-insertion -x '"\C-g":__sbtools_context'
bind -m vi-insertion -x '"\C-x\C-i":__sbtools_insert'
"$SBTOOLS_HELPER_PYTHON" -m solace_assist.interfaces.shell_bridge ready
printf '\nSolace Assist prototype: Ctrl+G shows command context; Ctrl+X then Ctrl+I inserts a staged preview at an EMPTY prompt. Press Enter yourself to run it.\n\n'
