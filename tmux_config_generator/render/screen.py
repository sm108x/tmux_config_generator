"""Build a character-grid mock-up of a tmux client from option values.

The result is a Screen (rows of cells with a CellStyle each) that the GTK
preview widget paints. Nothing here depends on GTK.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace

from ..options import OPTIONS
from ..styles import ATTRIBUTES
from .format import Context, expand, expand_time, split_styles, trim, visible_len

SCENES = [
    ("normal", "Normal"),
    ("copy", "Copy mode"),
    ("menu", "Menu"),
    ("popup", "Popup"),
    ("message", "Message"),
    ("prompt", "Command prompt"),
    ("clock", "Clock mode"),
    ("display-panes", "Display panes"),
    ("alerts", "Alerts"),
]

_ATTR_ALIASES = {"bold": "bright"}


@dataclass(frozen=True)
class CellStyle:
    fg: str = "default"
    bg: str = "default"
    us: str = ""
    attrs: frozenset = frozenset()


DEFAULT = CellStyle()


def apply_style(base: CellStyle, spec: str, default: CellStyle = DEFAULT):
    """Apply a tmux style string on top of *base*.

    Returns (style, align) where align is the last align= seen, if any.
    """
    style, align = base, None
    for part in re.split(r"[,\s]+", spec.strip()):
        low = part.lower()
        if not low:
            continue
        if low == "default":
            style = default
        elif low == "none":
            style = replace(style, attrs=frozenset())
        elif "=" in low:
            k, v = part.split("=", 1)
            k = k.lower()
            if k in ("fg", "bg", "us"):
                style = replace(style, **{k: v})
            elif k == "align":
                align = v.lower()
        else:
            name = _ATTR_ALIASES.get(low, low)
            if name in ATTRIBUTES:
                style = replace(style, attrs=style.attrs | {name})
            elif name.startswith("no") and _ATTR_ALIASES.get(name[2:], name[2:]) in ATTRIBUTES:
                style = replace(style, attrs=style.attrs - {_ATTR_ALIASES.get(name[2:], name[2:])})
    return style, align


def styled(base: CellStyle, spec: str, default: CellStyle = DEFAULT) -> CellStyle:
    return apply_style(base, spec, default)[0]


def runs(text: str, base: CellStyle, default: CellStyle | None = None):
    """Turn expanded text with #[...] directives into [(text, style, align)]."""
    default = default or base
    out, style, align = [], base, "left"
    for t, spec in split_styles(text):
        if spec is None:
            if t:
                out.append((t, style, align))
        else:
            style, a = apply_style(style, spec, default)
            if a:
                align = a
    return out


@dataclass
class Cursor:
    x: int
    y: int
    shape: str   # block, underline, bar
    colour: str  # tmux colour or "default"


@dataclass
class Screen:
    cols: int
    rows: int
    cells: list = field(default_factory=list)
    cursor: Cursor | None = None

    def __post_init__(self):
        self.cells = [[(" ", DEFAULT) for _ in range(self.cols)]
                      for _ in range(self.rows)]

    def put(self, x: int, y: int, text: str, style: CellStyle, limit: int | None = None):
        """Write text; returns the x after the last character written."""
        end = self.cols if limit is None else min(self.cols, limit)
        if not 0 <= y < self.rows:
            return x + len(text)
        for ch in text:
            if 0 <= x < end:
                self.cells[y][x] = (ch, style)
            x += 1
        return x

    def fill(self, x: int, y: int, w: int, h: int, style: CellStyle, ch: str = " "):
        for yy in range(y, y + h):
            self.put(x, yy, ch * w, style)

    def put_runs(self, x: int, y: int, rs, limit: int | None = None) -> int:
        for t, style, _align in rs:
            x = self.put(x, y, t, style, limit)
        return x

    def restyle(self, x: int, y: int, w: int, style: CellStyle):
        for xx in range(max(0, x), min(self.cols, x + w)):
            if 0 <= y < self.rows:
                self.cells[y][xx] = (self.cells[y][xx][0], style)


def runs_width(rs) -> int:
    return sum(len(t) for t, _s, _a in rs)


def clip_runs(rs, width: int, from_right: bool = False):
    if runs_width(rs) <= width:
        return rs
    out, keep = [], width
    for t, s, a in (reversed(rs) if from_right else rs):
        if keep <= 0:
            break
        piece = t[-keep:] if from_right else t[:keep]
        keep -= len(piece)
        out.append((piece, s, a))
    return list(reversed(out)) if from_right else out


# ---------------------------------------------------------------------------
# Sample session


LINES = {
    "single": dict(v="│", h="─", x="┼", td="┬", tu="┴", tr="├", tl="┤",
                   tlc="┌", trc="┐", blc="└", brc="┘"),
    "rounded": dict(v="│", h="─", x="┼", td="┬", tu="┴", tr="├", tl="┤",
                    tlc="╭", trc="╮", blc="╰", brc="╯"),
    "double": dict(v="║", h="═", x="╬", td="╦", tu="╩", tr="╠", tl="╣",
                   tlc="╔", trc="╗", blc="╚", brc="╝"),
    "heavy": dict(v="┃", h="━", x="╋", td="┳", tu="┻", tr="┣", tl="┫",
                  tlc="┏", trc="┓", blc="┗", brc="┛"),
    "simple": dict(v="|", h="-", x="+", td="+", tu="+", tr="+", tl="+",
                   tlc="+", trc="+", blc="+", brc="+"),
    "padded": dict(v=" ", h=" ", x=" ", td=" ", tu=" ", tr=" ", tl=" ",
                   tlc=" ", trc=" ", blc=" ", brc=" "),
}

SHELL_LINES = [
    "~/project$ ls",
    "README.md  src  tests  pyproject.toml",
    "~/project$ git log --oneline -3",
    "9a859c8 Add app icon and launcher",
    "0c5198a License under GPL-3.0",
    "0bf3e7a Add tmux config generator",
    "~/project$ grep -rn TODO src",
    "src/app.py:42:  # TODO: tidy up",
    "src/ui.py:17:   # TODO: dark mode",
    "~/project$ ",
]
VIM_LINES = [
    "  1 import os",
    "  2 import sys",
    "  3 ",
    "  4 def main():",
    "  5     print('hello')",
    "  6     return 0",
    "  7 ",
    "  8 if __name__ == '__main__':",
    "  9     sys.exit(main())",
]
TOP_LINES = [
    " CPU[|||||||      38.2%]",
    " Mem[|||||||||   2.1G/8G]",
    "  PID USER  %CPU COMMAND",
    " 1204 user  12.0 python3",
    "  987 user   3.1 tmux",
    "  412 root   0.7 Xorg",
]

MENU_ITEMS = [
    ("Horizontal Split", "h"), ("Vertical Split", "v"), None,
    ("Swap Up", "u"), ("Swap Down", "d"), None,
    ("Kill", "X"), ("Respawn", "R"), ("Mark", "m"), ("Zoom", "z"),
]

# 5x5 big digits, roughly as tmux's clock mode draws them.
BIG = {
    "0": ["#####", "#   #", "#   #", "#   #", "#####"],
    "1": ["    #", "    #", "    #", "    #", "    #"],
    "2": ["#####", "    #", "#####", "#    ", "#####"],
    "3": ["#####", "    #", "#####", "    #", "#####"],
    "4": ["#   #", "#   #", "#####", "    #", "    #"],
    "5": ["#####", "#    ", "#####", "    #", "#####"],
    "6": ["#####", "#    ", "#####", "#   #", "#####"],
    "7": ["#####", "    #", "    #", "    #", "    #"],
    "8": ["#####", "#   #", "#####", "#   #", "#####"],
    "9": ["#####", "#   #", "#####", "    #", "#####"],
    ":": ["     ", "  #  ", "     ", "  #  ", "     "],
    "A": ["#####", "#   #", "#####", "#   #", "#   #"],
    "P": ["#####", "#   #", "#####", "#    ", "#    "],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
}


def effective_values(cfg) -> dict:
    """Option name -> value, using tmux defaults for options not set."""
    return {o.name: cfg.values.get(o.name, o.default) for o in OPTIONS}


class SceneBuilder:
    def __init__(self, values: dict, scene: str = "normal", cols: int = 90,
                 rows: int = 22, now=None):
        self.v = values
        self.scene = scene
        self.scr = Screen(cols, rows)
        self.now = now if now is not None else time.localtime()
        self.base_index = self._int("base-index", 0)
        self.pane_base = self._int("pane-base-index", 0)
        self.windows = self._windows()
        self.ctx = Context(self._session_vars(), values, self.windows, [],
                           self.now)

    # -- helpers ----------------------------------------------------------

    def _int(self, name, fallback):
        try:
            return int(self.v.get(name, fallback))
        except (TypeError, ValueError):
            return fallback

    def _on(self, name) -> bool:
        return str(self.v.get(name, "off")) == "on"

    def _windows(self):
        b = self.base_index
        specs = [("bash", "-", "last"), ("vim", "*", "current"),
                 ("htop", "#", "activity"), ("logs", "!", "bell")]
        ws = []
        for i, (name, flag, kind) in enumerate(specs):
            ws.append({
                "window_index": str(b + i), "window_name": name,
                "window_flags": flag, "window_raw_flags": flag,
                "window_active": "1" if kind == "current" else "0",
                "window_last_flag": "1" if kind == "last" else "0",
                "window_bell_flag": "1" if kind == "bell" else "0",
                "window_activity_flag": "1" if kind == "activity" else "0",
                "window_silence_flag": "0",
                "window_start_flag": "1" if i == 0 else "0",
                "window_end_flag": "1" if i == len(specs) - 1 else "0",
                "window_panes": "3", "window_zoomed_flag": "0",
                "window_bigger": "0", "window_offset_x": "0",
                "window_offset_y": "0", "window_id": f"@{i}",
                "_kind": kind,
            })
        return ws

    def _session_vars(self):
        cur = self.windows[1]
        v = {k: val for k, val in cur.items() if not k.startswith("_")}
        v.update({
            "session_name": "main", "session_windows": "4",
            "session_alerts": f"{self.base_index + 2}#,{self.base_index + 3}!",
            "session_attached": "1", "host": "workstation",
            "host_short": "workstation", "client_prefix": "0",
            "client_termname": "xterm-256color", "pid": "4242",
            "version": "3.4",
        })
        v.update(self._pane_vars(0, True))
        return v

    def _pane_vars(self, i, active, width=44, height=20):
        cmds = ["bash", "vim", "htop"]
        return {
            "pane_index": str(self.pane_base + i), "pane_id": f"%{i + 1}",
            "pane_active": "1" if active else "0",
            "pane_title": "workstation", "pane_current_command": cmds[i],
            "pane_current_path": "/home/user/project",
            "pane_width": str(width), "pane_height": str(height),
            "pane_in_mode": "1" if (active and self.scene == "copy") else "0",
            "pane_mode": "copy-mode" if (active and self.scene == "copy") else "",
            "pane_dead": "0", "pane_marked": "0", "pane_marked_set": "0",
            "pane_synchronized": "1" if self._on("synchronize-panes") else "0",
        }

    def status_style(self) -> CellStyle:
        return styled(DEFAULT, str(self.v.get("status-style", "default")))

    # -- build ------------------------------------------------------------

    def build(self) -> Screen:
        status = str(self.v.get("status", "on"))
        lines = {"off": 0, "on": 1}.get(status, None)
        if lines is None:
            lines = int(status) if status.isdigit() else 1
        top = str(self.v.get("status-position", "bottom")) == "top"
        rows = self.scr.rows
        area_y = lines if top else 0
        area_h = rows - lines
        self.area_y, self.area_h = area_y, area_h
        self.draw_panes(0, area_y, self.scr.cols, area_h)
        status_y = 0 if top else rows - lines
        for i in range(lines):
            self.draw_status_line(status_y + i, i)
        if self.scene in ("message", "prompt", "alerts") and lines:
            idx = min(self._int("message-line", 0), lines - 1)
            self.draw_message(status_y + idx)
        if self.scene == "menu":
            self.draw_menu()
        if self.scene == "popup":
            self.draw_popup(area_y, area_h)
        return self.scr

    # -- status line --------------------------------------------------------

    def draw_status_line(self, y: int, index: int):
        scr, sst = self.scr, self.status_style()
        scr.fill(0, y, scr.cols, 1, sst)
        custom = self.v.get("status-format") or []
        if isinstance(custom, list) and index < len(custom) and custom[index]:
            self.draw_aligned(y, expand_time(custom[index], self.ctx), sst)
        elif index == 0:
            self.draw_default_status(y, sst)
        elif index == 1:
            parts = []
            for i, (w, h) in enumerate([(44, 20), (45, 9), (45, 10)]):
                pane = self.pane_base + i
                if i == 0:
                    parts.append(f"#[reverse]{pane}[{w}x{h}]#[default] ")
                else:
                    parts.append(f"{pane}[{w}x{h}] ")
            self.draw_aligned(y, "#[align=centre]" + "".join(parts), sst)

    def draw_aligned(self, y: int, text: str, base: CellStyle):
        rs = runs(text, base)
        groups = {"left": [], "centre": [], "center": [], "right": [],
                  "absolute-centre": []}
        for r in rs:
            groups.setdefault(r[2], []).append(r)
        cols = self.scr.cols
        self.scr.put_runs(0, y, groups["left"])
        right = groups["right"]
        self.scr.put_runs(cols - runs_width(right), y, right)
        centre = groups["centre"] + groups["center"] + groups["absolute-centre"]
        self.scr.put_runs((cols - runs_width(centre)) // 2, y, centre)

    def _window_runs(self, w, sst):
        v = self.v
        ctx = self.ctx.child(**{k: val for k, val in w.items() if not k.startswith("_")})
        kind = w["_kind"]
        wstyle = str(v.get("window-status-style", "default"))
        if kind == "current":
            cstyle = str(v.get("window-status-current-style", "default"))
            spec = cstyle if cstyle != "default" else wstyle
            fmt = str(v.get("window-status-current-format", ""))
        else:
            spec = wstyle
            fmt = str(v.get("window-status-format", ""))
        extra = {"last": "window-status-last-style",
                 "bell": "window-status-bell-style",
                 "activity": "window-status-activity-style"}.get(kind)
        base = styled(sst, expand(spec, ctx), sst)
        if extra:
            espec = str(v.get(extra, "default"))
            if espec != "default":
                base = styled(base, expand(espec, ctx), sst)
        return runs(expand_time(fmt, ctx), base, sst)

    def draw_default_status(self, y: int, sst: CellStyle):
        v, scr, cols = self.v, self.scr, self.scr.cols
        lstyle = styled(sst, str(v.get("status-left-style", "default")), sst)
        rstyle = styled(sst, str(v.get("status-right-style", "default")), sst)
        left = runs(expand_time(str(v.get("status-left", "")), self.ctx), lstyle, sst)
        right = runs(expand_time(str(v.get("status-right", "")), self.ctx), rstyle, sst)
        left = clip_runs(left, self._int("status-left-length", 10))
        right = clip_runs(right, self._int("status-right-length", 40))

        sep = runs(expand(str(v.get("window-status-separator", " ")), self.ctx), sst)
        wl = []
        for i, w in enumerate(self.windows):
            wl += self._window_runs(w, sst)
            if i < len(self.windows) - 1:
                wl += sep
        lw, rw, ww = runs_width(left), runs_width(right), runs_width(wl)
        free = cols - lw - rw
        wl = clip_runs(wl, max(0, free))
        ww = runs_width(wl)
        justify = str(v.get("status-justify", "left"))
        if justify == "right":
            x = cols - rw - ww
        elif justify == "centre":
            x = lw + (free - ww) // 2
        elif justify == "absolute-centre":
            x = (cols - ww) // 2
        else:
            x = lw
        scr.put_runs(0, y, left)
        scr.put_runs(max(x, lw), y, wl, limit=cols - rw)
        scr.put_runs(cols - rw, y, right)

    def draw_message(self, y: int):
        v, scr = self.v, self.scr
        if self.scene == "prompt":
            vi = str(v.get("status-keys", "emacs")) == "vi"
            spec = str(v.get("message-style", "default"))
            style = styled(self.status_style(), spec)
            text = ":split-window -h"
            scr.fill(0, y, scr.cols, 1, style)
            scr.put(0, y, text, style)
            if vi:
                # vi command mode (after Escape) uses message-command-style.
                cstyle = styled(self.status_style(), str(v.get("message-command-style", "default")))
                scr.fill(0, y, scr.cols, 1, cstyle)
                scr.put(0, y, text, cstyle)
            scr.cursor = Cursor(len(text), y, "block", "default")
            return
        if self.scene == "alerts":
            b = self.base_index
            if str(v.get("visual-bell", "off")) != "off":
                text = f"Bell in window {b + 3}"
            elif str(v.get("visual-activity", "off")) != "off":
                text = f"Activity in window {b + 2}"
            elif str(v.get("visual-silence", "off")) != "off":
                text = f"Silence in window {b + 2}"
            else:
                return
        else:
            text = "Config reloaded."
        style = styled(self.status_style(), str(v.get("message-style", "default")))
        scr.fill(0, y, scr.cols, 1, style)
        scr.put(0, y, text, style)

    # -- panes --------------------------------------------------------------

    def draw_panes(self, x0, y0, w, h):
        v, scr = self.v, self.scr
        if h <= 0:
            return
        border_status = str(v.get("pane-border-status", "off"))
        lines_type = str(v.get("pane-border-lines", "single"))
        ch = LINES.get(lines_type, LINES["single"])

        # Layout: left pane (active) | right-top / right-bottom.
        lw = (w - 1) // 2
        rx = x0 + lw + 1
        rwid = w - lw - 1
        top_pad = 1 if border_status == "top" else 0
        bot_pad = 1 if border_status == "bottom" else 0
        inner_h = h - top_pad - bot_pad
        th = (inner_h - 1) // 2
        panes = [
            (0, x0, y0 + top_pad, lw, inner_h),
            (1, rx, y0 + top_pad, rwid, th),
            (2, rx, y0 + top_pad + th + 1, rwid, inner_h - th - 1),
        ]
        active = 0
        pctx = {i: self.ctx.child(**self._pane_vars(i, i == active, pw, ph))
                for i, _x, _y, pw, ph in panes}
        wstyle = styled(DEFAULT, expand(str(v.get("window-style", "default")), self.ctx))
        astyle = styled(wstyle, expand(str(v.get("window-active-style", "default")), self.ctx), wstyle)

        def bstyle(i):
            name = "pane-active-border-style" if i == active else "pane-border-style"
            return styled(DEFAULT, expand(str(v.get(name, "default")), pctx[i]))

        for i, px, py, pw, ph in panes:
            style = astyle if i == active else wstyle
            scr.fill(px, py, pw, ph, style)
            self.draw_pane_content(i, px, py, pw, ph, style, i == active)

        # Borders.
        num = lines_type == "number"
        vert = str(self.pane_base + 0) if num else ch["v"]
        horz = str(self.pane_base + 2) if num else ch["h"]
        bx = x0 + lw
        sep_y = y0 + top_pad + th
        for yy in range(y0, y0 + h):
            scr.put(bx, yy, vert, bstyle(active))
        for xx in range(rx, x0 + w):
            scr.put(xx, sep_y, horz, bstyle(1))
        scr.put(bx, sep_y, ch["tr"] if not num else vert, bstyle(active))
        indicators = str(v.get("pane-border-indicators", "colour"))
        if indicators in ("arrows", "both"):
            scr.put(bx, y0 + top_pad + inner_h // 2, "←", bstyle(active))

        if border_status in ("top", "bottom"):
            fmt = str(v.get("pane-border-format", ""))
            for i, px, py, pw, ph in panes:
                if border_status == "top":
                    by = py - 1
                else:
                    by = py + ph
                if i == 1 and border_status == "bottom":
                    by = sep_y
                if i == 2 and border_status == "top":
                    by = sep_y
                st = bstyle(i)
                scr.put(px, by, horz * pw, st)
                text = expand_time(fmt, pctx[i])
                rs = clip_runs(runs(text, st), max(0, pw - 4))
                scr.put_runs(px + 2, by, rs, limit=px + pw - 2)
            scr.put(bx, sep_y, ch["tr"] if not num else vert, bstyle(active))
            if not num:
                edge_y = y0 if border_status == "top" else y0 + h - 1
                scr.put(bx, edge_y, ch["td"] if border_status == "top" else ch["tu"],
                        bstyle(active))

        if self.scene == "display-panes":
            for i, px, py, pw, ph in panes:
                colour = str(v.get("display-panes-active-colour" if i == active
                                   else "display-panes-colour", "blue"))
                self.draw_big(str(self.pane_base + i), px, py, pw, ph, colour,
                              f"{pw}x{ph}")

    def draw_pane_content(self, i, px, py, pw, ph, style, active):
        scr, v = self.scr, self.v
        if active and self.scene == "clock":
            colour = str(v.get("clock-mode-colour", "blue"))
            fmt = "%H:%M" if str(v.get("clock-mode-style", "24")) == "24" else "%I:%M"
            text = time.strftime(fmt, self.now)
            if fmt != "%H:%M":
                text += time.strftime("%p", self.now)
            self.draw_big(text, px, py, pw, ph, colour, time.strftime("%H:%M:%S", self.now))
            return
        lines = [SHELL_LINES, VIM_LINES, TOP_LINES][i]
        if active and self.scene == "copy":
            lines = SHELL_LINES[:-1]
        shown = lines[-ph:] if len(lines) > ph else lines
        for n, line in enumerate(shown):
            scr.put(px, py + n, line[:pw], style)
        if active and self.scene == "copy":
            self.draw_copy_mode(px, py, pw, ph, shown, style)
        elif active and self.scene not in ("display-panes",):
            cy = py + min(len(shown), ph) - 1
            cx = px + len(shown[-1]) if shown else px
            shape = str(v.get("cursor-style", "default"))
            shape = {"default": "block"}.get(shape, shape.replace("blinking-", ""))
            scr.cursor = Cursor(min(cx, px + pw - 1), cy, shape,
                                str(v.get("cursor-colour", "default")))

    def draw_copy_mode(self, px, py, pw, ph, shown, style):
        scr, v = self.scr, self.v
        ctx = self.ctx.child(**self._pane_vars(0, True, pw, ph))
        mode = styled(style, expand(str(v.get("mode-style", "default")), ctx), style)
        match = styled(style, str(v.get("copy-mode-match-style", "default")), style)
        current = styled(style, str(v.get("copy-mode-current-match-style", "default")), style)
        mark = styled(style, str(v.get("copy-mode-mark-style", "default")), style)
        # Mark line, search matches for "TODO", then a selection.
        for n, line in enumerate(shown):
            if line.startswith("0bf3e7a"):
                scr.restyle(px, py + n, pw, mark)
        found = 0
        for n, line in enumerate(shown):
            for m in re.finditer("TODO", line):
                st = current if found == 0 else match
                scr.restyle(px + m.start(), py + n, 4, st)
                found += 1
        for n, line in enumerate(shown):
            if line.startswith("9a859c8"):
                scr.restyle(px + 8, py + n, max(0, min(pw, len(line)) - 8), mode)
                if n + 1 < len(shown):
                    scr.restyle(px, py + n + 1, 7, mode)
        pos = f"[0/{len(shown) + 30}]"
        scr.put(px + pw - len(pos), py, pos, mode)

    def draw_big(self, text, px, py, pw, ph, colour, subtitle=""):
        scr = self.scr
        block = CellStyle(bg=colour)
        fg = CellStyle(fg=colour)
        width = len(text) * 6 - 1
        if width <= pw and ph >= 5:
            x = px + (pw - width) // 2
            y = py + (ph - 5) // 2
            for ch in text:
                glyph = BIG.get(ch.upper(), BIG[":"])
                for r, row in enumerate(glyph):
                    for c, cell in enumerate(row):
                        if cell == "#":
                            scr.put(x + c, y + r, " ", block)
                x += 6
            if subtitle and y + 6 < py + ph:
                scr.put(px + (pw - len(subtitle)) // 2, y + 6, subtitle, fg)
        else:
            scr.put(px + max(0, (pw - len(text)) // 2), py + ph // 2, text, fg)

    # -- overlays -----------------------------------------------------------

    def draw_box(self, x, y, w, h, lines_type, border, inner, title=""):
        scr = self.scr
        scr.fill(x, y, w, h, inner)
        if lines_type == "none":
            return
        ch = LINES.get(lines_type, LINES["single"])
        scr.put(x, y, ch["tlc"] + ch["h"] * (w - 2) + ch["trc"], border)
        scr.put(x, y + h - 1, ch["blc"] + ch["h"] * (w - 2) + ch["brc"], border)
        for yy in range(y + 1, y + h - 1):
            scr.put(x, yy, ch["v"], border)
            scr.put(x + w - 1, yy, ch["v"], border)
        if title:
            rs = clip_runs(runs(title, border), w - 4)
            scr.put_runs(x + (w - runs_width(rs)) // 2, y, rs)

    def draw_menu(self):
        v = self.v
        width = 24
        items = list(MENU_ITEMS)
        # Drop items until the menu fits in the pane area.
        while len(items) + 2 > self.area_h and len(items) > 1:
            items.pop()
        h = len(items) + 2
        x = 6
        y = self.area_y + min(2, max(0, self.area_h - h))
        mstyle = styled(DEFAULT, str(v.get("menu-style", "default")))
        sel = styled(mstyle, str(v.get("menu-selected-style", "default")), mstyle)
        border = styled(mstyle, str(v.get("menu-border-style", "default")), mstyle)
        lines_type = str(v.get("menu-border-lines", "single"))
        title = f"#[align=centre]{self.pane_base} (%1)"
        rs = runs(expand(title, self.ctx), border)
        title_text = "".join(t for t, _s, _a in rs)
        self.draw_box(x, y, width, h, lines_type, border, mstyle, "")
        if lines_type != "none":
            self.scr.put(x + (width - len(title_text)) // 2, y, title_text, border)
        ch = LINES.get(lines_type, LINES["single"])
        for n, item in enumerate(items):
            yy = y + 1 + n
            if item is None:
                if lines_type != "none":
                    self.scr.put(x, yy, ch["tr"] + ch["h"] * (width - 2) + ch["tl"], border)
                continue
            label, key = item
            st = sel if n == 0 else mstyle
            text = f" {label}".ljust(width - 6) + f"({key}) "
            self.scr.put(x + 1, yy, text[:width - 2], st)

    def draw_popup(self, area_y, area_h):
        v, scr = self.v, self.scr
        w = scr.cols * 6 // 10
        h = max(5, area_h * 6 // 10)
        x = (scr.cols - w) // 2
        y = area_y + (area_h - h) // 2
        pstyle = styled(DEFAULT, str(v.get("popup-style", "default")))
        border = styled(pstyle, str(v.get("popup-border-style", "default")), pstyle)
        lines_type = str(v.get("popup-border-lines", "single"))
        self.draw_box(x, y, w, h, lines_type, border, pstyle)
        inset = 0 if lines_type == "none" else 1
        for n, line in enumerate(TOP_LINES[:h - 2 * inset]):
            scr.put(x + inset, y + inset + n, line[:w - 2 * inset], pstyle)


def build_screen(values: dict, scene: str = "normal", cols: int = 90,
                 rows: int = 22, now=None) -> Screen:
    return SceneBuilder(values, scene, cols, rows, now).build()


# Which scene best shows an option, used to switch scene while editing.
def scene_for_option(name: str) -> str | None:
    if name.startswith("menu-"):
        return "menu"
    if name.startswith("popup-"):
        return "popup"
    if name.startswith("copy-mode-") or name == "mode-style":
        return "copy"
    if name.startswith("clock-mode-"):
        return "clock"
    if name.startswith("display-panes-"):
        return "display-panes"
    if name in ("message-command-style",):
        return "prompt"
    if name in ("message-style", "message-line", "display-time"):
        return "message"
    if name.startswith("visual-"):
        return "alerts"
    return None


# ---------------------------------------------------------------------------
# Small renders used by the format builder


def status_lines(values: dict) -> int:
    status = str(values.get("status", "on"))
    if status == "off":
        return 1  # still show the line being edited
    return int(status) if status.isdigit() else 1


def build_status_screen(values: dict, cols: int, now=None) -> Screen:
    """Just the status line(s), as tmux would draw them."""
    b = SceneBuilder(values, "normal", cols, status_lines(values), now)
    for i in range(b.scr.rows):
        b.draw_status_line(i, i)
    return b.scr


def build_border_screen(values: dict, cols: int, now=None) -> Screen:
    """A pane border status line for the active pane."""
    b = SceneBuilder(values, "normal", cols, 1, now)
    ctx = b.ctx.child(**b._pane_vars(0, True, cols, 20))
    style = styled(DEFAULT, expand(str(values.get("pane-active-border-style", "default")), ctx))
    kind = str(values.get("pane-border-lines", "single"))
    line = LINES.get(kind, LINES["single"])["h"] if kind != "number" else str(b.pane_base)
    b.scr.put(0, 0, line * cols, style)
    rs = clip_runs(runs(expand_time(str(values.get("pane-border-format", "")), ctx), style),
                   max(0, cols - 4))
    b.scr.put_runs(2, 0, rs)
    return b.scr


def build_text_screen(values: dict, fmt: str, cols: int, now=None) -> Screen:
    """A format expanded in the sample session, drawn on the default style."""
    b = SceneBuilder(values, "normal", cols, 1, now)
    b.scr.put_runs(0, 0, runs(expand_time(fmt, b.ctx), DEFAULT))
    return b.scr


def sample_context(values: dict, now=None) -> Context:
    """The sample session's format context (current window, active pane)."""
    return SceneBuilder(values, "normal", 10, 1, now).ctx
