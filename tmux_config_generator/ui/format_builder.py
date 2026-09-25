"""Format builder: compose tmux formats (#{...}, #[...], %H...) with help."""

from __future__ import annotations

import re
import time

from gi.repository import GLib, Gtk, Pango

from ..format_vars import FORMAT_VARIABLES
from ..presets import FORMAT_EXAMPLES
from ..render.format import _match_brace, expand_time, split_styles
from ..render.screen import (build_border_screen, build_status_screen,
                             build_text_screen, sample_context, status_lines)
from .colour import ColourButton
from .dialogs import Dialog
from .preview import ScreenStrip

# Options that take formats, and how the builder previews them.
FORMAT_OPTIONS = {
    "status-left": "status", "status-right": "status",
    "window-status-format": "status", "window-status-current-format": "status",
    "window-status-separator": "status", "status-format": "status",
    "pane-border-format": "border",
    "automatic-rename-format": "text", "set-titles-string": "text",
    "remain-on-exit-format": "text",
}

ALIASES = [
    ("#S", "session_name"), ("#I", "window_index"), ("#W", "window_name"),
    ("#F", "window_flags"), ("#P", "pane_index"), ("#T", "pane_title"),
    ("#D", "pane_id"), ("#H", "host"), ("#h", "host_short"),
]

VAR_GROUPS = [
    ("Session", ("session_",)), ("Window", ("window_", "active_window")),
    ("Pane", ("pane_",)), ("Client", ("client_",)),
    ("Server & host", ("host", "pid", "version", "start_time", "socket_path",
                       "server_", "config_files", "uid", "user")),
    ("Other", ("",)),
]

# (label, template, description). Upper-case words are placeholders; the
# first one is selected after inserting so you can type over it.
LOGIC = [
    ("If / else", "#{?CONDITION,IF_TRUE,IF_FALSE}",
     "CONDITION is a variable name (true if non-empty and not 0) or a nested #{...}"),
    ("If prefix pressed", "#{?client_prefix,TEXT,}", "Show TEXT while the prefix key is held"),
    ("If pane zoomed", "#{?window_zoomed_flag,TEXT,}", "Show TEXT when the window is zoomed"),
    ("If in copy mode", "#{?pane_in_mode,TEXT,}", "Show TEXT when the pane is in a mode"),
    ("Equal", "#{==:A,B}", "1 if A equals B"),
    ("Not equal", "#{!=:A,B}", "1 if A differs from B"),
    ("And", "#{&&:A,B}", "1 if both are true"),
    ("Or", "#{||:A,B}", "1 if either is true"),
    ("Not", "#{!:A}", "1 if A is false"),
    ("Pattern match", "#{m:PATTERN,STRING}", "1 if STRING matches the glob PATTERN (m/r: for regex)"),
    ("Truncate", "#{=20:VARIABLE}", "First 20 characters (use -20 for the last 20)"),
    ("Truncate with …", "#{=/20/…:VARIABLE}", "Truncate to 20 characters and add … if cut"),
    ("Pad", "#{p10:VARIABLE}", "Pad to 10 characters (p-10 pads on the right)"),
    ("Basename", "#{b:pane_current_path}", "Last component of a path"),
    ("Dirname", "#{d:pane_current_path}", "Directory part of a path"),
    ("Substitute", "#{s/FIND/REPLACE/:VARIABLE}", "Regular expression substitution"),
    ("Length", "#{n:VARIABLE}", "Length of the value"),
    ("Time value", "#{t:window_activity}", "Format a time variable as a date"),
    ("Expand option", "#{E:OPTION}", "Insert another option's value, expanded"),
    ("Expand option + time", "#{T:OPTION}", "As E:, also expanding %H:%M etc."),
    ("Literal", "#{l:TEXT}", "TEXT without expansion"),
    ("Each window", "#{W:#I:#W ,[#I:#W] }", "Loop over windows: normal format, current-window format"),
    ("Each pane", "#{P:#P }", "Loop over panes in the window"),
    ("Shell command", "#(COMMAND)", "Output of a shell command (refreshed every status-interval)"),
    ("Literal #", "##", "A # character"),
    ("Literal comma", "#,", "A comma inside #{?...} branches"),
]

STRFTIME = [
    ("%H", "hour (00-23)"), ("%I", "hour (01-12)"), ("%M", "minute"),
    ("%S", "second"), ("%p", "AM/PM"), ("%a", "weekday, short"),
    ("%A", "weekday"), ("%d", "day of month"), ("%e", "day, space padded"),
    ("%b", "month, short"), ("%B", "month"), ("%m", "month (01-12)"),
    ("%y", "year, 2 digits"), ("%Y", "year"), ("%j", "day of year"),
    ("%V", "ISO week number"), ("%Z", "time zone"), ("%R", "same as %H:%M"),
    ("%T", "same as %H:%M:%S"), ("%F", "same as %Y-%m-%d"), ("%%", "a % sign"),
]


def _group_of(name: str) -> str:
    for group, prefixes in VAR_GROUPS:
        if any(name.startswith(p) for p in prefixes if p):
            return group
    return "Other"


def _check(text: str) -> str | None:
    """Return a warning for obviously broken formats."""
    i = 0
    while True:
        i = text.find("#{", i)
        if i < 0:
            break
        if _match_brace(text, i + 1) < 0:
            return "Unclosed #{ … }"
        i += 2
    depth = 0
    for m in re.finditer(r"#\[|\]", text):
        depth += 1 if m.group() == "#[" else (-1 if depth else 0)
    if depth:
        return "Unclosed #[ … ]"
    return None


def _scroll(child) -> Gtk.ScrolledWindow:
    s = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
    s.set_child(child)
    return s


class FormatBuilder(Dialog):
    """Edit a format with insertable parts and a live preview."""

    def __init__(self, parent, option: str, text: str, values_fn, callback,
                 status_line: int = 0):
        super().__init__(parent, f"Format Builder — {option}", "Apply")
        self.option = option
        self.values_fn = values_fn
        self.callback = callback
        self.status_line = status_line
        self.set_default_size(900, 720)

        # Editor
        head = Gtk.Label(xalign=0)
        which = f" line {status_line}" if option == "status-format" else ""
        head.set_markup(f"<b>{GLib.markup_escape_text(option)}</b>{which}  "
                        "<small>click items below to insert them at the cursor; "
                        "select text first to wrap it in a style</small>")
        self.content.append(head)
        self.view = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.CHAR,
                                 top_margin=6, bottom_margin=6, left_margin=6,
                                 right_margin=6, accepts_tab=False)
        self.buf = self.view.get_buffer()
        self.buf.set_text(text)
        self.buf.connect("changed", lambda *_: self._update())
        frame = Gtk.Frame()
        sw = Gtk.ScrolledWindow(min_content_height=70, max_content_height=140,
                                propagate_natural_height=True)
        sw.set_child(self.view)
        frame.set_child(sw)
        self.content.append(frame)

        # Preview
        kind = FORMAT_OPTIONS.get(option, "text")
        rows = status_lines(self.values_fn()) if kind == "status" else 1
        self.strip = ScreenStrip(self._screen, rows=rows)
        pframe = Gtk.Frame()
        pframe.set_child(self.strip)
        self.content.append(pframe)
        self.expanded = Gtk.Label(xalign=0, selectable=True, wrap=True,
                                  wrap_mode=Pango.WrapMode.CHAR)
        self.expanded.add_css_class("monospace")
        self.expanded.add_css_class("dim-label")
        self.content.append(self.expanded)
        self.warning = Gtk.Label(xalign=0, visible=False)
        self.warning.add_css_class("warning")
        self.content.append(self.warning)

        # Palettes
        nb = Gtk.Notebook(vexpand=True)
        nb.append_page(self._variables_page(), Gtk.Label(label="Variables"))
        nb.append_page(self._styles_page(), Gtk.Label(label="Styles & colours"))
        nb.append_page(self._logic_page(), Gtk.Label(label="Conditions & modifiers"))
        nb.append_page(self._time_page(), Gtk.Label(label="Date & time"))
        if option in FORMAT_EXAMPLES:
            nb.append_page(self._examples_page(), Gtk.Label(label="Examples"))
        self.content.append(nb)
        self._update()
        self.view.grab_focus()

    # -- editing helpers ----------------------------------------------------

    def text(self) -> str:
        t = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False)
        return t.replace("\n", "")

    def insert(self, text: str):
        """Insert at the cursor (replacing any selection); select a placeholder."""
        self.buf.begin_user_action()
        self.buf.delete_selection(True, True)
        mark = self.buf.create_mark(None, self.buf.get_iter_at_mark(self.buf.get_insert()), True)
        self.buf.insert_at_cursor(text)
        self.buf.end_user_action()
        m = re.search(r"\b[A-Z][A-Z_]{2,}\b", text)
        if m:
            start = self.buf.get_iter_at_mark(mark)
            start.forward_chars(m.start())
            end = start.copy()
            end.forward_chars(m.end() - m.start())
            self.buf.select_range(start, end)
        self.buf.delete_mark(mark)
        self.view.grab_focus()

    def wrap(self, before: str, after: str = "#[default]"):
        """Wrap the selection in a style, or insert the opening tag."""
        bounds = self.buf.get_selection_bounds()
        if bounds:
            start, end = bounds
            sel = self.buf.get_text(start, end, False)
            self.buf.begin_user_action()
            self.buf.delete(start, end)
            self.buf.insert_at_cursor(before + sel + after)
            self.buf.end_user_action()
            self.view.grab_focus()
        else:
            self.insert(before)

    # -- preview ------------------------------------------------------------

    def _values(self):
        values = dict(self.values_fn())
        text = self.text()
        if self.option == "status-format":
            lines = list(values.get("status-format") or [])
            while len(lines) <= self.status_line:
                lines.append("")
            lines[self.status_line] = text
            values["status-format"] = lines
            want = self.status_line + 1
            if status_lines(values) < want:
                values["status"] = str(want)
        else:
            values[self.option] = text
        return values

    def _screen(self, cols):
        kind = FORMAT_OPTIONS.get(self.option, "text")
        values = self._values()
        if kind == "status":
            return build_status_screen(values, cols)
        if kind == "border":
            return build_border_screen(values, cols)
        return build_text_screen(values, self.text(), cols)

    def _update(self):
        ctx = sample_context(self._values())
        try:
            plain = "".join(t for t, s in split_styles(expand_time(self.text(), ctx))
                            if s is None)
        except Exception as e:  # keep the dialog usable whatever is typed
            plain = f"(error: {e})"
        self.expanded.set_label(f"Expands to: {plain!r}")
        warn = _check(self.text())
        self.warning.set_label(f"⚠ {warn}" if warn else "")
        self.warning.set_visible(bool(warn))
        self.strip.queue_draw()

    def on_ok(self):
        self.callback(self.text())
        self.close()

    # -- palettes -----------------------------------------------------------

    def _variables_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=6, margin_start=6, margin_end=6, margin_bottom=6)
        search = Gtk.SearchEntry(placeholder_text="Search variables")
        box.append(search)
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        lb.add_css_class("boxed-list")
        ctx = sample_context(self.values_fn())

        def header(title):
            r = Gtk.ListBoxRow(activatable=False, selectable=False)
            lab = Gtk.Label(xalign=0, margin_top=6, margin_start=6)
            lab.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
            r.set_child(lab)
            r.search = None
            lb.append(r)

        def row(insert, title, desc, sample):
            r = Gtk.ListBoxRow()
            r.insert_text = insert
            r.search = f"{title} {desc}".lower()
            h = Gtk.Box(spacing=12, margin_top=3, margin_bottom=3, margin_start=6,
                        margin_end=6)
            t = Gtk.Label(label=title, xalign=0, width_chars=26)
            t.add_css_class("monospace")
            d = Gtk.Label(label=desc, xalign=0, hexpand=True, wrap=True)
            d.add_css_class("dim-label")
            h.append(t)
            h.append(d)
            if sample:
                sm = Gtk.Label(label=sample[:24], xalign=1)
                sm.add_css_class("monospace")
                sm.add_css_class("caption")
                sm.set_tooltip_text(f"Value in the sample session: {sample}")
                h.append(sm)
            r.set_child(h)
            lb.append(r)

        header("Short aliases")
        for alias, name in ALIASES:
            row(alias, f"{alias}  = #{{{name}}}", "", ctx.lookup(name))
        by_group = {}
        for name, alias, desc in FORMAT_VARIABLES:
            by_group.setdefault(_group_of(name), []).append((name, alias, desc))
        for group, _p in VAR_GROUPS:
            if group not in by_group:
                continue
            header(group)
            for name, alias, desc in by_group[group]:
                row(f"#{{{name}}}", name + (f" ({alias})" if alias else ""), desc,
                    ctx.lookup(name))

        query = {"q": ""}
        lb.set_filter_func(lambda r: r.search is None and not query["q"]
                           or r.search is not None and query["q"] in r.search)

        def changed(e):
            query["q"] = e.get_text().strip().lower()
            lb.invalidate_filter()
        search.connect("search-changed", changed)
        lb.connect("row-activated", lambda _lb, r: self.insert(r.insert_text))
        box.append(_scroll(lb))
        return box

    def _styles_page(self):
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin_top=10,
                        margin_start=10, margin_end=10, margin_bottom=10)
        r = 0

        def label(text):
            lab = Gtk.Label(label=text, xalign=0)
            return lab

        for key, text in (("fg", "Text colour"), ("bg", "Background"),
                          ("fill", "Fill colour (whole line)")):
            btn = ColourButton(lambda v, k=key: self.wrap(f"#[{k}={v}]"),
                               tooltip=f"Insert #[{key}=…]")
            grid.attach(label(text), 0, r, 1, 1)
            grid.attach(btn, 1, r, 1, 1)
            hint = Gtk.Label(label=f"inserts #[{key}=colour]", xalign=0)
            hint.add_css_class("dim-label")
            grid.attach(hint, 2, r, 1, 1)
            r += 1

        grid.attach(label("Attributes"), 0, r, 1, 1)
        attrs = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                            max_children_per_line=6, min_children_per_line=3,
                            hexpand=True)
        for attr in ("bold", "dim", "italics", "underscore", "reverse", "blink",
                     "strikethrough", "overline", "double-underscore",
                     "curly-underscore"):
            b = Gtk.Button(label=attr, tooltip_text=f"#[{attr}] … #[no{attr}]")
            b.connect("clicked", lambda _b, a=attr: self.wrap(f"#[{a}]", f"#[no{a}]"))
            attrs.append(b)
        grid.attach(attrs, 1, r, 2, 1)
        r += 1

        grid.attach(label("Alignment"), 0, r, 1, 1)
        al = Gtk.Box(spacing=6)
        for a in ("left", "centre", "right", "absolute-centre"):
            b = Gtk.Button(label=a, tooltip_text=f"#[align={a}] (status-format)")
            b.connect("clicked", lambda _b, a=a: self.insert(f"#[align={a}]"))
            al.append(b)
        grid.attach(al, 1, r, 2, 1)
        r += 1

        grid.attach(label("Reset"), 0, r, 1, 1)
        rs = Gtk.Box(spacing=6)
        for text, tag, tip in [("default", "#[default]", "Back to the option's base style"),
                               ("none", "#[none]", "Clear all attributes"),
                               ("push-default", "#[push-default]", "Make the current style the default"),
                               ("pop-default", "#[pop-default]", "Restore the previous default")]:
            b = Gtk.Button(label=text, tooltip_text=tip)
            b.connect("clicked", lambda _b, t=tag: self.insert(t))
            rs.append(b)
        grid.attach(rs, 1, r, 2, 1)
        return _scroll(grid)

    def _template_list(self, items, on_activate):
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, margin_top=6,
                         margin_start=6, margin_end=6, margin_bottom=6)
        lb.add_css_class("boxed-list")
        for title, template, desc in items:
            r = Gtk.ListBoxRow()
            r.payload = template
            h = Gtk.Box(spacing=12, margin_top=3, margin_bottom=3, margin_start=6,
                        margin_end=6)
            t = Gtk.Label(label=title, xalign=0, width_chars=22)
            code = Gtk.Label(label=template, xalign=0, width_chars=30,
                             ellipsize=Pango.EllipsizeMode.END, max_width_chars=48)
            code.add_css_class("monospace")
            d = Gtk.Label(label=desc, xalign=0, hexpand=True, wrap=True)
            d.add_css_class("dim-label")
            for w in (t, code, d):
                h.append(w)
            r.set_child(h)
            r.set_tooltip_text(template)
            lb.append(r)
        lb.connect("row-activated", lambda _lb, r: on_activate(r.payload))
        return _scroll(lb)

    def _logic_page(self):
        return self._template_list(LOGIC, self.insert)

    def _time_page(self):
        now = time.localtime()
        items = [(code, code, f"{meaning} — now: {time.strftime(code, now)}")
                 for code, meaning in STRFTIME]
        return self._template_list(items, self.insert)

    def _examples_page(self):
        items = [(label, fmt, "replaces the whole format")
                 for label, fmt in FORMAT_EXAMPLES[self.option]]
        return self._template_list(items, lambda f: self.buf.set_text(f))
