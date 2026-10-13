# Sourced from ~/.bashrc: opens the PC monitor panel when a terminal starts
# (any terminal, including the ones inside VS Code or Cursor) unless it is up already.
# Interactive shells with a display only, so scripts and SSH sessions stay untouched.
if [[ $- == *i* && -n $DISPLAY ]] && ! systemctl --user is-active --quiet pc-monitor; then
    (pixi run --manifest-path "$HOME/Desktop/pc_monitor/pixi.toml" start >/dev/null 2>&1 &)
fi
