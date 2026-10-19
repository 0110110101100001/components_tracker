# PC monitor

Always-on-top panel showing how loaded each PC component is (CPU, RAM, GPU, VRAM, disk, network), in the same look as the Claude token tracker. Runs on Linux and Windows (linux-64, win-64).

## Install

```bash
pixi install
pixi run smoke-test
```

## Run

```bash
pixi run start     # open the panel (survives closing the terminal)
pixi run stop      # close it
pixi run panel     # foreground, to see errors
```

Every task is in `pixi.toml`. On Linux `start`/`stop` go through a systemd user service, on Windows through `winpanel.py` (detached `pythonw`, no console window; startup errors land in `data/panel.log`).

**Autostart (Linux):** `~/.bashrc` sources `shell_autostart.sh`, so opening any terminal (also inside VS Code / Cursor) opens the panel if it is not running. To turn it off, delete the `source …/shell_autostart.sh` line from `~/.bashrc`.

**Autostart (Windows):** `pixi run autostart` opens the panel at every login (a `pc-monitor` value in `HKCU\…\CurrentVersion\Run` that runs `autostart.vbs`, i.e. `pixi run start` without a console window). `pixi run autostart-off` removes it; Task Manager → Startup can also disable it. Re-run `pixi run autostart` if the project folder or pixi moves.

## Structure

```
config.yaml   refresh rate, disk to watch, colour thresholds
sensors.py    reads the figures (psutil, NVML) and formats the rows
widget.py     the GTK panel
winpanel.py   Windows start/stop (what systemd does on Linux) and login autostart
autostart.vbs Windows login launcher, registered by `pixi run autostart`
icons.py      the component icons (SVG) shown beside each row
shell_autostart.sh  sourced from ~/.bashrc, opens the panel with each terminal
tests/        unit tests + off-screen render of the panel
data/         remembered panel size (created on first resize); Windows: panel.log
```

## Notes

- Drag the middle to move, drag an edge or corner to resize. Right click: reset position, reset size, quit.
- Colours: green / amber / red by the thresholds in `config.yaml`; the cpu and gpu rows go red on either load or temperature.
- `cores` = how many CPU threads (32 on this machine) are at least `busy_core_percent` loaded.
- Hover the gpu row for the GPU name. Without an NVIDIA driver the GPU rows show `—`; so does `gpu power` where the driver does not report it (laptop GeForces).
- Windows shows no CPU temperature (it exposes none without admin rights), so the cpu row is load only.
