"""Key bindings editor: custom bindings, unbinds and tmux default reference."""

from __future__ import annotations

from gi.repository import Gio, GObject, Gtk, Pango

from ..commands import TMUX_COMMANDS
from ..config import KEY_TABLES, Binding, Config, Unbind
from ..default_bindings import DEFAULT_BINDINGS
from ..presets import COMMAND_PRESETS
from .dialogs import Dialog, KeyCaptureDialog

ALL_TABLES = "All tables"
TABLE_HELP = {
    "prefix": "after pressing the prefix key",
    "root": "without the prefix (bind -n)",
    "copy-mode": "in emacs-style copy mode",
    "copy-mode-vi": "in vi-style copy mode",
}


def default_binding(table: str, key: str):
    for row in DEFAULT_BINDINGS:
        if row[0] == table and row[1] == key:
            return row
    return None


class Item(GObject.Object):
    """GObject wrapper so bindings can live in a Gio.ListStore."""

    def __init__(self, obj):
        super().__init__()
        self.obj = obj


def _label_factory(getter, css=None):
    factory = Gtk.SignalListItemFactory()

    def setup(_f, li):
        lbl = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        if css:
            lbl.add_css_class(css)
        li.set_child(lbl)

    def bind(_f, li):
        text = getter(li.get_item().obj)
        li.get_child().set_label(text)
        li.get_child().set_tooltip_text(text if len(text) > 30 else None)

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


def make_column_view(model, columns, on_activate=None):
    """Build a ColumnView over *model*; columns are (title, getter, expand, css)."""
    selection = Gtk.SingleSelection(model=model, autoselect=False,
                                    can_unselect=True)
    view = Gtk.ColumnView(model=selection, show_row_separators=True,
                          vexpand=True)
    view.add_css_class("data-table")
    for title, getter, expand, css in columns:
        col = Gtk.ColumnViewColumn(title=title,
                                   factory=_label_factory(getter, css),
                                   expand=expand, resizable=True)
        view.append_column(col)
    if on_activate:
        view.connect("activate", lambda _v, pos: on_activate(pos))
    return view, selection


def table_dropdown_strings(extra_tables=()):
    tables = list(KEY_TABLES)
    for t in extra_tables:
        if t not in tables:
            tables.append(t)
    return tables


class BindingEditor(Dialog):
    """Dialog for creating/editing a single binding."""

    def __init__(self, parent, cfg: Config, binding: Binding | None, callback,
                 editing: Binding | None = None):
        super().__init__(parent, "Edit Binding" if editing else "New Binding",
                         "Save")
        self.cfg = cfg
        self.callback = callback
        self.editing = editing
        b = binding or Binding(key="", command="")
        self.set_default_size(640, -1)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        row = 0

        # Key table
        self.tables = table_dropdown_strings([b.table]) + ["Other…"]
        self.table_dd = Gtk.DropDown.new_from_strings(self.tables)
        self.table_entry = Gtk.Entry(placeholder_text="custom key table name",
                                     visible=False)
        self.table_help = Gtk.Label(xalign=0)
        self.table_help.add_css_class("dim-label")
        tbox = Gtk.Box(spacing=8)
        tbox.append(self.table_dd)
        tbox.append(self.table_entry)
        tbox.append(self.table_help)
        self.table_dd.set_selected(self.tables.index(b.table))
        self.table_dd.connect("notify::selected", self._on_table)
        self.table_entry.connect("changed", lambda *_: self._check())
        grid.attach(Gtk.Label(label="Key table", xalign=0), 0, row, 1, 1)
        grid.attach(tbox, 1, row, 1, 1)
        row += 1

        # Key
        kbox = Gtk.Box()
        kbox.add_css_class("linked")
        self.key_entry = Gtk.Entry(text=b.key, hexpand=True,
                                   placeholder_text="e.g. C-a, M-Left, |, F5, MouseDown1Pane")
        self.key_entry.add_css_class("monospace")
        self.key_entry.connect("changed", lambda *_: self._check())
        cap = Gtk.Button(label="Capture…")
        cap.set_tooltip_text("Press the key combination to bind")
        cap.connect("clicked", lambda *_: KeyCaptureDialog(
            self, self.key_entry.set_text, self.key_entry.get_text()).present())
        kbox.append(self.key_entry)
        kbox.append(cap)
        grid.attach(Gtk.Label(label="Key", xalign=0), 0, row, 1, 1)
        grid.attach(kbox, 1, row, 1, 1)
        row += 1

        self.conflict = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.conflict.add_css_class("warning")
        grid.attach(self.conflict, 1, row, 1, 1)
        row += 1

        # Command
        self.cmd_entry = Gtk.Entry(text=b.command, hexpand=True,
                                   placeholder_text='e.g. split-window -h -c "#{pane_current_path}"')
        self.cmd_entry.add_css_class("monospace")
        self.cmd_entry.connect("changed", lambda *_: self._check())
        grid.attach(Gtk.Label(label="Command", xalign=0), 0, row, 1, 1)
        grid.attach(self.cmd_entry, 1, row, 1, 1)
        row += 1

        helpers = Gtk.Box(spacing=8)
        helpers.append(self._presets_button())
        names = [c[0] for c in TMUX_COMMANDS]
        self.cmd_dd = Gtk.DropDown.new_from_strings(["Command reference…"] + names)
        self.cmd_dd.set_enable_search(True)
        self.cmd_dd.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        self.cmd_dd.connect("notify::selected", self._on_cmd_ref)
        helpers.append(self.cmd_dd)
        grid.attach(helpers, 1, row, 1, 1)
        row += 1
        self.usage = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.usage.add_css_class("dim-label")
        self.usage.add_css_class("monospace")
        grid.attach(self.usage, 1, row, 1, 1)
        row += 1

        # Flags
        self.repeat = Gtk.CheckButton(
            label="Repeatable (-r): can be pressed again within repeat-time "
                  "without the prefix",
            active=b.repeat)
        grid.attach(self.repeat, 1, row, 1, 1)
        row += 1
        self.note = Gtk.Entry(text=b.note, placeholder_text="shown by list-keys -N / prefix ?")
        grid.attach(Gtk.Label(label="Note (-N)", xalign=0), 0, row, 1, 1)
        grid.attach(self.note, 1, row, 1, 1)
        row += 1

        self.preview = Gtk.Label(xalign=0, wrap=True, selectable=True,
                                 margin_top=8)
        self.preview.add_css_class("monospace")
        grid.attach(Gtk.Label(label="Result", xalign=0, margin_top=8), 0, row, 1, 1)
        grid.attach(self.preview, 1, row, 1, 1)

        self.content.append(grid)
        self.repeat.connect("toggled", lambda *_: self._check())
        self.note.connect("changed", lambda *_: self._check())
        self._on_table()
        self.key_entry.grab_focus()

    def _presets_button(self):
        btn = Gtk.MenuButton(label="Common commands", always_show_arrow=True)
        pop = Gtk.Popover()
        scroll = Gtk.ScrolledWindow(min_content_height=360, min_content_width=380,
                                    propagate_natural_height=True)
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        for group, items in COMMAND_PRESETS:
            head = Gtk.Label(xalign=0, margin_top=8, margin_start=6)
            head.set_markup(f"<b>{group}</b>")
            r = Gtk.ListBoxRow(activatable=False, selectable=False)
            r.set_child(head)
            lb.append(r)
            for label, cmd in items:
                r = Gtk.ListBoxRow()
                r.cmd = cmd
                lab = Gtk.Label(label=label, xalign=0, margin_start=12,
                                tooltip_text=cmd)
                r.set_child(lab)
                lb.append(r)

        def activated(_lb, r):
            self.cmd_entry.set_text(r.cmd)
            pop.popdown()
        lb.connect("row-activated", activated)
        scroll.set_child(lb)
        pop.set_child(scroll)
        btn.set_popover(pop)
        return btn

    def _on_cmd_ref(self, dd, _pspec):
        i = dd.get_selected()
        if i <= 0:
            return
        name, alias, usage = TMUX_COMMANDS[i - 1]
        alias_s = f" ({alias})" if alias else ""
        self.usage.set_label(f"{name}{alias_s} {usage}")
        if not self.cmd_entry.get_text().strip():
            self.cmd_entry.set_text(name + " ")
            self.cmd_entry.set_position(-1)

    def _on_table(self, *_):
        sel = self.tables[self.table_dd.get_selected()]
        self.table_entry.set_visible(sel == "Other…")
        self.table_help.set_label(TABLE_HELP.get(sel, ""))
        self._check()

    def table(self) -> str:
        sel = self.tables[self.table_dd.get_selected()]
        return self.table_entry.get_text().strip() if sel == "Other…" else sel

    def current(self) -> Binding:
        return Binding(key=self.key_entry.get_text().strip(),
                       command=self.cmd_entry.get_text().strip(),
                       table=self.table(), repeat=self.repeat.get_active(),
                       note=self.note.get_text().strip())

    def _check(self):
        b = self.current()
        ok = bool(b.key and b.command and b.table)
        self.ok_button.set_sensitive(ok)
        self.preview.set_label(b.render() if ok else "")
        msgs = []
        for other in self.cfg.bindings:
            if other is not self.editing and other.table == b.table and other.key == b.key:
                msgs.append(f"⚠ Already bound in this config: {other.command}")
        d = default_binding(b.table, b.key)
        if d and b.key:
            msgs.append(f"ℹ Overrides tmux default: {d[4] or d[3]}")
        self.conflict.set_label("\n".join(msgs))
        self.conflict.set_visible(bool(msgs))

    def on_ok(self):
        self.callback(self.current())
        self.close()


class UnbindEditor(Dialog):
    def __init__(self, parent, callback, unbind: Unbind | None = None):
        super().__init__(parent, "Unbind Key", "Save")
        self.callback = callback
        u = unbind or Unbind("", "prefix")
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.tables = table_dropdown_strings([u.table])
        self.table_dd = Gtk.DropDown.new_from_strings(self.tables)
        self.table_dd.set_selected(self.tables.index(u.table))
        grid.attach(Gtk.Label(label="Key table", xalign=0), 0, 0, 1, 1)
        grid.attach(self.table_dd, 1, 0, 1, 1)
        self.all_check = Gtk.CheckButton(label="Remove every binding in this table (unbind -a)")
        grid.attach(self.all_check, 1, 1, 1, 1)
        kbox = Gtk.Box()
        kbox.add_css_class("linked")
        self.key_entry = Gtk.Entry(text=u.key, hexpand=True)
        self.key_entry.add_css_class("monospace")
        cap = Gtk.Button(icon_name="input-keyboard-symbolic", tooltip_text="Capture…")
        cap.connect("clicked", lambda *_: KeyCaptureDialog(
            self, self.key_entry.set_text, self.key_entry.get_text()).present())
        kbox.append(self.key_entry)
        kbox.append(cap)
        grid.attach(Gtk.Label(label="Key", xalign=0), 0, 2, 1, 1)
        grid.attach(kbox, 1, 2, 1, 1)
        self.info = Gtk.Label(xalign=0, wrap=True)
        self.info.add_css_class("dim-label")
        grid.attach(self.info, 1, 3, 1, 1)
        self.content.append(grid)
        self.all_check.set_active(unbind is not None and not u.key)
        self.all_check.connect("toggled", self._check)
        self.key_entry.connect("changed", self._check)
        self.table_dd.connect("notify::selected", self._check)
        self._check()
        self.set_default_size(460, -1)

    def _check(self, *_):
        all_keys = self.all_check.get_active()
        self.key_entry.set_sensitive(not all_keys)
        key = self.key_entry.get_text().strip()
        self.ok_button.set_sensitive(all_keys or bool(key))
        d = default_binding(self.tables[self.table_dd.get_selected()], key)
        self.info.set_label(f"Default binding: {d[4] or d[3]}" if d and not all_keys else "")

    def on_ok(self):
        table = self.tables[self.table_dd.get_selected()]
        key = "" if self.all_check.get_active() else self.key_entry.get_text().strip()
        self.callback(Unbind(key, table))
        self.close()


class DefaultsWindow(Gtk.Window):
    """Browse tmux's default bindings; override or unbind them."""

    def __init__(self, parent, page: "BindingsPage"):
        super().__init__(title="tmux Default Key Bindings", transient_for=parent,
                         destroy_with_parent=True, default_width=900,
                         default_height=600)
        self.page = page
        self.store = Gio.ListStore(item_type=Item)
        for row in DEFAULT_BINDINGS:
            self.store.append(Item(row))
        self.table_dd = Gtk.DropDown.new_from_strings([ALL_TABLES] + KEY_TABLES)
        self.table_dd.set_selected(1)
        self.table_dd.connect("notify::selected", lambda *_: self.filter.changed(
            Gtk.FilterChange.DIFFERENT))
        self.search = Gtk.SearchEntry(hexpand=True, placeholder_text="Search keys/commands")
        self.search.connect("search-changed", lambda *_: self.filter.changed(
            Gtk.FilterChange.DIFFERENT))
        self.filter = Gtk.CustomFilter.new(self._match)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        view, self.selection = make_column_view(filtered, [
            ("Table", lambda r: r[0], False, None),
            ("Key", lambda r: r[1], False, "monospace"),
            ("-r", lambda r: "✓" if r[2] else "", False, None),
            ("Description", lambda r: r[4], True, None),
            ("Command", lambda r: r[3], True, "monospace"),
        ], on_activate=lambda *_: self._override())

        top = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=8,
                      margin_end=8)
        override = Gtk.Button(label="Override…")
        override.set_tooltip_text("Create a custom binding for this key, starting from the default")
        override.connect("clicked", lambda *_: self._override())
        unbind = Gtk.Button(label="Unbind")
        unbind.set_tooltip_text("Remove this default binding in your config")
        unbind.connect("clicked", lambda *_: self._unbind())
        for w in (self.table_dd, self.search, override, unbind):
            top.append(w)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(view)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(top)
        box.append(scroll)
        self.set_child(box)

    def _match(self, item):
        r = item.obj
        sel = self.table_dd.get_selected()
        if sel > 0 and r[0] != KEY_TABLES[sel - 1]:
            return False
        q = self.search.get_text().lower()
        return not q or q in r[1].lower() or q in r[3].lower() or q in r[4].lower()

    def _selected(self):
        item = self.selection.get_selected_item()
        return item.obj if item else None

    def _override(self):
        r = self._selected()
        if r:
            self.page.new_binding(Binding(key=r[1], command=r[3], table=r[0],
                                          repeat=r[2], note=r[4]), parent=self)

    def _unbind(self):
        r = self._selected()
        if r:
            self.page.add_unbind(Unbind(r[1], r[0]))


class BindingsPage(Gtk.Box):
    def __init__(self, cfg: Config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         margin_top=12, margin_bottom=12, margin_start=12,
                         margin_end=12)
        self.cfg = cfg
        self.on_change = on_change

        # --- custom bindings ---
        head = Gtk.Box(spacing=6)
        title = Gtk.Label(xalign=0, hexpand=True)
        title.set_markup("<b>Key bindings</b>")
        head.append(title)
        self.table_filter = Gtk.DropDown.new_from_strings([ALL_TABLES] + KEY_TABLES)
        self.table_filter.connect("notify::selected", lambda *_: self.bind_filter.changed(
            Gtk.FilterChange.DIFFERENT))
        head.append(self.table_filter)
        for icon, tip, cb in [
            ("list-add-symbolic", "Add binding", lambda *_: self.new_binding()),
            ("document-edit-symbolic", "Edit binding", lambda *_: self.edit_selected()),
            ("edit-copy-symbolic", "Duplicate binding", lambda *_: self.duplicate_selected()),
            ("list-remove-symbolic", "Remove binding", lambda *_: self.remove_selected()),
        ]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", cb)
            head.append(b)
        defaults = Gtk.Button(label="tmux defaults…")
        defaults.set_tooltip_text("Browse the default bindings to override or unbind them")
        defaults.connect("clicked", lambda *_: DefaultsWindow(self.get_root(), self).present())
        head.append(defaults)
        self.append(head)

        self.bind_store = Gio.ListStore(item_type=Item)
        self.bind_filter = Gtk.CustomFilter.new(self._match_table)
        filtered = Gtk.FilterListModel(model=self.bind_store, filter=self.bind_filter)
        self.bind_view, self.bind_sel = make_column_view(filtered, [
            ("Table", lambda b: b.table, False, None),
            ("Key", lambda b: b.key, False, "monospace"),
            ("-r", lambda b: "✓" if b.repeat else "", False, None),
            ("Command", lambda b: b.command, True, "monospace"),
            ("Note", lambda b: b.note, False, None),
        ], on_activate=lambda *_: self.edit_selected())
        self.empty_label = Gtk.Label(
            label="No custom bindings yet. Click + to add one, or start from "
                  "“tmux defaults…”.")
        self.empty_label.add_css_class("dim-label")
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=200)
        scroll.set_child(self.bind_view)
        frame = Gtk.Frame()
        frame.set_child(scroll)
        self.append(frame)
        self.append(self.empty_label)

        # --- unbinds ---
        head2 = Gtk.Box(spacing=6, margin_top=12)
        t2 = Gtk.Label(xalign=0, hexpand=True)
        t2.set_markup("<b>Unbound keys</b>  <small>(written before the bindings)</small>")
        head2.append(t2)
        for icon, tip, cb in [
            ("list-add-symbolic", "Unbind a key", lambda *_: UnbindEditor(
                self.get_root(), self.add_unbind).present()),
            ("list-remove-symbolic", "Remove", lambda *_: self.remove_unbind()),
        ]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", cb)
            head2.append(b)
        self.append(head2)
        self.unbind_store = Gio.ListStore(item_type=Item)
        self.unbind_view, self.unbind_sel = make_column_view(self.unbind_store, [
            ("Table", lambda u: u.table, False, None),
            ("Key", lambda u: u.key or "(all keys)", True, "monospace"),
            ("Line", lambda u: u.render(), True, "monospace"),
        ])
        scroll2 = Gtk.ScrolledWindow(min_content_height=110, vexpand=False)
        scroll2.set_child(self.unbind_view)
        frame2 = Gtk.Frame()
        frame2.set_child(scroll2)
        self.append(frame2)
        self.refresh()

    def _match_table(self, item):
        sel = self.table_filter.get_selected()
        return sel == 0 or item.obj.table == KEY_TABLES[sel - 1]

    def refresh(self):
        self.bind_store.remove_all()
        for b in self.cfg.bindings:
            self.bind_store.append(Item(b))
        self.unbind_store.remove_all()
        for u in self.cfg.unbinds:
            self.unbind_store.append(Item(u))
        self.empty_label.set_visible(not self.cfg.bindings)

    def _changed(self):
        self.refresh()
        self.on_change()

    def _selected_binding(self):
        item = self.bind_sel.get_selected_item()
        return item.obj if item else None

    def new_binding(self, template: Binding | None = None, parent=None):
        def done(b):
            self.cfg.bindings.append(b)
            self._changed()
        BindingEditor(parent or self.get_root(), self.cfg, template, done).present()

    def edit_selected(self):
        b = self._selected_binding()
        if not b:
            return

        def done(new):
            idx = self.cfg.bindings.index(b)
            self.cfg.bindings[idx] = new
            self._changed()
        BindingEditor(self.get_root(), self.cfg, b, done, editing=b).present()

    def duplicate_selected(self):
        b = self._selected_binding()
        if b:
            self.new_binding(Binding(key="", command=b.command, table=b.table,
                                     repeat=b.repeat, note=b.note))

    def remove_selected(self):
        b = self._selected_binding()
        if b:
            self.cfg.bindings.remove(b)
            self._changed()

    def add_unbind(self, u: Unbind):
        if not any(x.table == u.table and x.key == u.key for x in self.cfg.unbinds):
            self.cfg.unbinds.append(u)
            self._changed()

    def remove_unbind(self):
        item = self.unbind_sel.get_selected_item()
        if item:
            self.cfg.unbinds.remove(item.obj)
            self._changed()
