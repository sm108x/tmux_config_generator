"""Builder for the terminal-features and terminal-overrides array options."""

from __future__ import annotations

import fnmatch
import os

from gi.repository import GLib, Gtk, Pango

from ..terminal import (CAPABILITIES, CAPABILITY_INFO, FEATURE_NAMES,
                        FEATURE_RECIPES, FEATURES, OVERRIDE_RECIPES, PATTERNS,
                        format_override, join_entry, parse_override,
                        split_entry)
from .dialogs import Dialog

MODES = [("set", "= value"), ("flag", "on (flag)"), ("unset", "@ remove")]


def _dim(text: str, **kw) -> Gtk.Label:
    lab = Gtk.Label(label=text, xalign=0, **kw)
    lab.add_css_class("dim-label")
    return lab


def _popover_list(button: Gtk.MenuButton, items, on_pick):
    """Fill a MenuButton with a popover list of (title, subtitle, payload)."""
    pop = Gtk.Popover()
    lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    for title, subtitle, payload in items:
        r = Gtk.ListBoxRow()
        r.payload = payload
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=3,
                    margin_bottom=3, margin_start=6, margin_end=6)
        v.append(Gtk.Label(label=title, xalign=0))
        if subtitle:
            sub = _dim(subtitle, ellipsize=Pango.EllipsizeMode.END, max_width_chars=60)
            sub.add_css_class("caption")
            sub.add_css_class("monospace")
            v.append(sub)
        r.set_child(v)
        lb.append(r)

    def activated(_lb, r):
        pop.popdown()
        on_pick(r.payload)
    lb.connect("row-activated", activated)
    sw = Gtk.ScrolledWindow(max_content_height=420, propagate_natural_height=True,
                            propagate_natural_width=True)
    sw.set_child(lb)
    pop.set_child(sw)
    button.set_popover(pop)


class TerminalListBuilder(Dialog):
    """Edit every entry of terminal-features or terminal-overrides."""

    def __init__(self, parent, option: str, entries: list[str], callback):
        super().__init__(parent, f"Builder — {option}", "Apply")
        self.option = option
        self.features = option == "terminal-features"
        self.callback = callback
        self.entries = [split_entry(e) for e in entries if e.strip()]
        self.set_default_size(900, 600)

        intro = Gtk.Label(xalign=0, wrap=True)
        if self.features:
            intro.set_markup(
                "<b>terminal-features</b>: tell tmux what your outer terminal supports. "
                "Each entry is a terminal type pattern plus the features to enable for "
                "matching terminals.")
        else:
            intro.set_markup(
                "<b>terminal-overrides</b>: change individual terminfo capabilities for "
                "matching terminals. Prefer terminal-features where a feature exists.")
        self.content.append(intro)
        term = os.environ.get("TERM", "")
        self.term = term
        if term:
            self.content.append(_dim(f"Your current TERM is {term}"))

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=300,
                          vexpand=True, shrink_start_child=False)
        # Left: entries
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_end=6)
        tools = Gtk.Box(spacing=4)
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New entry")
        add.connect("clicked", lambda *_: self._add(["xterm*"]))
        rm = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove entry")
        rm.connect("clicked", lambda *_: self._remove())
        recipes = Gtk.MenuButton(label="Recipes", always_show_arrow=True,
                                 tooltip_text="Add a ready-made entry")
        _popover_list(recipes, [(label, entry, entry) for label, entry in
                                (FEATURE_RECIPES if self.features else OVERRIDE_RECIPES)],
                      lambda e: self._add(split_entry(e)))
        for w in (add, rm, recipes):
            tools.append(w)
        left.append(tools)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.connect("row-selected", lambda _lb, r: self._edit(r))
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_child(self.list)
        fr = Gtk.Frame()
        fr.set_child(sw)
        left.append(fr)
        paned.set_start_child(left)

        # Right: editor for the selected entry
        self.editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                              margin_start=6)
        esw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        esw.set_child(self.editor)
        paned.set_end_child(esw)
        self.content.append(paned)

        self.result = Gtk.Label(xalign=0, selectable=True, wrap=True,
                                wrap_mode=Pango.WrapMode.CHAR)
        self.result.add_css_class("monospace")
        self.content.append(self.result)
        self._rebuild_list(0 if self.entries else None)

    # -- list ----------------------------------------------------------------

    def _rebuild_list(self, select: int | None):
        self.list.remove_all()
        for parts in self.entries:
            lab = Gtk.Label(label=join_entry(parts), xalign=0,
                            ellipsize=Pango.EllipsizeMode.END, margin_top=4,
                            margin_bottom=4, margin_start=6)
            lab.add_css_class("monospace")
            self.list.append(lab)
        if select is not None and select < len(self.entries):
            self.list.select_row(self.list.get_row_at_index(select))
        else:
            self._edit(None)
        self._update_result()

    def _index(self):
        r = self.list.get_selected_row()
        return r.get_index() if r else None

    def _add(self, parts):
        self.entries.append(list(parts))
        self._rebuild_list(len(self.entries) - 1)

    def _remove(self):
        i = self._index()
        if i is not None:
            del self.entries[i]
            self._rebuild_list(min(i, len(self.entries) - 1) if self.entries else None)

    def _changed(self):
        """Refresh the selected row's label and the result line."""
        i = self._index()
        if i is not None:
            self.list.get_row_at_index(i).get_child().set_label(join_entry(self.entries[i]))
        self._update_result()

    def _update_result(self):
        n = len(self.entries)
        self.result.set_label(
            f"{n} entr{'y' if n == 1 else 'ies'}:\n" +
            "\n".join(join_entry(p) for p in self.entries) if n else "No entries.")

    # -- editor ----------------------------------------------------------------

    def _edit(self, row):
        child = self.editor.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.editor.remove(child)
            child = nxt
        if row is None:
            self.editor.append(_dim("Select an entry, click + or pick a recipe."))
            return
        parts = self.entries[row.get_index()]
        self._pattern_editor(parts)
        if self.features:
            self._features_editor(parts)
        else:
            self._overrides_editor(parts)

    def _pattern_editor(self, parts):
        box = Gtk.Box(spacing=6)
        box.append(Gtk.Label(label="Terminal pattern"))
        entry = Gtk.Entry(text=parts[0], hexpand=True,
                          tooltip_text="fnmatch pattern for TERM of the outer terminal")
        entry.add_css_class("monospace")
        match = _dim("")

        def sync(*_):
            parts[0] = entry.get_text().strip()
            if self.term:
                ok = fnmatch.fnmatchcase(self.term, parts[0]) if parts[0] else False
                match.set_label(f"✓ matches your terminal ({self.term})" if ok
                                else f"does not match your terminal ({self.term})")
            self._changed()
        entry.connect("changed", sync)
        pick = Gtk.MenuButton(icon_name="view-list-symbolic", tooltip_text="Common patterns")
        _popover_list(pick, [(p, d, p) for p, d in PATTERNS], entry.set_text)
        box.append(entry)
        box.append(pick)
        self.editor.append(box)
        self.editor.append(match)
        sync()

    def _features_editor(self, parts):
        self.editor.append(Gtk.Label(label="Features", xalign=0,
                                     css_classes=["heading"]))
        grid = Gtk.Grid(column_spacing=12, row_spacing=2)
        checks = {}

        def sync(*_):
            chosen = [f for f in FEATURE_NAMES if checks[f].get_active()]
            unknown = [p for p in parts[1:] if p and p not in FEATURE_NAMES]
            parts[1:] = chosen + unknown
            self._changed()
        for i, (name, desc) in enumerate(FEATURES):
            cb = Gtk.CheckButton(label=name, active=name in parts[1:])
            cb.connect("toggled", sync)
            checks[name] = cb
            grid.attach(cb, 0, i, 1, 1)
            grid.attach(_dim(desc, wrap=True, hexpand=True), 1, i, 1, 1)
        self.editor.append(grid)
        unknown = [p for p in parts[1:] if p and p not in FEATURE_NAMES]
        if unknown:
            self.editor.append(_dim("Kept as-is (not a tmux 3.4 feature): " + ", ".join(unknown)))

    def _overrides_editor(self, parts):
        head = Gtk.Box(spacing=6)
        head.append(Gtk.Label(label="Capabilities", xalign=0, hexpand=True,
                              css_classes=["heading"]))
        add = Gtk.MenuButton(label="Add capability", always_show_arrow=True)
        head.append(add)
        self.editor.append(head)
        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.editor.append(rows_box)
        self.editor.append(_dim(
            "Values use terminfo syntax: \\E is Escape, %p1%d the first parameter. "
            "Colons inside values are written as :: in the config (done for you).",
            wrap=True))
        rows = []

        def sync(*_):
            items = []
            for cap_e, mode_dd, val_e, _desc, _row in rows:
                cap = cap_e.get_text().strip()
                if not cap:
                    continue
                mode = MODES[mode_dd.get_selected()][0]
                val_e.set_sensitive(mode == "set")
                items.append(format_override(cap, mode, val_e.get_text()))
            parts[1:] = items
            self._changed()

        def add_row(cap="", mode="set", value=""):
            row = Gtk.Box(spacing=6)
            cap_e = Gtk.Entry(text=cap, width_chars=8, placeholder_text="cap")
            cap_e.add_css_class("monospace")
            mode_dd = Gtk.DropDown.new_from_strings([m[1] for m in MODES])
            mode_dd.set_selected([m[0] for m in MODES].index(mode))
            val_e = Gtk.Entry(text=value, hexpand=True, placeholder_text="value")
            val_e.add_css_class("monospace")
            rm = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Remove")
            desc = _dim("", wrap=True)
            desc.add_css_class("caption")

            def describe(*_):
                info = CAPABILITY_INFO.get(cap_e.get_text().strip())
                desc.set_label(info[2] if info else "")
            cap_e.connect("changed", describe)
            describe()
            for w in (cap_e, mode_dd, val_e, rm):
                row.append(w)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            outer.append(row)
            outer.append(desc)
            entry = (cap_e, mode_dd, val_e, desc, outer)
            rows.append(entry)

            def remove(*_):
                rows.remove(entry)
                rows_box.remove(outer)
                sync()
            rm.connect("clicked", remove)
            cap_e.connect("changed", sync)
            val_e.connect("changed", sync)
            mode_dd.connect("notify::selected", sync)
            rows_box.append(outer)

        for item in parts[1:]:
            if item:
                add_row(*parse_override(item))

        def add_cap(cap):
            _name, kind, _desc, example = CAPABILITY_INFO[cap]
            add_row(cap, "flag" if kind == "flag" else "set", example)
            sync()
        _popover_list(add, [(f"{c}  —  {d}", ex, c) for c, _k, d, ex in CAPABILITIES],
                      add_cap)
        sync()

    def on_ok(self):
        # A pattern with nothing after it has no effect, so drop it.
        self.callback([join_entry(p) for p in self.entries
                       if p and p[0] and any(x for x in p[1:])])
        self.close()


class DefaultTerminalEditor(Gtk.Box):
    """Dropdown of common default-terminal values, with 'Other…' free text.

    The Gtk.Entry *entry* stays the source of truth for the option value.
    """

    def __init__(self, entry: Gtk.Entry):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        from ..terminal import DEFAULT_TERMINALS, terminfo_available
        self.entry = entry
        self.names = [n for n, _d in DEFAULT_TERMINALS]
        self.descriptions = dict(DEFAULT_TERMINALS)
        self.available = terminfo_available
        self._updating = False

        model = Gtk.StringList.new(self.names + ["Other…"])
        self.dd = Gtk.DropDown(model=model)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_item)
        factory.connect("bind", self._bind_item)
        self.dd.set_list_factory(factory)
        self.dd.connect("notify::selected", self._on_selected)
        top = Gtk.Box(spacing=6)
        top.append(self.dd)
        top.append(entry)
        self.append(top)
        self.status = Gtk.Label(xalign=0)
        self.status.add_css_class("caption")
        self.append(self.status)
        entry.connect("changed", lambda *_: self.sync())
        self.sync()

    def _setup_item(self, _f, li):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        v.append(Gtk.Label(xalign=0))
        sub = _dim("", wrap=True, max_width_chars=50)
        sub.add_css_class("caption")
        v.append(sub)
        li.set_child(v)

    def _bind_item(self, _f, li):
        name = li.get_item().get_string()
        title, sub = li.get_child().get_first_child(), li.get_child().get_last_child()
        mark = ""
        if name in self.descriptions:
            ok = self.available(name)
            mark = {True: "  ✓", False: "  (not installed here)", None: ""}[ok]
        title.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>{GLib.markup_escape_text(mark)}")
        sub.set_label(self.descriptions.get(name, "Type any terminfo name"))

    def _on_selected(self, dd, _p):
        if self._updating:
            return
        i = dd.get_selected()
        # Act after the dropdown's notify emission has finished: changing
        # widgets from inside it can deadlock GTK.
        if i < len(self.names):
            GLib.idle_add(lambda: (self.entry.set_text(self.names[i]), False)[1])
        else:
            def show():
                self.entry.set_visible(True)
                self.entry.grab_focus()
                return False
            GLib.idle_add(show)

    def sync(self):
        value = self.entry.get_text().strip()
        known = value in self.names
        target = self.names.index(value) if known else len(self.names)
        if self.dd.get_selected() != target:
            self._updating = True
            self.dd.set_selected(target)
            self._updating = False
        if self.entry.get_visible() == known:
            self.entry.set_visible(not known)
        ok = self.available(value) if value else False
        if not value:
            self.status.set_label("")
        elif ok is None:
            self.status.set_label("terminfo database not found on this machine")
        elif ok:
            self.status.set_label(f"✓ terminfo entry '{value}' is installed here")
        else:
            self.status.set_label(f"⚠ no terminfo entry '{value}' on this machine")
