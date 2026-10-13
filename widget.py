#!/usr/bin/env python3
"""Always-on-top PC load panel, styled like the Claude token tracker."""

import json
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("Rsvg", "2.0")
from gi.repository import Gdk, GLib, Gtk, Pango, Rsvg  # noqa: E402

import icons  # noqa: E402
import sensors  # noqa: E402

WINDOW_STATE_PATH = Path(__file__).with_name("data") / "window.json"
MARGIN = 24
WIDTH = 240
MIN_SCALE = 0.7
MAX_SCALE = 3.0
EDGE = 16
CORNER = 32
FONT_PX = 11
BRAND_FONT_PX = 13
MARK_PX = 15
ICON_PX = 13
ICON_SPACING = 6
BORDER = 10
ROW_SPACING = 3
COLUMN_SPACING = 12
BRAND_SPACING = 7
BRAND = "pc load"
# Teal rather than the tracker's terracotta, so the two panels tell apart at a glance.
ACCENT = "#4fb3bf"

# (row key, caption); None is a separator.
ROWS = (("cpu", "cpu"), ("cores", "cores"), ("ram", "ram"), None,
        ("gpu", "gpu"), ("vram", "vram"), ("gpu_power", "gpu power"), None,
        ("disk", "disk"), ("disk_io", "disk r/w"), ("net", "net ↓/↑"))
COLOUR_CLASSES = ("green", "amber", "red", "muted")

# Font size is set per label through Pango attributes, not here: a reloaded
# CssProvider restyles nothing that already exists, so a resize would not reach it.
CSS = b"""
window { background-color: #1e1e22; }
label { color: #d8d8dc; font-family: monospace; }
label.value { font-weight: bold; }
label.brand { color: #ffffff; font-weight: bold; }
label.muted { color: #8a8a92; }
label.green { color: #78d178; }
label.amber { color: #e3b341; }
label.red { color: #f06a5a; }
menu { background-color: #ffffff; }
menu label { color: #000000; }
menu menuitem:hover { background-color: #d5d5da; }
"""


def clamp_scale(scale):
    return min(MAX_SCALE, max(MIN_SCALE, scale))


def font_attrs(px):
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_size_new_absolute(px * Pango.SCALE))
    return attrs


def resize_zone(x, y, width, height):
    """Which resize handle the pointer is over, or None for the panel's body."""
    west, east = x < EDGE, x >= width - EDGE
    north, south = y < EDGE, y >= height - EDGE
    if west or east:
        side = "west" if west else "east"
        if y < CORNER:
            return f"north_{side}"
        return f"south_{side}" if y >= height - CORNER else side
    if north or south:
        side = "north" if north else "south"
        if x < CORNER:
            return f"{side}_west"
        return f"{side}_east" if x >= width - CORNER else side
    return None


def drag_scale(zone, start_scale, dx, dy):
    """Pulling any edge outwards grows the panel; a panel width doubles it."""
    outwards = 0.0
    if "west" in zone:
        outwards -= dx
    elif "east" in zone:
        outwards += dx
    if "north" in zone:
        outwards -= dy
    elif "south" in zone:
        outwards += dy
    return clamp_scale(start_scale + outwards / WIDTH)


def drag_origin(zone, start, width, height):
    """Window origin that keeps the edges not being dragged where they were."""
    x = (start["x_window"] + start["width"] - width if "west" in zone
         else start["x_window"])
    y = (start["y_window"] + start["height"] - height if "north" in zone
         else start["y_window"])
    return x, y


def saved_scale():
    try:
        return clamp_scale(float(json.loads(WINDOW_STATE_PATH.read_text())["scale"]))
    except FileNotFoundError:
        return 1.0


def save_scale(scale):
    WINDOW_STATE_PATH.parent.mkdir(exist_ok=True)
    WINDOW_STATE_PATH.write_text(json.dumps({"scale": scale}))


class LoadMark(Gtk.DrawingArea):
    """Header mark: three bars showing CPU, RAM and GPU load live."""

    def __init__(self, size):
        super().__init__()
        self.loads = (0.0, 0.0, 0.0)
        self.set_size(size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self.on_draw)

    def set_size(self, size):
        self.size = size
        self.set_size_request(size, size)

    def set_loads(self, loads):
        self.loads = loads
        self.queue_draw()

    def on_draw(self, _widget, context):
        bar = self.size / 5
        colour = Gdk.RGBA()
        colour.parse(ACCENT)
        context.set_source_rgba(colour.red, colour.green, colour.blue, 0.25)
        for index in range(len(self.loads)):
            context.rectangle(index * 2 * bar, 0, bar, self.size)
        context.fill()
        context.set_source_rgb(colour.red, colour.green, colour.blue)
        for index, load in enumerate(self.loads):
            height = self.size * max(0.12, min(load, 100) / 100)
            context.rectangle(index * 2 * bar, self.size - height, bar, height)
        context.fill()
        return True


class Icon(Gtk.DrawingArea):
    """A row's component icon, rendered from SVG so it stays sharp at every scale."""

    def __init__(self, name, size):
        super().__init__()
        self.handle = Rsvg.Handle.new_from_data(icons.svg(name, ACCENT))
        self.set_size(size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self.on_draw)

    def set_size(self, size):
        self.size = size
        self.set_size_request(size, size)

    def on_draw(self, _widget, context):
        box = Rsvg.Rectangle()
        box.x = box.y = 0.0
        box.width = box.height = float(self.size)
        self.handle.render_document(context, box)
        return True


class PcMonitor(Gtk.Window):
    def __init__(self, config):
        super().__init__(title="PC monitor")
        self.config = config
        self.sampler = sensors.Sampler(config["disk_mount"])
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        # Resizable, or resize() — which applies a scale change — is a no-op.
        self.set_resizable(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("button-press-event", self.on_click)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("size-allocate", self.on_size_allocate)
        self.connect("destroy", Gtk.main_quit)
        # Anchored to the top-right corner until the user drags the panel away.
        self.anchored = True
        self._resize = None
        self._cursor_name = None

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.grid = Gtk.Grid()
        self.add(self.grid)
        self.mark = LoadMark(MARK_PX)
        self.brand = Gtk.Label(label=BRAND, xalign=0.0)
        self.brand.get_style_context().add_class("brand")
        self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.header.pack_start(self.mark, False, False, 0)
        self.header.pack_start(self.brand, False, False, 0)
        self.grid.attach(self.header, 0, 0, 2, 1)
        self.grid.attach(Gtk.Separator(), 0, 1, 2, 1)

        self.labels = []
        self.values = {}
        self.icons = []
        self.caption_boxes = []
        for index, row in enumerate(ROWS, start=2):
            if row is None:
                self.grid.attach(Gtk.Separator(), 0, index, 2, 1)
                continue
            key, caption = row
            icon = Icon(key, ICON_PX)
            left = Gtk.Label(label=caption, xalign=0.0)
            # Icon and caption share a box, so the gap between them is not the
            # wide column spacing that separates caption from value.
            caption_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            caption_box.pack_start(icon, False, False, 0)
            caption_box.pack_start(left, False, False, 0)
            right = Gtk.Label(label="—", xalign=1.0, hexpand=True)
            right.get_style_context().add_class("value")
            self.grid.attach(caption_box, 0, index, 1, 1)
            self.grid.attach(right, 1, index, 1, 1)
            self.labels += [left, right]
            self.icons.append(icon)
            self.caption_boxes.append(caption_box)
            self.values[key] = right
        if self.sampler.gpu is not None:
            self.values["gpu"].set_tooltip_text(self.sampler.gpu.name)

        self.apply_scale(saved_scale())
        self.refresh()
        GLib.timeout_add(round(config["refresh_seconds"] * 1000), self.refresh)

    def refresh(self):
        sample = self.sampler.sample()
        for key, (text, colour) in sensors.rows(sample, self.config).items():
            label = self.values[key]
            label.set_text(text)
            context = label.get_style_context()
            for name in COLOUR_CLASSES:
                context.remove_class(name)
            if colour != "plain":
                context.add_class(colour)
        gpu = sample["gpu"]
        self.mark.set_loads((sample["cpu_load"],
                             100 * sample["ram_used"] / sample["ram_total"],
                             gpu["load"] if gpu else 0.0))
        return True

    def apply_scale(self, scale):
        """Scale text, spacing and width together; the rows decide the height."""
        self.scale = clamp_scale(scale)
        attrs = font_attrs(round(FONT_PX * self.scale))
        for label in self.labels:
            label.set_attributes(attrs)
        self.brand.set_attributes(font_attrs(round(BRAND_FONT_PX * self.scale)))
        self.mark.set_size(round(MARK_PX * self.scale))
        for icon in self.icons:
            icon.set_size(round(ICON_PX * self.scale))
        for caption_box in self.caption_boxes:
            caption_box.set_spacing(round(ICON_SPACING * self.scale))
        self.header.set_spacing(round(BRAND_SPACING * self.scale))
        self.grid.set_border_width(round(BORDER * self.scale))
        self.grid.set_row_spacing(round(ROW_SPACING * self.scale))
        self.grid.set_column_spacing(round(COLUMN_SPACING * self.scale))
        self.resize(round(WIDTH * self.scale), 1)

    def anchor_top_right(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        target = (area.x + area.width - self.get_size().width - MARGIN,
                  area.y + MARGIN)
        if tuple(self.get_position()) != target:
            self.move(*target)

    def on_size_allocate(self, _widget, _allocation):
        if self.anchored:
            self.anchor_top_right()
        elif self._resize is not None:
            # The new height only exists once allocated, so the move happens here.
            self.move(*drag_origin(self._resize["zone"], self._resize,
                                   *self.get_size()))

    def on_click(self, _widget, event):
        if event.button == 3:
            self.show_menu(event)
            return True
        if event.button != 1:
            return False
        zone = resize_zone(event.x, event.y, *self.get_size())
        if zone is None:
            self.anchored = False
            self.begin_move_drag(event.button, int(event.x_root),
                                 int(event.y_root), event.time)
            return True
        # Sampled once: measured per motion event, the panel would run from the pointer.
        position, size = self.get_position(), self.get_size()
        self._resize = {"zone": zone, "x": event.x_root, "y": event.y_root,
                        "scale": self.scale,
                        "x_window": position[0], "y_window": position[1],
                        "width": size.width, "height": size.height}
        return True

    def on_motion(self, _widget, event):
        if self._resize is None:
            self.set_resize_cursor(resize_zone(event.x, event.y, *self.get_size()))
            return False
        start = self._resize
        scale = drag_scale(start["zone"], start["scale"],
                           event.x_root - start["x"], event.y_root - start["y"])
        if scale != self.scale:
            self.apply_scale(scale)
        return True

    def on_release(self, _widget, _event):
        if self._resize is None:
            return False
        self._resize = None
        save_scale(self.scale)
        return True

    def set_resize_cursor(self, zone):
        name = {"west": "ew-resize", "east": "ew-resize",
                "north": "ns-resize", "south": "ns-resize",
                "north_west": "nwse-resize", "south_east": "nwse-resize",
                "north_east": "nesw-resize", "south_west": "nesw-resize",
                }.get(zone)
        if name == self._cursor_name or self.get_window() is None:
            return
        self._cursor_name = name
        self.get_window().set_cursor(
            None if name is None
            else Gdk.Cursor.new_from_name(self.get_display(), name))

    def show_menu(self, event):
        menu = Gtk.Menu()
        for caption, handler in (("Reset position", self.reset_position),
                                 ("Reset size", self.reset_scale),
                                 ("Quit", Gtk.main_quit)):
            item = Gtk.MenuItem(label=caption)
            item.connect("activate", lambda *_, h=handler: h())
            menu.append(item)
        menu.show_all()
        menu.popup_at_pointer(event)
        self.menu = menu  # keep a reference so it is not collected mid-display

    def reset_position(self):
        self.anchored = True
        self.anchor_top_right()

    def reset_scale(self):
        WINDOW_STATE_PATH.unlink(missing_ok=True)
        self.apply_scale(1.0)


def main():
    PcMonitor(sensors.load_config()).show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
