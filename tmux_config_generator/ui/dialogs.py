"""Reusable dialogs: key capture, style editor, colour entry."""

from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk

from ..keys import MOUSE_KEYS, SPECIAL_KEYS, event_to_tmux
from ..styles import ATTRIBUTES, NAMED_COLOURS, colour_to_rgb, parse_style, rgb_to_hex


def button_row(*buttons: Gtk.Widget) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                  halign=Gtk.Align.END, margin_top=12)
    for b in buttons:
        box.append(b)
    return box


class Dialog(Gtk.Window):
    """A small modal window with a content box and OK/Cancel buttons."""

    def __init__(self, parent: Gtk.Window, title: str, ok_label: str = "OK"):
        super().__init__(title=title, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                               margin_top=16, margin_bottom=16,
                               margin_start=16, margin_end=16)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", lambda *_: self.close())
        self.ok_button = Gtk.Button(label=ok_label)
        self.ok_button.add_css_class("suggested-action")
        self.ok_button.connect("clicked", lambda *_: self.on_ok())
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.content)
        outer.append(button_row(self.cancel_button, self.ok_button))
        outer.set_margin_bottom(12)
        outer.set_margin_end(12)
        self.set_child(outer)
        self.set_default_widget(self.ok_button)

    def on_ok(self):
        self.close()


class KeyCaptureDialog(Dialog):
    """Captures one key press and reports it as a tmux key name."""

    def __init__(self, parent: Gtk.Window, callback, initial: str = ""):
        super().__init__(parent, "Capture Key", "Use Key")
        self.callback = callback
        self.key = initial
        hint = Gtk.Label(label="Press the key combination to bind.\n"
                               "Mouse and other special keys can be picked below.",
                         justify=Gtk.Justification.CENTER)
        hint.add_css_class("dim-label")
        self.key_label = Gtk.Label(label=initial or "…", margin_top=12,
                                   margin_bottom=12)
        self.key_label.add_css_class("title-1")
        self.key_label.add_css_class("monospace")

        special = [""] + SPECIAL_KEYS + MOUSE_KEYS
        self.special = Gtk.DropDown.new_from_strings(
            ["Special / mouse key…"] + special[1:])
        self.special.set_enable_search(True)
        self.special.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.special.connect("notify::selected", self._on_special)
        # Keep keyboard focus off widgets so Tab/Space/Enter are captured.
        self.special.set_focus_on_click(False)
        for b in (self.ok_button, self.cancel_button):
            b.set_focus_on_click(False)

        self.content.append(hint)
        self.content.append(self.key_label)
        self.content.append(self.special)
        self.set_default_widget(None)

        ctl = Gtk.EventControllerKey()
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctl.connect("key-pressed", self._on_key)
        self.add_controller(ctl)
        self.set_default_size(360, -1)

    def _on_key(self, _ctl, keyval, _keycode, state):
        focus = self.get_focus()
        if focus is not None and focus.is_ancestor(self.special):
            return False  # typing into the dropdown's search box
        ch =Gdk.keyval_to_unicode(keyval)
        name = event_to_tmux(
            Gdk.keyval_name(keyval), chr(ch) if ch else "",
            bool(state & Gdk.ModifierType.CONTROL_MASK),
            bool(state & Gdk.ModifierType.ALT_MASK),
            bool(state & Gdk.ModifierType.SHIFT_MASK))
        if name is None:
            return False
        self._set(name)
        return True

    def _on_special(self, dd, _pspec):
        if dd.get_selected() > 0:
            self._set(dd.get_selected_item().get_string())

    def _set(self, name: str):
        self.key = name
        self.key_label.set_label(name)

    def on_ok(self):
        if self.key:
            self.callback(self.key)
        self.close()


class ColourEntry(Gtk.Box):
    """Entry for a tmux colour with a swatch/picker button."""

    def __init__(self, on_changed=None, allow_empty=True):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.add_css_class("linked")
        self.on_changed = on_changed
        self._updating = False
        self.entry = Gtk.Entry(width_chars=14, hexpand=True,
                               placeholder_text="e.g. red, colour33, #ff8800")
        self.entry.connect("changed", self._on_entry)
        completion_names = NAMED_COLOURS + [f"colour{i}" for i in range(256)]
        self.names = Gtk.DropDown.new_from_strings([""] + completion_names)
        self.names.set_enable_search(True)
        self.names.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.names.set_tooltip_text("Pick a named or palette colour")
        self.names.connect("notify::selected", self._on_name)
        self.picker = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
        self.picker.set_tooltip_text("Pick an RGB colour")
        self.picker.connect("notify::rgba", self._on_pick)
        self.append(self.entry)
        self.append(self.names)
        self.append(self.picker)

    def get_text(self) -> str:
        return self.entry.get_text().strip()

    def set_text(self, text: str):
        self._updating = True
        self.entry.set_text(text)
        self._sync_swatch(text)
        self._updating = False

    def _sync_swatch(self, text):
        rgb = colour_to_rgb(text)
        if rgb:
            rgba = Gdk.RGBA()
            rgba.parse(rgb_to_hex(*rgb))
            was = self._updating
            self._updating = True
            self.picker.set_rgba(rgba)
            self._updating = was

    def _on_entry(self, entry):
        if self._updating:
            return
        self._sync_swatch(entry.get_text())
        if self.on_changed:
            self.on_changed(self.get_text())

    def _on_name(self, dd, _pspec):
        if dd.get_selected() > 0:
            self.entry.set_text(dd.get_selected_item().get_string())
            dd.set_selected(0)

    def _on_pick(self, btn, _pspec):
        if self._updating:
            return
        c = btn.get_rgba()
        self.entry.set_text(rgb_to_hex(round(c.red * 255), round(c.green * 255),
                                       round(c.blue * 255)))


class StyleDialog(Dialog):
    """Edits a tmux style string (fg/bg/underscore colours and attributes)."""

    def __init__(self, parent: Gtk.Window, value: str, callback):
        super().__init__(parent, "Edit Style", "Apply")
        self.callback = callback
        style = parse_style(value)
        self.style = style

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        self.colours = {}
        for row, (key, label) in enumerate([("fg", "Foreground"),
                                            ("bg", "Background"),
                                            ("us", "Underscore colour"),
                                            ("fill", "Fill colour")]):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            ce = ColourEntry(on_changed=lambda *_: self._update_preview())
            ce.set_text(getattr(style, key))
            self.colours[key] = ce
            grid.attach(ce, 1, row, 1, 1)
        self.content.append(grid)

        self.default_check = Gtk.CheckButton(
            label="Start from 'default' (reset inherited style first)",
            active=style.default)
        self.default_check.connect("toggled", lambda *_: self._update_preview())
        self.content.append(self.default_check)

        frame = Gtk.Frame(label="Attributes")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                           max_children_per_line=4, column_spacing=6,
                           margin_top=6, margin_bottom=6, margin_start=6,
                           margin_end=6)
        self.attr_checks = {}
        for a in ATTRIBUTES:
            cb = Gtk.CheckButton(label=a, active=a in style.attrs)
            cb.connect("toggled", lambda *_: self._update_preview())
            self.attr_checks[a] = cb
            flow.append(cb)
        frame.set_child(flow)
        self.content.append(frame)

        self.result_label = Gtk.Label(xalign=0, selectable=True, wrap=True)
        self.result_label.add_css_class("monospace")
        self.preview = Gtk.Label(label="  #[tmux] sample text  ",
                                 margin_top=6, xalign=0.5)
        self.preview.add_css_class("monospace")
        self.content.append(self.preview)
        self.content.append(self.result_label)
        if style.other:
            note = Gtk.Label(label="Kept unrecognised parts: " + ",".join(style.other),
                             xalign=0, wrap=True)
            note.add_css_class("dim-label")
            self.content.append(note)
        self._update_preview()

    def _current(self):
        s = self.style
        for key, ce in self.colours.items():
            setattr(s, key, ce.get_text())
        s.default = self.default_check.get_active()
        s.attrs = {a for a, cb in self.attr_checks.items() if cb.get_active()}
        return s

    def _update_preview(self):
        s = self._current()
        text = s.to_string()
        self.result_label.set_label(text)
        attrs = []
        fg, bg = colour_to_rgb(s.fg), colour_to_rgb(s.bg)
        if "reverse" in s.attrs:
            fg, bg = bg or (0xff, 0xff, 0xff), fg or (0, 0, 0)
        if fg:
            attrs.append(f'foreground="{rgb_to_hex(*fg)}"')
        if bg:
            attrs.append(f'background="{rgb_to_hex(*bg)}"')
        if "bright" in s.attrs:
            attrs.append('weight="bold"')
        if "dim" in s.attrs:
            attrs.append('alpha="60%"')
        if "italics" in s.attrs:
            attrs.append('style="italic"')
        if s.attrs & {"underscore", "curly-underscore", "dotted-underscore",
                      "dashed-underscore"}:
            attrs.append('underline="single"')
        if "double-underscore" in s.attrs:
            attrs.append('underline="double"')
        if "strikethrough" in s.attrs:
            attrs.append('strikethrough="true"')
        if "overline" in s.attrs:
            attrs.append('overline="single"')
        sample = GLib.markup_escape_text("  sample text 0123  ")
        self.preview.set_markup(f"<span {' '.join(attrs)}>{sample}</span>")

    def on_ok(self):
        self.callback(self._current().to_string())
        self.close()
