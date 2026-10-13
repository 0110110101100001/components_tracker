import pytest
import yaml

import sensors

CONFIG = {"refresh_seconds": 1.0, "disk_mount": "/", "busy_core_percent": 50,
          "load_thresholds": {"amber": 60, "red": 85},
          "temp_thresholds": {"cpu": {"amber": 80, "red": 90},
                              "gpu": {"amber": 75, "red": 85}}}
GB = sensors.GB


def sample(**overrides):
    base = {"cpu_load": 10.0, "core_loads": [5.0, 5.0, 5.0, 5.0], "cpu_temp": 50.0,
            "ram_used": 8 * GB, "ram_total": 64 * GB,
            "disk_fill": 40.0, "disk_read": 0.0, "disk_write": 0.0,
            "net_down": 0.0, "net_up": 0.0,
            "gpu": {"load": 5, "temp": 30, "power": 32.4,
                    "vram_used": 2 * GB, "vram_total": 32 * GB}}
    return base | overrides


def test_level_boundaries():
    t = {"amber": 60, "red": 85}
    assert sensors.level(59.9, t) == "green"
    assert sensors.level(60, t) == "amber"
    assert sensors.level(85, t) == "red"
    assert sensors.level(None, t) == "green"


def test_worst_picks_most_severe():
    assert sensors.worst("green", "red", "amber") == "red"


def test_formatters():
    assert sensors.fmt_load_temp(37.4, 61.6) == "37 % · 62 °C"
    assert sensors.fmt_load_temp(37.4, None) == "37 %"
    assert sensors.fmt_used(12.34 * GB, 62 * GB) == "12.3 / 62 GB"
    assert sensors.fmt_rates(1.25 * sensors.MB, 0) == "1.2 / 0.0 MB/s"


def test_rates_per_second():
    assert sensors.rates((0.0, 0, 0, 0, 0), (2.0, 10, 20, 30, 40)) == [5, 10, 15, 20]


def test_rows_hot_cpu_turns_red_even_when_idle():
    rows = sensors.rows(sample(cpu_temp=95.0), CONFIG)
    assert rows["cpu"] == ("10 % · 95 °C", "red")
    assert rows["gpu_power"] == ("32 W", "plain")


def test_cores_row_counts_cores_from_threshold_up():
    rows = sensors.rows(sample(core_loads=[100.0, 50.0, 49.9, 0.0]), CONFIG)
    assert rows["cores"] == ("2 / 4", "green")
    rows = sensors.rows(sample(core_loads=[100.0, 90.0, 80.0, 70.0]), CONFIG)
    assert rows["cores"] == ("4 / 4", "red")


def test_rows_without_gpu_are_muted_dashes():
    rows = sensors.rows(sample(gpu=None), CONFIG)
    assert rows["gpu"] == rows["vram"] == rows["gpu_power"] == ("—", "muted")


def test_shipped_config_loads():
    assert sensors.load_config()["refresh_seconds"] > 0


def test_config_rejects_inverted_thresholds(tmp_path):
    bad = CONFIG | {"load_thresholds": {"amber": 90, "red": 80}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="amber must be below red"):
        sensors.load_config(path)


def test_sampler_reads_this_machine():
    sampler = sensors.Sampler("/")
    rows = sensors.rows(sampler.sample(), CONFIG)
    assert set(rows) == {"cpu", "cores", "ram", "disk", "disk_io", "net",
                         "gpu", "vram", "gpu_power"}
