"""Reads PC load figures and turns them into the panel's row texts."""

import sys
import time
from pathlib import Path

import psutil
import pynvml
import yaml

GB = 1024 ** 3
MB = 1024 ** 2
CONFIG_PATH = Path(__file__).with_name("config.yaml")
# Sensor chip and label of the one CPU temperature worth showing, per vendor.
CPU_TEMP_SENSORS = (("k10temp", "Tctl"), ("coretemp", "Package id 0"))
# Loopback interface names (Linux, Windows); their traffic never leaves the PC.
LOOPBACK = ("lo", "Loopback Pseudo-Interface 1")


def load_config(path=CONFIG_PATH):
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config["refresh_seconds"] <= 0:
        raise ValueError("refresh_seconds must be > 0")
    if not 0 < config["busy_core_percent"] <= 100:
        raise ValueError("busy_core_percent must be in (0, 100]")
    thresholds = {"load": config["load_thresholds"],
                  **{f"{part} temp": levels
                     for part, levels in config["temp_thresholds"].items()}}
    for name, levels in thresholds.items():
        if not levels["amber"] < levels["red"]:
            raise ValueError(f"{name} thresholds: amber must be below red")
    if not Path(config["disk_mount"]).is_dir():
        raise ValueError(f"disk_mount {config['disk_mount']} does not exist")
    return config


def level(value, thresholds):
    """Colour class for one figure; None (unknown) counts as green."""
    if value is None or value < thresholds["amber"]:
        return "green"
    return "amber" if value < thresholds["red"] else "red"


def worst(*levels):
    return max(levels, key=("green", "amber", "red").index)


def fmt_load_temp(load, temp):
    text = f"{load:.0f} %"
    return text if temp is None else f"{text} · {temp:.0f} °C"


def fmt_used(used, total):
    return f"{used / GB:.1f} / {total / GB:.0f} GB"


def fmt_fill_free(fill, free):
    return f"{fill:.0f} % · {free / GB:.1f} GB free"


def fmt_rates(first, second):
    return f"{first / MB:.1f} / {second / MB:.1f} MB/s"


def cpu_temp():
    # psutil reads temperatures on Linux only; Windows exposes none without admin.
    if not hasattr(psutil, "sensors_temperatures"):
        return None
    readings = psutil.sensors_temperatures()
    for chip, label in CPU_TEMP_SENSORS:
        for sensor in readings.get(chip, []):
            if sensor.label == label:
                return sensor.current
    return None


class Gpu:
    """The first NVIDIA GPU, read through NVML."""

    def __init__(self):
        pynvml.nvmlInit()
        self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        self.name = pynvml.nvmlDeviceGetName(self.handle)

    def read(self):
        memory = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
        return {
            "load": pynvml.nvmlDeviceGetUtilizationRates(self.handle).gpu,
            "temp": pynvml.nvmlDeviceGetTemperature(
                self.handle, pynvml.NVML_TEMPERATURE_GPU),
            "power": self.power(),
            "vram_used": memory.used,
            "vram_total": memory.total,
        }

    def power(self):
        """Board power in W, or None where the driver does not report it (laptop GeForces)."""
        try:
            return pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000
        except pynvml.NVMLError_NotSupported:
            return None


def open_gpu():
    """The GPU, or None on a machine without a working NVIDIA driver."""
    try:
        return Gpu()
    except pynvml.NVMLError as error:
        print(f"pc-monitor: no NVIDIA GPU, GPU rows stay empty ({error})",
              file=sys.stderr)
        return None


def io_counters():
    """(time, disk read, disk write, net down, net up), cumulative bytes."""
    disk = psutil.disk_io_counters()
    nics = psutil.net_io_counters(pernic=True)
    down = sum(n.bytes_recv for name, n in nics.items() if name not in LOOPBACK)
    up = sum(n.bytes_sent for name, n in nics.items() if name not in LOOPBACK)
    return time.monotonic(), disk.read_bytes, disk.write_bytes, down, up


def rates(before, after):
    """Bytes per second between two io_counters() samples."""
    elapsed = after[0] - before[0]
    return [(b - a) / elapsed for a, b in zip(before[1:], after[1:])]


class Sampler:
    """Remembers the previous counters, so rates and CPU load are per interval."""

    def __init__(self, disk_mount):
        self.disk_mount = disk_mount
        self.gpu = open_gpu()
        # The first calls have no interval to measure and return 0.
        psutil.cpu_percent()
        psutil.cpu_percent(percpu=True)
        self.counters = io_counters()

    def sample(self):
        counters = io_counters()
        disk_read, disk_write, net_down, net_up = rates(self.counters, counters)
        self.counters = counters
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_mount)
        return {
            "cpu_load": psutil.cpu_percent(),
            "core_loads": psutil.cpu_percent(percpu=True),
            "cpu_temp": cpu_temp(),
            "ram_used": memory.total - memory.available,
            "ram_total": memory.total,
            "disk_fill": disk.percent,
            "disk_free": disk.free,
            "disk_read": disk_read,
            "disk_write": disk_write,
            "net_down": net_down,
            "net_up": net_up,
            "gpu": self.read_gpu(),
        }

    def read_gpu(self):
        """GPU figures, or None for this sample when NVML cannot read them.

        An Optimus laptop GPU that has powered down answers with NVML errors
        (seen: Unknown Error); raising here would end the panel's refresh timer.
        """
        if self.gpu is None:
            return None
        try:
            return self.gpu.read()
        except pynvml.NVMLError:
            return None


def rows(sample, config):
    """{row key: (text, colour class)} for every row the panel shows."""
    load_t, temp_t = config["load_thresholds"], config["temp_thresholds"]
    ram_pct = 100 * sample["ram_used"] / sample["ram_total"]
    cores = len(sample["core_loads"])
    busy = sum(load >= config["busy_core_percent"] for load in sample["core_loads"])
    result = {
        "cpu": (fmt_load_temp(sample["cpu_load"], sample["cpu_temp"]),
                worst(level(sample["cpu_load"], load_t),
                      level(sample["cpu_temp"], temp_t["cpu"]))),
        "cores": (f"{busy} / {cores}", level(100 * busy / cores, load_t)),
        "ram": (fmt_used(sample["ram_used"], sample["ram_total"]),
                level(ram_pct, load_t)),
        "disk": (fmt_fill_free(sample["disk_fill"], sample["disk_free"]),
                 level(sample["disk_fill"], load_t)),
        "disk_io": (fmt_rates(sample["disk_read"], sample["disk_write"]), "plain"),
        "net": (fmt_rates(sample["net_down"], sample["net_up"]), "plain"),
    }
    gpu = sample["gpu"]
    if gpu is None:
        result.update({key: ("—", "muted") for key in ("gpu", "vram", "gpu_power")})
        return result
    vram_pct = 100 * gpu["vram_used"] / gpu["vram_total"]
    result.update({
        "gpu": (fmt_load_temp(gpu["load"], gpu["temp"]),
                worst(level(gpu["load"], load_t), level(gpu["temp"], temp_t["gpu"]))),
        "vram": (fmt_used(gpu["vram_used"], gpu["vram_total"]), level(vram_pct, load_t)),
        "gpu_power": (("—", "muted") if gpu["power"] is None
                      else (f"{gpu['power']:.0f} W", "plain")),
    })
    return result
