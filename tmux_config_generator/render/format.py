"""A small tmux format expander, good enough to preview status lines.

Supports short aliases (#S, #W, ...), #{variables}, conditionals
#{?cond,a,b}, comparisons (==, !=, <, >, <=, >=, ||, &&, !, m), option
expansion (E:, T:), window/pane loops (W:, P:), and value modifiers
(=N, =/N/suffix, pN, b:, d:, n:, l:, s/a/b/). Shell commands #(...) are not
run; a placeholder is shown instead. Style directives #[...] are passed
through for the renderer.
"""

from __future__ import annotations

import fnmatch
import os
import re
import time

ALIASES = {
    "D": "pane_id", "F": "window_flags", "H": "host", "h": "host_short",
    "I": "window_index", "P": "pane_index", "S": "session_name",
    "T": "pane_title", "W": "window_name",
}

_STRFTIME = set("aAbBcCdDeFgGhHIjklmMnpPrRsStTuUVwWxXyYzZ%")


class Context:
    """Variables, options and loop data used while expanding formats."""

    def __init__(self, variables=None, options=None, windows=None, panes=None,
                 now=None):
        self.variables = dict(variables or {})
        self.options = options or {}
        self.windows = windows or []   # list of dicts of window variables
        self.panes = panes or []       # list of dicts of pane variables
        self.now = now if now is not None else time.localtime()

    def child(self, **variables) -> "Context":
        c = Context(self.variables, self.options, self.windows, self.panes,
                    self.now)
        c.variables.update({k: str(v) for k, v in variables.items()})
        return c

    def lookup(self, name: str) -> str:
        if name in self.variables:
            return str(self.variables[name])
        if name in self.options:
            v = self.options[name]
            if isinstance(v, list):
                return v[0] if v else ""
            # Flag options read as 1/0 in formats, as in tmux.
            return {"on": "1", "off": "0"}.get(str(v), str(v))
        return ""


def strftime(text: str, now=None) -> str:
    """Expand strftime(3) sequences, leaving unknown ones untouched."""
    now = now if now is not None else time.localtime()

    def repl(m):
        c = m.group(1)
        if c == "%":
            return "%"
        if c not in _STRFTIME:
            return m.group(0)
        try:
            return time.strftime("%" + c, now)
        except ValueError:
            return m.group(0)
    return re.sub(r"%(.)", repl, text)


def _match_brace(s: str, i: int) -> int:
    """Given s[i] == '{' (after '#'), return the index of its closing '}'."""
    depth, j, n = 1, i + 1, len(s)
    while j < n:
        c = s[j]
        if c == "#" and j + 1 < n:
            if s[j + 1] == "{":
                depth += 1
            j += 2
            continue
        if c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def _split(s: str, sep: str, maxsplit: int = -1) -> list[str]:
    """Split on *sep* at the top level (outside #{...}), honouring #-escapes."""
    parts, depth, start, j, n = [], 0, 0, 0, len(s)
    while j < n:
        c = s[j]
        if c == "#" and j + 1 < n:
            if s[j + 1] == "{":
                depth += 1
            j += 2
            continue
        if c == "}" and depth:
            depth -= 1
        elif c == sep and depth == 0 and (maxsplit < 0 or len(parts) < maxsplit):
            parts.append(s[start:j])
            start = j + 1
        j += 1
    parts.append(s[start:])
    return parts


def _truthy(v: str) -> bool:
    return v != "" and v != "0"


def expand(fmt: str, ctx: Context, depth: int = 0) -> str:
    if depth > 20:
        return ""
    out, i, n = [], 0, len(fmt)
    in_style = False
    while i < n:
        c = fmt[i]
        if c == "#" and i + 1 < n:
            nxt = fmt[i + 1]
            if nxt == "{":
                end = _match_brace(fmt, i + 1)
                if end < 0:
                    out.append(fmt[i:])
                    break
                out.append(_expand_var(fmt[i + 2:end], ctx, depth + 1))
                i = end + 1
                continue
            if nxt == "[":
                in_style = True
                out.append("#[")
                i += 2
                continue
            if nxt in "#,}":
                out.append("#" + nxt if nxt == "#" else nxt)
                i += 2
                continue
            if nxt == "(":
                end = fmt.find(")", i)
                out.append("…")
                i = n if end < 0 else end + 1
                continue
            if nxt in ALIASES and not in_style:
                out.append(ctx.lookup(ALIASES[nxt]))
                i += 2
                continue
        if c == "]" and in_style:
            in_style = False
        out.append(c)
        i += 1
    return "".join(out)


def expand_time(fmt: str, ctx: Context) -> str:
    """Like expand, but strftime sequences are expanded first (status-left etc)."""
    return expand(strftime(fmt, ctx.now), ctx)


def visible_len(text: str) -> int:
    return sum(len(t) for t, _s in split_styles(text))


def trim(text: str, width: int, suffix: str = "") -> str:
    """Keep *width* visible characters (negative: from the right)."""
    segs = split_styles(text)
    total = sum(len(t) for t, _s in segs)
    if abs(width) >= total:
        return text
    keep = abs(width)
    if width < 0:
        segs = list(reversed(segs))
    out = []
    for t, style in segs:
        if style is not None:
            out.append(f"#[{style}]")
            continue
        if keep <= 0:
            continue
        piece = t[:keep] if width >= 0 else t[-keep:]
        keep -= len(piece)
        out.append(piece.replace("#", "##"))
    if width < 0:
        out.reverse()
        return suffix + "".join(out)
    return "".join(out) + suffix


def split_styles(text: str):
    """Split expanded text into (text, None) and ("", style) pieces."""
    segs, buf, i, n = [], [], 0, len(text)
    while i < n:
        if text.startswith("##", i):
            buf.append("#")
            i += 2
            continue
        if text.startswith("#[", i):
            end = text.find("]", i)
            if end >= 0:
                if buf:
                    segs.append(("".join(buf), None))
                    buf = []
                segs.append(("", text[i + 2:end]))
                i = end + 1
                continue
        buf.append(text[i])
        i += 1
    if buf:
        segs.append(("".join(buf), None))
    return segs


_CMP = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
}


def _expand_var(content: str, ctx: Context, depth: int) -> str:
    if content.startswith("?"):
        parts = _split(content[1:], ",")
        while len(parts) >= 3:
            cond, value = parts[0], parts[1]
            cv = expand(cond, ctx, depth) if "#{" in cond else ctx.lookup(cond)
            if _truthy(cv):
                return expand(value, ctx, depth)
            parts = parts[2:]
        return expand(parts[0], ctx, depth) if parts else ""

    head = _split(content, ":", 1)
    if len(head) == 1:
        return ctx.lookup(content) if "#{" not in content else expand(content, ctx, depth)
    mods_s, rest = head
    mods = _split(mods_s, ";")

    first = mods[0]
    if first in _CMP:
        a, b = (_split(rest, ",", 1) + [""])[:2]
        return "1" if _CMP[first](expand(a, ctx, depth), expand(b, ctx, depth)) else "0"
    if first in ("||", "&&"):
        vals = [_truthy(expand(p, ctx, depth)) for p in _split(rest, ",")]
        return "1" if (any(vals) if first == "||" else all(vals)) else "0"
    if first == "!":
        return "0" if _truthy(expand(rest, ctx, depth)) else "1"
    if first.startswith("m"):
        pat, s = (_split(rest, ",", 1) + [""])[:2]
        pat, s = expand(pat, ctx, depth), expand(s, ctx, depth)
        if "r" in first:
            try:
                return "1" if re.search(pat, s, re.I if "i" in first else 0) else "0"
            except re.error:
                return "0"
        return "1" if fnmatch.fnmatchcase(s, pat) else "0"
    if first == "l":
        return rest
    if first in ("W", "S", "P"):
        items = {"W": ctx.windows, "P": ctx.panes}.get(first, [])
        fmts = _split(rest, ",")
        out = []
        for item in items:
            cur = item.get("window_active" if first == "W" else "pane_active") == "1"
            f = fmts[1] if cur and len(fmts) > 1 else fmts[0]
            out.append(expand(f, ctx.child(**item), depth))
        return "".join(out)
    if first.startswith("e|"):
        return ""

    # Value modifiers applied to a variable or expanded option.
    if any(m in ("E", "T") for m in mods):
        value = expand(ctx.lookup(rest), ctx, depth)
        if "T" in mods:
            value = strftime(value, ctx.now)
    elif "#{" in rest:
        value = expand(rest, ctx, depth)
    else:
        value = ctx.lookup(rest)

    for m in mods:
        if m in ("E", "T", ""):
            continue
        if m == "b":
            value = os.path.basename(value)
        elif m == "d":
            value = os.path.dirname(value)
        elif m == "n":
            value = str(len(value))
        elif m == "q":
            value = re.sub(r"([^\w/.:-])", r"\\\1", value)
        elif m == "t":
            value = time.strftime("%a %b %d %H:%M:%S %Y", ctx.now)
        elif m.startswith("s/"):
            bits = m[2:].split("/")
            if len(bits) >= 2:
                try:
                    value = re.sub(bits[0], bits[1], value)
                except re.error:
                    pass
        elif m.startswith("="):
            spec = m[1:]
            suffix = ""
            if spec.startswith("/"):
                bits = spec[1:].split("/", 1)
                spec, suffix = bits[0], (bits[1] if len(bits) > 1 else "")
            try:
                w = int(expand(spec, ctx, depth))
            except ValueError:
                continue
            if w and visible_len(value) > abs(w):
                value = trim(value, w, suffix)
        elif m.startswith("p"):
            try:
                w = int(expand(m[1:], ctx, depth))
            except ValueError:
                continue
            pad = abs(w) - visible_len(value)
            if pad > 0:
                value = value + " " * pad if w < 0 else " " * pad + value
    return value
