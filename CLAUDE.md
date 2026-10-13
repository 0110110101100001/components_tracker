# PC monitor — notes for Claude

Sibling of `~/Desktop/token_tracker` (the Claude cost meter). The user asked for "the same window" showing component load instead of tokens, so the look is copied on purpose: same CSS colours, monospace 11 px rows, 240 px width at scale 1.0, header word + mark, separators, drag-to-move, edge-drag scaling (0.7–3×), right-click menu with a white background. Keep it visually in step with the tracker if that one changes.

## Deliberate differences from the tracker
- Header mark is three live bars (CPU, RAM, GPU load) drawn in teal `MARK_COLOUR`, not the terracotta Anthropic logo, so the two panels tell apart at a glance.
- Opens anchored to the **top-right** of the primary monitor (the tracker opens at the origin / bottom-right); it re-anchors on every size change until the user drags it (`anchored` flips on a body drag). Position is not persisted, same reasoning as the tracker (a remembered position on another monitor makes the panel "vanish"). Only the scale is persisted, in `data/window.json`.
- No liveness lock / pid file: `pixi run start` runs it as the transient systemd user service `pc-monitor`, and systemd refuses a second unit with the same name ("Unit pc-monitor.service was already loaded"). A service (not `--scope`) is what detaches it from the terminal's cgroup; DISPLAY, XAUTHORITY and GDK_BACKEND are passed with `--setenv` because services do not inherit the caller's environment. `pixi run panel` bypasses this (foreground, for debugging).
- No Claude hooks, no Patrik mode/sound.

## Autostart (added 2026-10-12)
- User asked for the panel to open whenever a terminal opens, including editor-integrated terminals (VS Code, Cursor). Done by appending `source "$HOME/Desktop/pc_monitor/shell_autostart.sh"` to the end of `~/.bashrc` (after the pixi PATH line, which it needs).
- Guarded to interactive shells with `$DISPLAY`: Claude Code's Bash tool and scripts are non-interactive, SSH has no DISPLAY, so neither spawns a panel. The `systemctl --user is-active` check costs ~10 ms per terminal; `pixi run start` only runs when the panel is down, backgrounded in a subshell so the prompt is not delayed.
- Consequence: quitting the panel from its menu lasts only until the next terminal opens. That is what the user asked for.
- Not a login autostart (`~/.config/autostart`) — the user asked specifically for terminal start.
- Verified: stop → `bash -ic exit` → unit active; second `bash -ic exit` → still one window.

## Row icons (icons.py, added 2026-10-12)
- User asked for a picture of the component beside each row. Hand-drawn 24×24 stroke SVGs (own work, no third-party licence): CPU chip, RAM stick (also used for vram), graphics card with two fans + bracket, lightning bolt (gpu power), hard drive (also disk r/w), RJ45 port (net).
- Rendered per row by `Icon` (Gtk.DrawingArea + librsvg) so they stay sharp at every scale; colour is `ACCENT`, the same teal as the header mark. librsvg is a hard dependency here (unlike the tracker, where the logo is optional).
- Icon + caption sit in one HBox in grid column 0 with `ICON_SPACING`; the grid's 12 px column spacing would be too wide between icon and caption. Separators still span the 2 grid columns.

## Data sources (sensors.py)
- CPU load: `psutil.cpu_percent()` between refreshes (primed once in `Sampler.__init__`, the first call always returns 0).
- "cores" row (added 2026-10-12, user asked how many cores are loaded): `psutil.cpu_percent(percpu=True)` counts **logical** CPUs (32 = 16 cores × SMT) at or above `busy_core_percent` (config, default 50). Coloured by busy fraction against `load_thresholds`. psutil keeps separate last-sample state for total and per-CPU calls, so both are primed in `Sampler.__init__`. Context: the user saw 100 % during hand-to-eye `03_detect_grid`, which forks ~33 workers, one per thread.
- CPU temp: `k10temp`/`Tctl` (AMD) or `coretemp`/`Package id 0` (Intel). This machine: Ryzen 9 9950X3D → k10temp.
- RAM used = total − available (what "really used" means; excludes cache).
- GPU: NVML via `nvidia-ml-py`, device 0 only (RTX 5090 here; the amdgpu iGPU is ignored). `open_gpu()` returns None and prints to stderr when NVML init fails; rows show a muted `—`.
- Disk fill: `psutil.disk_usage(disk_mount).percent` (excludes root-reserved blocks, so it reads ~1 % lower than `df`). Disk r/w and net rates: deltas of cumulative counters over the real elapsed time; net excludes `lo`.
- Colour: `level()` per figure, `worst()` combines load and temperature for cpu/gpu rows. "plain" = no colour class (rates, power).

## Measured (2026-10-12)
- Panel process: <1 % CPU, ~85 MB RSS at 1 s refresh.
- Root fs `/` was at 98 % (19 GB free) on first run, so the disk row shows red — real, not a bug.
- Displays: two 6144×3456 monitors at scale 2 under XWayland; primary DP-6 at x=6144. Panel landed at +11760+364 (top-right of DP-6), correct.

## Open ideas (not built — YAGNI until asked)
- Per-core / per-disk breakdown in tooltips, swap row, fan speeds.
