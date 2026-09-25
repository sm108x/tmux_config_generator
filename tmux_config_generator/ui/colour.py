"""Colour widgets: a swatch button with a tmux palette and RGB picker."""

from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk

from ..styles import (colour_to_rgb, normalize_colour, palette_rgb, rgb_to_hex,
                      tmux_colour_name)

CELL = 14  # palette cell size in pixels

# Palette layout: rows of palette indexes (None = gap).
_ROWS = [list(range(0, 8)), list(range(8, 16)), [None]]
for block in range(6):  # the 6x6x6 cube as 6 rows of 36
    _ROWS.append(list(range(16 + block * 36, 16 + (block + 1) * 36)))
_ROWS += [[None], list(range(232, 256))]
_COLS = max(len(r) for r in _ROWS)


def _rgba(rgb) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(rgb_to_hex(*rgb))
    return c


class PaletteGrid(Gtk.DrawingArea):
    """Clickable grid of the 256 tmux palette colours."""

    def __init__(self, on_pick, on_hover):
        super().__init__(content_width=_COLS * CELL, content_height=len(_ROWS) * CELL)
        self.on_pick = on_pick
        self.on_hover = on_hover
        self.hover = None
        self.set_draw_func(self._draw)
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", lambda *_: self._set_hover(None))
        self.add_controller(motion)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    def _index_at(self, x, y):
        r, c = int(y // CELL), int(x // CELL)
        if 0 <= r < len(_ROWS) and 0 <= c < len(_ROWS[r]):
            return _ROWS[r][c]
        return None

    def _set_hover(self, idx):
        if idx != self.hover:
            self.hover = idx
            self.on_hover(idx)
            self.queue_draw()

    def _on_motion(self, _ctl, x, y):
        self._set_hover(self._index_at(x, y))

    def _on_click(self, _g, _n, x, y):
        idx = self._index_at(x, y)
        if idx is not None:
            self.on_pick(tmux_colour_name(idx))

    def _draw(self, _a, cr, _w, _h):
        for r, row in enumerate(_ROWS):
            for c, idx in enumerate(row):
                if idx is None:
                    continue
                rgb = palette_rgb(idx)
                cr.set_source_rgb(*(v / 255 for v in rgb))
                cr.rectangle(c * CELL + 1, r * CELL + 1, CELL - 2, CELL - 2)
                cr.fill()
                if idx == self.hover:
                    lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
                    cr.set_source_rgb(*((0, 0, 0) if lum > 128 else (1, 1, 1)))
                    cr.set_line_width(2)
                    cr.rectangle(c * CELL + 1, r * CELL + 1, CELL - 2, CELL - 2)
                    cr.stroke()


class Swatch(Gtk.DrawingArea):
    """Small colour sample; hatched when the colour has no fixed RGB."""

    def __init__(self):
        super().__init__(content_width=22, content_height=14)
        self.colour = ""
        self.set_draw_func(self._draw)

    def set_colour(self, colour: str):
        self.colour = colour
        self.queue_draw()

    def _draw(self, _a, cr, w, h):
        rgb = colour_to_rgb(self.colour) if self.colour else None
        if rgb:
            cr.set_source_rgb(*(v / 255 for v in rgb))
            cr.rectangle(0, 0, w, h)
            cr.fill()
        else:  # default / terminal / unset: diagonal hatching
            cr.set_source_rgb(0.85, 0.85, 0.85)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            cr.set_source_rgb(0.55, 0.55, 0.55)
            cr.set_line_width(1)
            for x in range(-h, w, 5):
                cr.move_to(x, h)
                cr.line_to(x + h, 0)
            cr.stroke()
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()


class ColourButton(Gtk.MenuButton):
    """Swatch button opening a tmux palette, Default, and an RGB picker."""

    def __init__(self, on_pick, tooltip="Pick a colour", label: str | None = None):
        super().__init__(tooltip_text=tooltip, valign=Gtk.Align.CENTER)
        self.on_pick = on_pick
        self.colour = ""
        self.swatch = Swatch()
        if label:
            box = Gtk.Box(spacing=4)
            lab = Gtk.Label(label=label)
            lab.add_css_class("caption")
            box.append(lab)
            box.append(self.swatch)
            self.set_child(box)
        else:
            self.set_child(self.swatch)

        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
        self.info = Gtk.Label(label="Hover a colour", xalign=0)
        self.info.add_css_class("monospace")
        self.info.add_css_class("dim-label")
        box.append(PaletteGrid(self._pick, self._hover))
        box.append(self.info)
        buttons = Gtk.Box(spacing=6)
        for text, value, tip in [
            ("Default", "default", "Inherit the default colour"),
            ("Terminal", "terminal", "The terminal's own default colour"),
        ]:
            b = Gtk.Button(label=text, tooltip_text=tip)
            b.connect("clicked", lambda _b, v=value: self._pick(v))
            buttons.append(b)
        custom = Gtk.Button(label="Custom colour…", hexpand=True, halign=Gtk.Align.END,
                            tooltip_text="Choose any RGB colour (#rrggbb)")
        custom.connect("clicked", self._custom)
        buttons.append(custom)
        box.append(buttons)
        pop.set_child(box)
        self.set_popover(pop)
        self.pop = pop

    def set_colour(self, colour: str):
        self.colour = colour
        self.swatch.set_colour(colour)

    def _hover(self, idx):
        if idx is None:
            self.info.set_label("Hover a colour")
        else:
            name = tmux_colour_name(idx)
            self.info.set_label(f"{name}  {rgb_to_hex(*palette_rgb(idx))}")

    def _pick(self, value: str):
        self.pop.popdown()
        self.set_colour(value)
        self.on_pick(value)

    def _custom(self, _btn):
        self.pop.popdown()
        dialog = Gtk.ColorDialog(with_alpha=False, title="Choose a colour")
        rgb = colour_to_rgb(self.colour) if self.colour else None
        initial = _rgba(rgb) if rgb else None

        def done(d, res):
            try:
                c = d.choose_rgba_finish(res)
            except GLib.Error:
                return  # cancelled
            self._pick(rgb_to_hex(round(c.red * 255), round(c.green * 255),
                                  round(c.blue * 255)))
        dialog.choose_rgba(self.get_root(), initial, None, done)


class ColourEntry(Gtk.Box):
    """Text entry for a tmux colour plus a ColourButton.

    Typed colours may be names, colourN, #rrggbb, rrggbb, #rgb or
    rgb(r, g, b); they are normalised to tmux syntax when the entry loses
    focus or Enter is pressed, and invalid input is highlighted.
    """

    def __init__(self, on_changed=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.on_changed = on_changed
        self._updating = False
        self.entry = Gtk.Entry(width_chars=14, hexpand=True,
                               placeholder_text="red, colour33, #ff8800")
        self.entry.connect("changed", self._on_entry)
        self.entry.connect("activate", lambda *_: self.normalize())
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda *_: self.normalize())
        self.entry.add_controller(focus)
        self.button = ColourButton(self._on_pick)
        self.append(self.entry)
        self.append(self.button)

    def get_text(self) -> str:
        """The colour in tmux syntax (normalised if valid, else as typed)."""
        raw = self.entry.get_text().strip()
        return normalize_colour(raw) or raw

    def set_text(self, text: str):
        self._updating = True
        self.entry.set_text(text)
        self._sync(text)
        self._updating = False

    def is_valid(self) -> bool:
        raw = self.entry.get_text().strip()
        return raw == "" or normalize_colour(raw) is not None

    def normalize(self):
        raw = self.entry.get_text().strip()
        norm = normalize_colour(raw)
        if norm and norm != self.entry.get_text():
            self._updating = True
            self.entry.set_text(norm)
            self._updating = False

    def _sync(self, text):
        norm = normalize_colour(text)
        self.button.set_colour(norm or "")
        if self.is_valid():
            self.entry.remove_css_class("error")
            self.entry.set_tooltip_text(None)
        else:
            self.entry.add_css_class("error")
            self.entry.set_tooltip_text(
                "Not a tmux colour. Use a name (red, brightblue, default), "
                "colour0–colour255, or RGB as #rrggbb, #rgb or rgb(r, g, b).")

    def _on_entry(self, entry):
        if self._updating:
            return
        self._sync(entry.get_text())
        if self.on_changed:
            self.on_changed(self.get_text())

    def _on_pick(self, value):
        self.entry.set_text(value)
