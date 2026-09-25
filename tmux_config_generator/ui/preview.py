"""Live preview of a tmux client, painted from a render.screen.Screen."""

from __future__ import annotations

from gi.repository import GLib, Gtk, Pango, PangoCairo

from ..render.screen import SCENES, CellStyle, build_screen
from ..styles import colour_to_rgb

FONT_FAMILY = "DejaVu Sans Mono, Menlo, Consolas, Monospace"
COLS, MIN_ROWS = 90, 14

PALETTES = {
    "dark": {"fg": (0xd4, 0xd4, 0xd4), "bg": (0x1e, 0x1e, 0x1e)},
    "light": {"fg": (0x20, 0x20, 0x20), "bg": (0xfa, 0xfa, 0xfa)},
}

# Box drawing: char -> (up, down, left, right); 1 light, 2 heavy, 3 double.
_BOX = {}
for chars, segs in [
    ("│┃║", (1, 1, 0, 0)), ("─━═", (0, 0, 1, 1)),
    ("┌┏╔╭", (0, 1, 0, 1)), ("┐┓╗╮", (0, 1, 1, 0)),
    ("└┗╚╰", (1, 0, 0, 1)), ("┘┛╝╯", (1, 0, 1, 0)),
    ("├┣╠", (1, 1, 0, 1)), ("┤┫╣", (1, 1, 1, 0)),
    ("┬┳╦", (0, 1, 1, 1)), ("┴┻╩", (1, 0, 1, 1)), ("┼╋╬", (1, 1, 1, 1)),
]:
    for ch, weight in zip(chars, (1, 2, 3, 1)):
        _BOX[ch] = tuple(weight if s else 0 for s in segs)


def _rgb(colour: str, default):
    if colour in ("default", "terminal", ""):
        return default
    rgb = colour_to_rgb(colour)
    return rgb if rgb else default


def _blend(a, b, t):
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b))


class PreviewPanel(Gtk.Box):
    """Scene picker plus a drawing of the sample tmux session."""

    def __init__(self, values_fn, scene: str = "normal"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         margin_top=12, margin_start=12, margin_end=12,
                         margin_bottom=6)
        self.values_fn = values_fn
        self.scene_ids = [s for s, _ in SCENES]
        self.palette = "dark"
        self.painter = ScreenPainter()

        head = Gtk.Box(spacing=8)
        title = Gtk.Label(xalign=0)
        title.set_markup("<b>Preview</b>")
        head.append(title)
        hint = Gtk.Label(label="sample session · updates as you edit",
                         xalign=0, hexpand=True)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        head.append(hint)
        self.scene_dd = Gtk.DropDown.new_from_strings([label for _, label in SCENES])
        self.scene_dd.set_tooltip_text("What the sample tmux client is showing")
        self.scene_dd.connect("notify::selected", lambda *_: self.area.queue_draw())
        head.append(self.scene_dd)
        self.light = Gtk.ToggleButton(icon_name="weather-clear-symbolic",
                                      tooltip_text="Light terminal background")
        self.light.connect("toggled", self._on_light)
        head.append(self.light)
        self.append(head)

        self.area = Gtk.DrawingArea(vexpand=True, hexpand=True,
                                    content_height=180, content_width=400)
        self.area.set_draw_func(self._draw)
        frame = Gtk.Frame()
        frame.set_child(self.area)
        self.append(frame)
        self.set_scene(scene)

    def _on_light(self, btn):
        self.palette = "light" if btn.get_active() else "dark"
        self.area.queue_draw()

    @property
    def scene(self) -> str:
        return self.scene_ids[self.scene_dd.get_selected()]

    def set_scene(self, scene: str | None):
        if scene in self.scene_ids and scene != self.scene:
            self.scene_dd.set_selected(self.scene_ids.index(scene))

    def refresh(self):
        self.area.queue_draw()

    def _draw(self, _area, cr, width, height):
        painter = self.painter
        # Fill the area: 90 columns wide if that leaves enough rows,
        # otherwise fit 14 rows and use as many columns as fit.
        cw100, ch100 = painter.measure(cr)
        scale = width / (COLS * cw100)
        cols, rows = COLS, int(height / (ch100 * scale))
        if rows < MIN_ROWS:
            scale = height / (MIN_ROWS * ch100)
            rows, cols = MIN_ROWS, max(40, int(width / (cw100 * scale)))
        rows = min(rows, 60)
        try:
            screen = build_screen(self.values_fn(), self.scene, cols, rows)
        except Exception as e:  # never let a bad value break the UI
            painter.error(cr, e)
            return
        painter.paint(cr, screen, width, height, scale, self.palette,
                      cursor=self.scene not in ("display-panes", "menu", "popup"))


class ScreenPainter:
    """Paints a Screen with cairo/Pango; box-drawing characters as lines."""

    def __init__(self):
        self._metrics = {}

    def font(self, px: float) -> Pango.FontDescription:
        desc = Pango.FontDescription.from_string(FONT_FAMILY)
        desc.set_absolute_size(px * Pango.SCALE)
        return desc

    def measure(self, cr):
        """Cell width/height for a 100px font, measured once."""
        if "base" not in self._metrics:
            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(self.font(100))
            layout.set_text("M" * 20, -1)
            _ink, logical = layout.get_pixel_extents()
            self._metrics["base"] = (logical.width / 20, logical.height)
        return self._metrics["base"]

    def error(self, cr, e):
        cr.set_source_rgb(0.5, 0, 0)
        cr.paint()
        layout = PangoCairo.create_layout(cr)
        layout.set_text(f"Preview error: {e}", -1)
        cr.set_source_rgb(1, 1, 1)
        PangoCairo.show_layout(cr, layout)

    def paint(self, cr, screen, width, height, scale, palette="dark", cursor=True):
        pal = PALETTES[palette]
        cw100, ch100 = self.measure(cr)
        cw, chh = cw100 * scale, ch100 * scale
        ox = (width - screen.cols * cw) / 2
        oy = (height - screen.rows * chh) / 2
        cr.set_source_rgb(*[c / 255 for c in pal["bg"]])
        cr.paint()
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(self.font(100 * scale))
        # Backgrounds first, then text, so descenders (e.g. "_") are not
        # painted over by the next row.
        pieces = []
        for y, row in enumerate(screen.cells):
            x = 0
            while x < len(row):
                ch, style = row[x]
                boxy = ch in _BOX
                end = x + 1
                if ch.isascii() and not boxy:
                    while (end < len(row) and row[end][1] == style
                           and row[end][0].isascii()):
                        end += 1
                fg, bg = self.colours(style, pal)
                rx, ry = ox + x * cw, oy + y * chh
                cr.set_source_rgb(*[c / 255 for c in bg])
                cr.rectangle(rx, ry, (end - x) * cw + 0.6, chh + 0.6)
                cr.fill()
                text = "".join(c for c, _ in row[x:end])
                if boxy or text.strip():
                    pieces.append((text, style, fg, rx, ry, boxy))
                x = end
        for text, style, fg, rx, ry, boxy in pieces:
            if boxy:
                self._box_char(cr, text, rx, ry, cw, chh, fg, "bright" in style.attrs)
            else:
                cr.set_source_rgb(*[c / 255 for c in fg])
                self._text(cr, layout, text, style, rx, ry)

        cur = screen.cursor
        if cur is not None and cursor:
            colour = _rgb(cur.colour, pal["fg"])
            rx, ry = ox + cur.x * cw, oy + cur.y * chh
            cr.set_source_rgb(*[c / 255 for c in colour])
            if cur.shape == "underline":
                cr.rectangle(rx, ry + chh - max(2, chh * 0.12), cw, max(2, chh * 0.12))
            elif cur.shape == "bar":
                cr.rectangle(rx, ry, max(2, cw * 0.15), chh)
            else:
                cr.rectangle(rx, ry, cw, chh)
            cr.fill()

    def colours(self, style: CellStyle, pal):
        fg = _rgb(style.fg, pal["fg"])
        bg = _rgb(style.bg, pal["bg"])
        if "reverse" in style.attrs:
            fg, bg = bg, fg
        if "dim" in style.attrs:
            fg = _blend(fg, bg, 0.45)
        if "hidden" in style.attrs:
            fg = bg
        return fg, bg

    def _text(self, cr, layout, text, style, x, y):
        attrs = style.attrs
        span = []
        if "bright" in attrs:
            span.append('weight="bold"')
        if "italics" in attrs:
            span.append('style="italic"')
        if "double-underscore" in attrs:
            span.append('underline="double"')
        elif "curly-underscore" in attrs:
            span.append('underline="error"')
        elif attrs & {"underscore", "dotted-underscore", "dashed-underscore"}:
            span.append('underline="single"')
        if "strikethrough" in attrs:
            span.append('strikethrough="true"')
        if "overline" in attrs:
            span.append('overline="single"')
        esc = GLib.markup_escape_text(text)
        if span:
            layout.set_markup(f"<span {' '.join(span)}>{esc}</span>", -1)
        else:
            layout.set_attributes(None)  # drop attributes from the last run
            layout.set_text(text, -1)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)

    def _box_char(self, cr, ch, x, y, cw, chh, fg, bold):
        up, down, left, right = _BOX[ch]
        cx, cy = x + cw / 2, y + chh / 2
        light = max(1.0, round(cw * 0.12))
        cr.set_source_rgb(*[c / 255 for c in fg])
        gap = max(1.5, cw * 0.18)

        def seg(weight, x1, y1, x2, y2, vertical):
            if not weight:
                return
            if weight == 3:
                for d in (-gap, gap):
                    cr.set_line_width(light)
                    if vertical:
                        cr.move_to(x1 + d, y1)
                        cr.line_to(x2 + d, y2)
                    else:
                        cr.move_to(x1, y1 + d)
                        cr.line_to(x2, y2 + d)
                    cr.stroke()
                return
            cr.set_line_width(light * (2 if weight == 2 or bold else 1))
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # Extend each half past the centre so joins close cleanly.
        ext_v = gap if 3 in (left, right) else light / 2
        ext_h = gap if 3 in (up, down) else light / 2
        seg(up, cx, y, cx, cy + ext_v, True)
        seg(down, cx, cy - ext_v, cx, y + chh, True)
        seg(left, x, cy, cx + ext_h, cy, False)
        seg(right, cx - ext_h, cy, x + cw, cy, False)


class ScreenStrip(Gtk.DrawingArea):
    """Paints a few rows (e.g. a status line) built by *screen_fn(cols)*."""

    def __init__(self, screen_fn, rows: int = 1, row_px: int = 22):
        super().__init__(hexpand=True, content_height=rows * row_px + 8)
        self.screen_fn = screen_fn
        self.rows = rows
        self.painter = ScreenPainter()
        self.palette = "dark"
        self.set_draw_func(self._draw)

    def _draw(self, _a, cr, width, height):
        cw100, ch100 = self.painter.measure(cr)
        scale = min((height - 8) / (self.rows * ch100), 0.16)
        cols = max(10, int(width / (cw100 * scale)))
        try:
            screen = self.screen_fn(cols)
        except Exception as e:
            self.painter.error(cr, e)
            return
        self.painter.paint(cr, screen, width, height, scale, self.palette,
                           cursor=False)
