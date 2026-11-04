import pytest

import sensors
import widget
from widget import Gtk


def test_resize_zone_body_and_corners():
    assert widget.resize_zone(100, 60, 240, 160) is None
    assert widget.resize_zone(2, 2, 240, 160) == "north_west"
    assert widget.resize_zone(239, 80, 240, 160) == "east"


def test_drag_scale_outwards_grows_and_clamps():
    assert widget.drag_scale("east", 1.0, 240, 0) == 2.0
    assert widget.drag_scale("west", 1.0, 240, 0) == widget.MIN_SCALE
    assert widget.drag_scale("south_east", 1.0, 10_000, 0) == widget.MAX_SCALE


def test_drag_origin_keeps_far_edges():
    start = {"x_window": 100, "y_window": 50, "width": 240, "height": 160}
    assert widget.drag_origin("north_west", start, 300, 200) == (40, 10)
    assert widget.drag_origin("south_east", start, 300, 200) == (100, 50)


def test_every_row_has_a_parsable_icon():
    for key, _caption in filter(None, widget.ROWS):
        assert widget.Rsvg.Handle.new_from_data(widget.icons.svg(key, widget.ACCENT))


def test_panel_renders_offscreen(monkeypatch, tmp_path):
    """Builds the real panel and renders it off-screen; a blank frame is one colour."""
    if not Gtk.init_check()[0]:
        pytest.skip("no display")
    monkeypatch.setattr(widget, "WINDOW_STATE_PATH", tmp_path / "window.json")
    # No probes or speed test from a test run.
    monkeypatch.setattr(widget.internet.Internet, "start", lambda self: None)
    panel = widget.PcMonitor(sensors.load_config())
    content = panel.get_child()
    panel.remove(content)
    offscreen = Gtk.OffscreenWindow()
    offscreen.set_size_request(widget.WIDTH, -1)
    offscreen.add(content)
    offscreen.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    pixbuf = offscreen.get_pixbuf()
    pixels, channels = pixbuf.get_pixels(), pixbuf.get_n_channels()
    colours = {pixels[i:i + channels] for i in range(0, len(pixels), channels)}
    assert pixbuf.get_height() > 100
    assert len(colours) > 8
    pixbuf.savev(str(tmp_path / "panel.png"), "png", [], [])


@pytest.fixture
def stubbed_panel(monkeypatch, tmp_path):
    """A real panel whose window calls are recorded instead of reaching the WM."""
    if not Gtk.init_check()[0]:
        pytest.skip("no display")
    monkeypatch.setattr(widget, "WINDOW_STATE_PATH", tmp_path / "window.json")
    monkeypatch.setattr(widget.internet.Internet, "start", lambda self: None)
    panel = widget.PcMonitor(sensors.load_config())
    panel.calls = []
    monkeypatch.setattr(panel, "get_mapped", lambda: True)
    monkeypatch.setattr(panel, "get_position", lambda: (40, 50))
    monkeypatch.setattr(panel, "hide", lambda: panel.calls.append("hide"))
    monkeypatch.setattr(panel, "move", lambda x, y: panel.calls.append(("move", x, y)))
    monkeypatch.setattr(panel, "show", lambda: panel.calls.append("show"))
    monkeypatch.setattr(panel, "set_keep_above", lambda on: panel.calls.append(("above", on)))
    return panel


def tick(panel, times, painted=False):
    for _ in range(times):
        if painted:
            panel.mark.drawn_at += 1
        panel.check_redraw()


def test_frozen_panel_is_remapped_in_place_and_stays_on_top(stubbed_panel):
    """Remapping drops _NET_WM_STATE_ABOVE (seen 2026-11-04), so it is set again."""
    tick(stubbed_panel, widget.FROZEN_REFRESHES)
    assert stubbed_panel.calls == ["hide", ("move", 40, 50), "show", ("above", True)]


def test_painting_panel_is_left_alone(stubbed_panel):
    tick(stubbed_panel, 3 * widget.FROZEN_REFRESHES, painted=True)
    assert stubbed_panel.calls == []


def test_one_late_refresh_is_not_a_freeze(stubbed_panel):
    """A main loop blocked for a minute is one late tick, then GTK paints."""
    tick(stubbed_panel, 1)
    tick(stubbed_panel, 1, painted=True)
    tick(stubbed_panel, widget.FROZEN_REFRESHES - 1)
    assert stubbed_panel.calls == []


def test_hidden_spell_restarts_the_count(stubbed_panel, monkeypatch):
    """No paint while unmapped is expected; the count starts again once shown."""
    tick(stubbed_panel, widget.FROZEN_REFRESHES - 1)
    monkeypatch.setattr(stubbed_panel, "get_mapped", lambda: False)
    tick(stubbed_panel, 60)
    monkeypatch.setattr(stubbed_panel, "get_mapped", lambda: True)
    tick(stubbed_panel, widget.FROZEN_REFRESHES - 1)
    assert stubbed_panel.calls == []


def test_still_frozen_panel_is_retried(stubbed_panel):
    tick(stubbed_panel, 2 * widget.FROZEN_REFRESHES)
    assert stubbed_panel.calls.count("hide") == 2
