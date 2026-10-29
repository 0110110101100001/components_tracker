# PC monitor

Always-on-top panel showing how loaded each PC component is (CPU, RAM, GPU, VRAM, disk) plus whether the internet is up and how fast it is, in the same look as the Claude token tracker. Runs on Linux and Windows (linux-64, win-64).

## Install

```bash
pixi install
pixi run smoke-test
```

## Run

```bash
pixi run start     # open the panel (survives closing the terminal)
pixi run stop      # close it
pixi run resurrect # stop it and open a fresh one (panel off-screen or stuck; also works when none runs)
pixi run panel     # foreground, to see errors
```

Every task is in `pixi.toml`. On Linux `start`/`stop` go through a systemd user service, on Windows through `winpanel.py` (detached `pythonw`, no console window; startup errors land in `data/panel.log`).

**Autostart (Linux):** `~/.bashrc` sources `shell_autostart.sh`, so opening any terminal (also inside VS Code / Cursor) opens the panel if it is not running. To turn it off, delete the `source …/shell_autostart.sh` line from `~/.bashrc`.

**Autostart (Windows):** `pixi run autostart` opens the panel at every login (a `pc-monitor` value in `HKCU\…\CurrentVersion\Run` that runs `autostart.vbs`, i.e. `pixi run start` without a console window). `pixi run autostart-off` removes it; Task Manager → Startup can also disable it. Re-run `pixi run autostart` if the project folder or pixi moves.

## Structure

```
config.yaml   refresh rate, disk to watch, colour thresholds, internet check / speed test intervals
sensors.py    reads the figures (psutil, NVML) and formats the rows
internet.py   connectivity probe and speed test, in background threads
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
- `internet`: green `↓95 ↑8.2 · 12 ms` while online, pulsing red `offline` when not.
  - Online and latency: a TCP connect to 1.1.1.1 / 8.8.8.8 every `online_check_seconds` (5 s). By IP, so a broken DNS still reads as online.
  - `↓ ↑`: download / upload in Mbit/s from a speed test against speed.cloudflare.com every `speed_test_minutes` (30 min, first one 30 s after start); until then the row reads `online · 12 ms`. Hover for when it ran. Each test moves data: ~4 s of download + ~1 s of upload (about 60 MB on a 100 Mbit line, so ~3 GB a day at the default 30 min). Your own traffic at that moment lowers the figure.
  - A test that gets no data through (download rounds to 0, or the connection times out) while the probe still connects also reads `offline`, instead of `↓0 ↑0`; the test then retries every minute until data flows.
- Windows shows no CPU temperature (it exposes none without admin rights), so the cpu row is load only.
