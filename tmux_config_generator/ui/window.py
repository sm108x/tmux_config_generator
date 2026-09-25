"""Main application window."""

from __future__ import annotations

import os
from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk

from .. import __version__
from ..config import Binding, Config, Unbind, generate, parse
from ..options import CATEGORIES, OPTIONS_BY_NAME
from ..presets import QUICK_PRESETS
from ..validate import validate
from .bindings_page import BindingsPage
from .option_page import OptionPage

CSS = b"""
.option-included { background-color: alpha(@accent_bg_color, 0.08); }
.warning { color: #c07000; }
.preview-view { font-family: monospace; }
"""


def default_config_path() -> Path:
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    if (xdg / "tmux" / "tmux.conf").exists():
        return xdg / "tmux" / "tmux.conf"
    return Path.home() / ".tmux.conf"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, default_width=1400, default_height=850)
        self.cfg = Config()
        self.path: Path | None = None
        self.dirty = False
        self._preview_pending = False

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS, len(CSS))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._build_header()
        self._build_actions(app)

        # Left: notebook of option categories + bindings + custom.
        self.notebook = Gtk.Notebook(scrollable=True, hexpand=True,
                                     tab_pos=Gtk.PositionType.LEFT)
        self.pages: list[OptionPage] = []
        for cat, title in CATEGORIES:
            page = OptionPage(cat, self.cfg, self.changed)
            self.pages.append(page)
            self.notebook.append_page(page, Gtk.Label(label=title, xalign=0))
        self.bindings = BindingsPage(self.cfg, self.changed)
        self.notebook.append_page(self.bindings, Gtk.Label(label="Key Bindings", xalign=0))
        self.notebook.append_page(self._build_custom_page(), Gtk.Label(label="Custom", xalign=0))

        # Right: live preview.
        self.preview = Gtk.TextView(editable=False, monospace=True,
                                    cursor_visible=False, left_margin=8,
                                    top_margin=8, right_margin=8,
                                    wrap_mode=Gtk.WrapMode.NONE)
        pscroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        pscroll.set_child(self.preview)
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        phead = Gtk.Box(spacing=6, margin_top=6, margin_bottom=6,
                        margin_start=8, margin_end=8)
        plabel = Gtk.Label(xalign=0, hexpand=True)
        plabel.set_markup("<b>Preview</b>")
        self.count_label = Gtk.Label()
        self.count_label.add_css_class("dim-label")
        phead.append(plabel)
        phead.append(self.count_label)
        for icon, tip, action in [("edit-copy-symbolic", "Copy to clipboard", "win.copy"),
                                  ("emblem-ok-symbolic", "Check with tmux", "win.validate")]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, action_name=action)
            b.add_css_class("flat")
            phead.append(b)
        pbox.append(phead)
        pbox.append(Gtk.Separator())
        pbox.append(pscroll)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,
                          wide_handle=True, position=880,
                          resize_start_child=True, shrink_start_child=False,
                          resize_end_child=True, shrink_end_child=False)
        paned.set_start_child(self.notebook)
        paned.set_end_child(pbox)
        self.set_child(paned)
        self.connect("close-request", self._on_close_request)
        self.update_preview()
        self.update_title()

    # -- construction -----------------------------------------------------

    def _build_header(self):
        header = Gtk.HeaderBar()
        self.set_titlebar(header)
        open_btn = Gtk.Button(label="Open", action_name="win.open",
                              tooltip_text="Import an existing tmux.conf (Ctrl+O)")
        header.pack_start(open_btn)
        save_btn = Gtk.Button(label="Save", action_name="win.save",
                              tooltip_text="Save (Ctrl+S)")
        save_btn.add_css_class("suggested-action")
        header.pack_start(save_btn)

        menu = Gio.Menu()
        file_section = Gio.Menu()
        file_section.append("New (reset everything)", "win.new")
        file_section.append("Save As…", "win.save-as")
        file_section.append("Copy to Clipboard", "win.copy")
        file_section.append("Check with tmux", "win.validate")
        menu.append_section(None, file_section)
        presets = Gio.Menu()
        for i, (label, *_rest) in enumerate(QUICK_PRESETS):
            presets.append(label, f"win.preset({i})")
        menu.append_submenu("Apply Preset", presets)
        about = Gio.Menu()
        about.append("About", "win.about")
        menu.append_section(None, about)
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                  tooltip_text="Menu")
        header.pack_end(menu_btn)

        self.search = Gtk.SearchEntry(placeholder_text="Filter options",
                                      width_chars=24)
        self.search.connect("search-changed", self._on_search)
        header.pack_end(self.search)

    def _build_actions(self, app):
        def add(name, cb, accel=None, param=None):
            action = Gio.SimpleAction.new(name, param)
            action.connect("activate", cb)
            self.add_action(action)
            if accel:
                app.set_accels_for_action(f"win.{name}", [accel])

        add("open", lambda *_: self.open_file(), "<Primary>o")
        add("save", lambda *_: self.save(), "<Primary>s")
        add("save-as", lambda *_: self.save_as(), "<Primary><Shift>s")
        add("new", lambda *_: self.confirm_discard(self.reset_all), "<Primary>n")
        add("copy", lambda *_: self.copy_clipboard(), "<Primary><Shift>c")
        add("validate", lambda *_: self.run_validate(), "<Primary>r")
        add("about", lambda *_: self.show_about())
        add("preset", lambda _a, p: self.apply_preset(p.get_int32()),
            param=GLib.VariantType.new("i"))
        add("find", lambda *_: self.search.grab_focus(), "<Primary>f")

    def _build_custom_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=12, margin_bottom=12, margin_start=12,
                      margin_end=12)
        hint = Gtk.Label(xalign=0, wrap=True)
        hint.set_markup(
            "<b>Custom configuration</b>\n"
            "Anything else to append verbatim: hooks (<tt>set-hook</tt>), "
            "<tt>if-shell</tt>, <tt>source-file</tt>, plugin lines "
            "(<tt>set -g @plugin …</tt>, <tt>run '~/.tmux/plugins/tpm/tpm'</tt>) "
            "and so on. Lines from an imported file that the editor does not "
            "understand also end up here.")
        box.append(hint)
        self.custom = Gtk.TextView(monospace=True, top_margin=6, left_margin=6,
                                   bottom_margin=6)
        self.custom.get_buffer().connect("changed", self._on_custom)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.custom)
        frame = Gtk.Frame()
        frame.set_child(scroll)
        box.append(frame)
        return box

    # -- state --------------------------------------------------------------

    def _on_custom(self, buf):
        if getattr(self, "_loading", False):
            return
        self.cfg.extra = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self.changed()

    def _on_search(self, entry):
        query = entry.get_text()
        first_hit = None
        for i, page in enumerate(self.pages):
            n = page.filter(query)
            title = CATEGORIES[i][1]
            label = f"{title} ({n})" if query.strip() else title
            self.notebook.get_tab_label(page).set_label(label)
            if n and first_hit is None:
                first_hit = i
        current = self.notebook.get_current_page()
        if query.strip() and first_hit is not None and (
                current >= len(self.pages) or not self.pages[current].filter(query)):
            self.notebook.set_current_page(first_hit)

    def changed(self):
        self.dirty = True
        self.update_title()
        if not self._preview_pending:
            self._preview_pending = True
            GLib.idle_add(self.update_preview)

    def text(self) -> str:
        return generate(self.cfg)

    def update_preview(self):
        self._preview_pending = False
        self.preview.get_buffer().set_text(self.text())
        for page in self.pages:
            page.refresh_preview()
        n = len(self.cfg.values)
        self.count_label.set_label(
            f"{n} option{'s' if n != 1 else ''}, {len(self.cfg.bindings)} "
            f"binding{'s' if len(self.cfg.bindings) != 1 else ''}")
        return False

    def update_title(self):
        name = self.path.name if self.path else "Untitled"
        self.set_title(f"{'• ' if self.dirty else ''}{name} — tmux Config Generator")

    def load_config(self, cfg: Config):
        # Mutate in place: pages hold a reference to self.cfg.
        self.cfg.values = cfg.values
        self.cfg.list_append = cfg.list_append
        self.cfg.bindings = cfg.bindings
        self.cfg.unbinds = cfg.unbinds
        self.cfg.extra = cfg.extra
        for page in self.pages:
            page.refresh()
        self.bindings.refresh()
        self._loading = True
        self.custom.get_buffer().set_text(cfg.extra)
        self._loading = False
        self.update_preview()

    def reset_all(self):
        self.path = None
        self.load_config(Config())
        self.dirty = False
        self.update_title()

    def apply_preset(self, index: int):
        label, _desc, values, bindings, unbinds = QUICK_PRESETS[index]
        for name, value in values.items():
            self.cfg.values[name] = list(value) if isinstance(value, list) else value
            if OPTIONS_BY_NAME[name].type == "list":
                self.cfg.list_append.add(name)
        for table, key, repeat, command in bindings:
            self.cfg.bindings = [b for b in self.cfg.bindings
                                 if not (b.table == table and b.key == key)]
            self.cfg.bindings.append(Binding(key=key, command=command,
                                             table=table, repeat=repeat))
        for table, key in unbinds:
            if not any(u.table == table and u.key == key for u in self.cfg.unbinds):
                self.cfg.unbinds.append(Unbind(key, table))
        for page in self.pages:
            page.refresh()
        self.bindings.refresh()
        self.changed()
        self.toast(f"Applied preset “{label}”.")

    # -- file handling ------------------------------------------------------

    def open_file(self):
        def do_open():
            dialog = Gtk.FileDialog(title="Open tmux configuration")
            start = default_config_path()
            if start.exists():
                dialog.set_initial_file(Gio.File.new_for_path(str(start)))
            dialog.open(self, None, self._on_open_done)
        self.confirm_discard(do_open)

    def _on_open_done(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        self.load_path(Path(gfile.get_path()))

    def load_path(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self.error("Could not open file", str(e))
            return
        cfg = parse(text)
        self.load_config(cfg)
        self.path = path
        self.dirty = False
        self.update_title()
        extra_lines = len([line for line in cfg.extra.splitlines()
                           if line.strip() and not line.lstrip().startswith("#")])
        msg = (f"Imported {len(cfg.values)} options and {len(cfg.bindings)} bindings.")
        if extra_lines:
            msg += f" {extra_lines} other line(s) were kept on the Custom tab."
        self.toast(msg)

    def save(self):
        if self.path:
            self._write(self.path)
        else:
            self.save_as()

    def save_as(self):
        dialog = Gtk.FileDialog(title="Save tmux configuration")
        target = self.path or default_config_path()
        if target.exists():
            dialog.set_initial_file(Gio.File.new_for_path(str(target)))
        else:
            dialog.set_initial_folder(Gio.File.new_for_path(str(target.parent)))
            dialog.set_initial_name(target.name)
        dialog.save(self, None, self._on_save_done)

    def _on_save_done(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        self._write(Path(gfile.get_path()))

    def _write(self, path: Path):
        try:
            if path.exists() and not getattr(self, "_backed_up", {}).get(path):
                backup = path.with_name(path.name + ".bak")
                backup.write_bytes(path.read_bytes())
                self._backed_up = {**getattr(self, "_backed_up", {}), path: True}
            path.write_text(self.text(), encoding="utf-8")
        except OSError as e:
            self.error("Could not save file", str(e))
            return
        self.path = path
        self.dirty = False
        self.update_title()
        self.toast(f"Saved {path}. Reload in tmux with: tmux source-file {path}")

    def copy_clipboard(self):
        self.get_clipboard().set_content(Gdk.ContentProvider.new_for_bytes(
            "text/plain;charset=utf-8", GLib.Bytes.new(self.text().encode())))
        self.toast("Copied configuration to the clipboard.")

    def run_validate(self):
        # Custom lines may run shell commands, so they are only syntax-checked.
        safe = generate(Config(self.cfg.values, self.cfg.list_append,
                               self.cfg.unbinds, self.cfg.bindings))
        ok, msg = validate(self.text(), safe)
        self.info("Configuration is valid" if ok else "tmux reported a problem", msg)

    # -- dialogs --------------------------------------------------------------

    def confirm_discard(self, then):
        if not self.dirty:
            then()
            return
        dialog = Gtk.AlertDialog(message="Discard unsaved changes?",
                                 detail="Your current configuration has not been saved.",
                                 buttons=["Cancel", "Discard"], cancel_button=0,
                                 default_button=0)

        def done(d, res):
            try:
                if d.choose_finish(res) == 1:
                    then()
            except GLib.Error:
                pass
        dialog.choose(self, None, done)

    def _on_close_request(self, _win):
        if not self.dirty:
            return False

        def close():
            self.dirty = False
            self.close()
        self.confirm_discard(close)
        return True

    def error(self, message, detail):
        Gtk.AlertDialog(message=message, detail=detail).show(self)

    def info(self, message, detail):
        Gtk.AlertDialog(message=message, detail=detail).show(self)

    def toast(self, text: str):
        """Show a transient message in the title bar's subtitle area."""
        self.set_title(text)
        GLib.timeout_add_seconds(4, lambda: (self.update_title(), False)[1])

    def show_about(self):
        Gtk.AboutDialog(transient_for=self, modal=True,
                        program_name="tmux Config Generator",
                        comments="Build a tmux.conf with a GUI: every option, "
                                 "grouped by category, plus a key binding editor.",
                        version=__version__,
                        copyright="Copyright © 2026 Stephen Martina",
                        license_type=Gtk.License.GPL_3_0,
                        logo_icon_name="utilities-terminal").present()
