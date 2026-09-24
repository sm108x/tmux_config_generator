"""A page listing the options of one category, one editable row each."""

from __future__ import annotations

from gi.repository import Gtk

from ..config import INDEX_ONLY, Config
from ..options import Option, options_in
from .dialogs import ColourEntry, KeyCaptureDialog, StyleDialog

SCOPE_LABELS = {"server": "server", "session": "session", "window": "window",
                "pane": "pane"}


class OptionRow(Gtk.ListBoxRow):
    """Include-checkbox, name/description, value editor and reset button."""

    def __init__(self, opt: Option, cfg: Config, on_change):
        super().__init__(activatable=False)
        self.opt = opt
        self.cfg = cfg
        self.on_change = on_change
        self._updating = False

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                      margin_top=6, margin_bottom=6, margin_start=6,
                      margin_end=6)
        self.include = Gtk.CheckButton(valign=Gtk.Align.CENTER,
                                       tooltip_text="Write this option to the config")
        self.include.connect("toggled", self._on_include)
        box.append(self.include)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       hexpand=True, valign=Gtk.Align.CENTER)
        name = Gtk.Label(xalign=0, selectable=True)
        name.set_markup(f"<b>{opt.name}</b>  <small>{SCOPE_LABELS[opt.scope]}"
                        f" · {opt.type}</small>")
        desc = Gtk.Label(label=opt.description, xalign=0, wrap=True,
                         max_width_chars=70, width_chars=40)
        desc.add_css_class("dim-label")
        desc.add_css_class("caption")
        text.append(name)
        text.append(desc)
        box.append(text)

        self.editor = self._build_editor()
        self.editor.set_valign(Gtk.Align.CENTER)
        box.append(self.editor)

        reset = Gtk.Button(icon_name="edit-undo-symbolic", valign=Gtk.Align.CENTER,
                           tooltip_text="Reset to tmux default and exclude")
        reset.add_css_class("flat")
        reset.connect("clicked", lambda *_: self.reset())
        box.append(reset)
        self.set_child(box)
        self.refresh()

    # -- editor widgets ---------------------------------------------------

    def _build_editor(self) -> Gtk.Widget:
        t = self.opt.type
        if t == "flag":
            self.switch = Gtk.Switch()
            self.switch.connect("notify::active", self._edited)
            return self.switch
        if t == "choice":
            self.dropdown = Gtk.DropDown.new_from_strings(list(self.opt.choices))
            self.dropdown.connect("notify::selected", self._edited)
            return self.dropdown
        if t == "number":
            adj = Gtk.Adjustment(lower=self.opt.min, upper=self.opt.max,
                                 step_increment=1, page_increment=10)
            self.spin = Gtk.SpinButton(adjustment=adj, numeric=True, width_chars=8)
            self.spin.connect("value-changed", self._edited)
            return self.spin
        if t == "colour":
            self.colour = ColourEntry(on_changed=lambda *_: self._edited())
            return self.colour
        if t == "list":
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            scroll = Gtk.ScrolledWindow(min_content_height=80,
                                        min_content_width=320)
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            self.textview = Gtk.TextView(monospace=True, top_margin=4,
                                         bottom_margin=4, left_margin=4)
            self.textview.get_buffer().connect("changed", self._edited)
            scroll.set_child(self.textview)
            frame = Gtk.Frame()
            frame.set_child(scroll)
            hint = Gtk.Label(label="One entry per line", xalign=0)
            hint.add_css_class("dim-label")
            hint.add_css_class("caption")
            box.append(frame)
            box.append(hint)
            self.append_check = Gtk.CheckButton(label="Append to tmux defaults")
            self.append_check.connect("toggled", self._edited)
            if self.opt.name not in INDEX_ONLY:
                box.append(self.append_check)
            return box

        # string / format / style / key: an entry, maybe with a helper button
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.add_css_class("linked")
        self.entry = Gtk.Entry(width_chars=24 if t in ("key", "style") else 32)
        if t == "format":
            self.entry.add_css_class("monospace")
        self.entry.connect("changed", self._edited)
        box.append(self.entry)
        if t == "style":
            b = Gtk.Button(icon_name="document-edit-symbolic",
                           tooltip_text="Style editor…")
            b.connect("clicked", self._edit_style)
            box.append(b)
        elif t == "key":
            b = Gtk.Button(icon_name="input-keyboard-symbolic",
                           tooltip_text="Capture a key…")
            b.connect("clicked", self._capture_key)
            box.append(b)
        return box

    def _edit_style(self, _btn):
        StyleDialog(self.get_root(), self.entry.get_text(),
                    self.entry.set_text).present()

    def _capture_key(self, _btn):
        KeyCaptureDialog(self.get_root(), self.entry.set_text,
                         self.entry.get_text()).present()

    # -- value plumbing ---------------------------------------------------

    def get_value(self):
        t = self.opt.type
        if t == "flag":
            return "on" if self.switch.get_active() else "off"
        if t == "choice":
            return self.opt.choices[self.dropdown.get_selected()]
        if t == "number":
            return str(self.spin.get_value_as_int())
        if t == "colour":
            return self.colour.get_text()
        if t == "list":
            buf = self.textview.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            return [line for line in text.split("\n") if line.strip()]
        return self.entry.get_text()

    def set_value(self, value):
        t = self.opt.type
        if t == "flag":
            self.switch.set_active(value == "on")
        elif t == "choice":
            if value in self.opt.choices:
                self.dropdown.set_selected(self.opt.choices.index(value))
        elif t == "number":
            try:
                self.spin.set_value(int(value))
            except (TypeError, ValueError):
                pass
        elif t == "colour":
            self.colour.set_text(value)
        elif t == "list":
            self.textview.get_buffer().set_text("\n".join(value))
        else:
            self.entry.set_text(value)

    def refresh(self):
        """Load state from the config model."""
        self._updating = True
        included = self.opt.name in self.cfg.values
        self.set_value(self.cfg.values[self.opt.name] if included
                       else self.opt.default)
        if self.opt.type == "list":
            self.append_check.set_active(self.opt.name in self.cfg.list_append)
        self.include.set_active(included)
        self._update_style(included)
        self._updating = False

    def reset(self):
        self.cfg.unset(self.opt.name)
        self.refresh()
        self.on_change()

    def _update_style(self, included):
        if included:
            self.add_css_class("option-included")
        else:
            self.remove_css_class("option-included")

    def _store(self):
        self.cfg.set(self.opt.name, self.get_value())
        if self.opt.type == "list":
            if self.append_check.get_active() and self.opt.name not in INDEX_ONLY:
                self.cfg.list_append.add(self.opt.name)
            else:
                self.cfg.list_append.discard(self.opt.name)

    def _edited(self, *_):
        if self._updating:
            return
        self._store()
        self._updating = True
        self.include.set_active(True)
        self._updating = False
        self._update_style(True)
        self.on_change()

    def _on_include(self, check):
        if self._updating:
            return
        if check.get_active():
            self._store()
        else:
            self.cfg.unset(self.opt.name)
        self._update_style(check.get_active())
        self.on_change()

    def matches(self, query: str) -> bool:
        q = query.lower()
        return q in self.opt.name or q in self.opt.description.lower()


class OptionPage(Gtk.ScrolledWindow):
    def __init__(self, category: str, cfg: Config, on_change):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                   margin_top=12, margin_bottom=12,
                                   margin_start=12, margin_end=12)
        self.listbox.add_css_class("boxed-list")
        self.rows = [OptionRow(o, cfg, on_change) for o in options_in(category)]
        for r in self.rows:
            self.listbox.append(r)
        self.query = ""
        self.listbox.set_filter_func(lambda row: row.matches(self.query))
        self.set_child(self.listbox)

    def refresh(self):
        for r in self.rows:
            r.refresh()

    def filter(self, query: str) -> int:
        self.query = query.strip()
        self.listbox.invalidate_filter()
        return sum(1 for r in self.rows if r.matches(self.query))
