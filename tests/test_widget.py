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


def test_redraw_frozen_after_quiet_spell():
    assert not widget.redraw_frozen(now=105.0, drawn_at=100.0, recovered_at=0.0)
    assert widget.redraw_frozen(now=100.0 + widget.FROZEN_SECONDS + 1, drawn_at=100.0,
                                recovered_at=0.0)


def test_redraw_frozen_waits_after_a_recovery():
    # Just remapped: give the window time to paint before trying again.
    assert not widget.redraw_frozen(now=200.0, drawn_at=100.0, recovered_at=195.0)
    assert widget.redraw_frozen(now=195.0 + widget.FROZEN_SECONDS + 1, drawn_at=100.0,
                                recovered_at=195.0)


def test_frozen_panel_is_remapped_in_place(monkeypatch, tmp_path):
    """A mapped panel that stopped painting is hidden and shown at the same spot."""
    if not Gtk.init_check()[0]:
        pytest.skip("no display")
    monkeypatch.setattr(widget, "WINDOW_STATE_PATH", tmp_path / "window.json")
    monkeypatch.setattr(widget.internet.Internet, "start", lambda self: None)
    panel = widget.PcMonitor(sensors.load_config())
    calls = []
    monkeypatch.setattr(panel, "get_mapped", lambda: True)
    monkeypatch.setattr(panel, "get_position", lambda: (40, 50))
    monkeypatch.setattr(panel, "hide", lambda: calls.append("hide"))
    monkeypatch.setattr(panel, "move", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(panel, "show", lambda: calls.append("show"))
    now = panel.mark.drawn_at + widget.FROZEN_SECONDS + 1
    panel.check_redraw(now)
    assert calls == ["hide", ("move", 40, 50), "show"]
    panel.check_redraw(now + 1)  # backs off right after a recovery
    assert len(calls) == 3
    panel.mark.drawn_at = now + 2  # painting again: nothing to do
    panel.check_redraw(now + 3)
    assert len(calls) == 3
