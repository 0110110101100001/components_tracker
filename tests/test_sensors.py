import pytest
import yaml

import internet
import sensors

CONFIG = {"refresh_seconds": 1.0, "disk_mount": "/", "busy_core_percent": 50,
          "online_check_seconds": 5, "speed_test_minutes": 30,
          "load_thresholds": {"amber": 60, "red": 85},
          "temp_thresholds": {"cpu": {"amber": 80, "red": 90},
                              "gpu": {"amber": 75, "red": 85}}}
GB = sensors.GB


def sample(**overrides):
    base = {"cpu_load": 10.0, "core_loads": [5.0, 5.0, 5.0, 5.0], "cpu_temp": 50.0,
            "ram_used": 8 * GB, "ram_total": 64 * GB,
            "disk_fill": 40.0, "disk_free": 120 * GB, "disk_read": 0.0, "disk_write": 0.0,
            "gpu": {"load": 5, "temp": 30, "power": 32.4,
                    "vram_used": 2 * GB, "vram_total": 32 * GB},
            "online": True, "latency": 12.4, "speed": (94.6e6, 8.25e6), "stalled": False}
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
    assert sensors.fmt_fill_free(94.2, 13.3 * GB) == "94 % · 13.3 GB free"
    assert sensors.fmt_rates(1.25 * sensors.MB, 0) == "1.2 / 0.0 MB/s"
    assert sensors.fmt_mbits(94.6e6, 8.25e6) == "↓95 ↑8.2"


def test_rates_per_second():
    assert sensors.rates((0.0, 0, 0), (2.0, 10, 20)) == [5, 10]


def test_internet_rows():
    def internet(**overrides):
        return sensors.rows(sample(**overrides), CONFIG)["internet"]

    assert internet() == ("↓95 ↑8.2 · 12 ms", "green")
    assert internet(speed=None) == ("online · 12 ms", "green")
    assert internet(online=False, latency=None) == ("offline", "offline")
    assert internet(stalled=True) == ("offline", "offline")
    assert internet(online=None, latency=None, speed=None) == ("…", "muted")


def test_rows_hot_cpu_turns_red_even_when_idle():
    rows = sensors.rows(sample(cpu_temp=95.0), CONFIG)
    assert rows["cpu"] == ("10 % · 95 °C", "red")
    assert rows["gpu_power"] == ("32 W", "plain")


def test_cores_row_counts_cores_from_threshold_up():
    rows = sensors.rows(sample(core_loads=[100.0, 50.0, 49.9, 0.0]), CONFIG)
    assert rows["cores"] == ("2 / 4", "green")
    rows = sensors.rows(sample(core_loads=[100.0, 90.0, 80.0, 70.0]), CONFIG)
    assert rows["cores"] == ("4 / 4", "red")


def test_unreported_gpu_power_is_a_muted_dash():
    gpu = sample()["gpu"] | {"power": None}
    assert sensors.rows(sample(gpu=gpu), CONFIG)["gpu_power"] == ("—", "muted")


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
    sampler = sensors.Sampler("/", internet.Internet(5, 30))
    rows = sensors.rows(sampler.sample(), CONFIG)
    assert set(rows) == {"cpu", "cores", "ram", "disk", "disk_io", "internet",
                         "gpu", "vram", "gpu_power"}


def test_failed_gpu_read_blanks_the_sample(monkeypatch):
    class FailingGpu:
        def read(self):
            raise sensors.pynvml.NVMLError_Unknown()

    monkeypatch.setattr(sensors, "open_gpu", FailingGpu)
    assert sensors.Sampler("/", internet.Internet(5, 30)).sample()["gpu"] is None
