# PC monitor

Always-on-top panel showing how loaded each PC component is (CPU, RAM, GPU, VRAM, disk, network), in the same look as the Claude token tracker.

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

Every task is in `pixi.toml`.

**Autostart:** `~/.bashrc` sources `shell_autostart.sh`, so opening any terminal (also inside VS Code / Cursor) opens the panel if it is not running. To turn it off, delete the `source …/shell_autostart.sh` line from `~/.bashrc`.

## Structure

```
config.yaml   refresh rate, disk to watch, colour thresholds
sensors.py    reads the figures (psutil, NVML) and formats the rows
widget.py     the GTK panel
icons.py      the component icons (SVG) shown beside each row
shell_autostart.sh  sourced from ~/.bashrc, opens the panel with each terminal
tests/        unit tests + off-screen render of the panel
data/         remembered panel size (created on first resize)
```

## Notes

- Drag the middle to move, drag an edge or corner to resize. Right click: reset position, reset size, quit.
- Colours: green / amber / red by the thresholds in `config.yaml`; the cpu and gpu rows go red on either load or temperature.
- `cores` = how many CPU threads (32 on this machine) are at least `busy_core_percent` loaded.
- Hover the gpu row for the GPU name. Without an NVIDIA driver the GPU rows show `—`.
