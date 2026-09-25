"""Parsing/building tmux style strings and converting tmux colours to RGB."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

NAMED_COLOURS = [
    "default", "terminal", "black", "red", "green", "yellow", "blue",
    "magenta", "cyan", "white", "brightblack", "brightred", "brightgreen",
    "brightyellow", "brightblue", "brightmagenta", "brightcyan", "brightwhite",
]

ATTRIBUTES = [
    "bright", "dim", "underscore", "blink", "reverse", "hidden", "italics",
    "overline", "strikethrough", "double-underscore", "curly-underscore",
    "dotted-underscore", "dashed-underscore",
]
# Aliases tmux accepts for attributes.
_ATTR_ALIASES = {"bold": "bright"}

_BASE16 = [
    (0x00, 0x00, 0x00), (0x80, 0x00, 0x00), (0x00, 0x80, 0x00),
    (0x80, 0x80, 0x00), (0x00, 0x00, 0x80), (0x80, 0x00, 0x80),
    (0x00, 0x80, 0x80), (0xc0, 0xc0, 0xc0), (0x80, 0x80, 0x80),
    (0xff, 0x00, 0x00), (0x00, 0xff, 0x00), (0xff, 0xff, 0x00),
    (0x00, 0x00, 0xff), (0xff, 0x00, 0xff), (0x00, 0xff, 0xff),
    (0xff, 0xff, 0xff),
]
_NAME_INDEX = {n: i for i, n in enumerate(
    ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"])}


def colour_to_rgb(colour: str):
    """Return (r, g, b) for a tmux colour, or None if it has no fixed RGB."""
    c = normalize_colour(colour) or colour.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", c):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    if c in _NAME_INDEX:
        return _BASE16[_NAME_INDEX[c]]
    if c.startswith("bright") and c[6:] in _NAME_INDEX:
        return _BASE16[_NAME_INDEX[c[6:]] + 8]
    m = re.fullmatch(r"colou?r(\d{1,3})", c)
    if m and int(m.group(1)) < 256:
        return _palette256(int(m.group(1)))
    return None


def normalize_colour(text: str) -> str | None:
    """Return *text* as a colour tmux accepts, or None if it isn't one.

    Accepts tmux names (red, brightblue, default, terminal), colourN/colorN
    (0-255), and RGB as #rrggbb, rrggbb, #rgb or rgb(r, g, b); RGB is
    returned as lower-case #rrggbb, the only RGB form tmux understands.
    """
    t = text.strip().lower()
    if t in NAMED_COLOURS:
        return t
    m = re.fullmatch(r"colou?r(\d{1,3})", t)
    if m:
        return f"colour{int(m.group(1))}" if int(m.group(1)) < 256 else None
    m = re.fullmatch(r"#?([0-9a-f]{6})", t)
    if m:
        return "#" + m.group(1)
    m = re.fullmatch(r"#([0-9a-f]{3})", t)  # short form needs the '#'
    if m:
        return "#" + "".join(c * 2 for c in m.group(1))
    m = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", t)
    if m and all(int(v) < 256 for v in m.groups()):
        return rgb_to_hex(*(int(v) for v in m.groups()))
    return None


def tmux_colour_name(index: int) -> str:
    """Name for palette entry *index*: the 16 base colours by name."""
    if index < 8:
        return NAMED_COLOURS[2 + index]
    if index < 16:
        return NAMED_COLOURS[10 + index - 8]
    return f"colour{index}"


def palette_rgb(index: int):
    return _palette256(index)


def _palette256(n: int):
    if n < 16:
        return _BASE16[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return steps[n // 36], steps[(n // 6) % 6], steps[n % 6]
    v = 8 + (n - 232) * 10
    return v, v, v


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class Style:
    fg: str = ""
    bg: str = ""
    us: str = ""
    fill: str = ""
    attrs: set = field(default_factory=set)
    noattrs: set = field(default_factory=set)
    default: bool = False
    other: list = field(default_factory=list)  # unrecognised parts, kept

    def to_string(self) -> str:
        parts = []
        if self.default:
            parts.append("default")
        for key in ("fg", "bg", "us", "fill"):
            if getattr(self, key):
                parts.append(f"{key}={getattr(self, key)}")
        parts += [a for a in ATTRIBUTES if a in self.attrs]
        parts += [f"no{a}" for a in ATTRIBUTES if a in self.noattrs]
        parts += self.other
        return ",".join(parts) or "default"


def parse_style(text: str) -> Style | None:
    """Parse a style string. Returns None if it contains formats (#{...})."""
    if "#{" in text:
        return None
    s = Style()
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        low = part.lower()
        if low in ("default", "none"):
            s.default = True
        elif "=" in low and low.split("=", 1)[0] in ("fg", "bg", "us", "fill"):
            k, v = part.split("=", 1)
            setattr(s, k.lower(), v)
        elif _ATTR_ALIASES.get(low, low) in ATTRIBUTES:
            s.attrs.add(_ATTR_ALIASES.get(low, low))
        elif low.startswith("no") and _ATTR_ALIASES.get(low[2:], low[2:]) in ATTRIBUTES:
            s.noattrs.add(_ATTR_ALIASES.get(low[2:], low[2:]))
        else:
            s.other.append(part)
    return s
