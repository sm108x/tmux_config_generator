"""Terminal settings data: default-terminal choices, terminal-features and
terminal-overrides vocabulary, and helpers to parse/build their entries.

Descriptions are condensed from tmux(1) (3.4).
"""

from __future__ import annotations

import os
from pathlib import Path

# (value, description) for default-terminal.
DEFAULT_TERMINALS = [
    ("tmux-256color", "Recommended. Full tmux terminfo: 256 colours, italics, "
                      "strikethrough; needs the tmux-256color entry"),
    ("screen-256color", "Widely installed fallback with 256 colours "
                        "(no italics on some systems)"),
    ("tmux", "tmux terminfo with 8 colours"),
    ("screen", "Most compatible, 8 colours; for very old systems"),
    ("tmux-direct", "tmux terminfo with direct (24-bit) colour instead of a palette"),
    ("xterm-256color", "Not recommended inside tmux; some programs misbehave, "
                       "but useful where no tmux/screen entry exists"),
]

# (feature, description) for terminal-features.
FEATURES = [
    ("256", "256 colours with the SGR escape sequences"),
    ("RGB", "RGB (24-bit, true) colour with the SGR escape sequences"),
    ("clipboard", "Allows setting the system clipboard (OSC 52)"),
    ("ccolour", "Allows setting the cursor colour"),
    ("cstyle", "Allows setting the cursor style"),
    ("extkeys", "Supports extended keys"),
    ("focus", "Supports focus reporting"),
    ("hyperlinks", "Supports OSC 8 hyperlinks"),
    ("ignorefkeys", "Ignore function keys from terminfo; use tmux's internal set"),
    ("margins", "Supports DECSLRM margins"),
    ("mouse", "Supports xterm mouse sequences"),
    ("osc7", "Supports the OSC 7 working directory extension"),
    ("overline", "Supports the overline SGR attribute"),
    ("rectfill", "Supports the DECFRA rectangle fill escape sequence"),
    ("sixel", "Supports SIXEL graphics"),
    ("strikethrough", "Supports the strikethrough SGR escape sequence"),
    ("sync", "Supports synchronized updates"),
    ("title", "Supports xterm title setting"),
    ("usstyle", "Allows underscore style and colour to be set (undercurl etc.)"),
]
FEATURE_NAMES = [f for f, _d in FEATURES]

# (capability, kind, description, example value) for terminal-overrides.
# kind: "flag" (boolean, just the name), "string", "number".
CAPABILITIES = [
    ("Tc", "flag", "Terminal supports direct (RGB) colour; same as RGB", ""),
    ("RGB", "flag", "Terminal supports RGB colour", ""),
    ("Ss", "string", "Set cursor style", r"\E[%p1%d q"),
    ("Se", "string", "Reset cursor style", r"\E[2 q"),
    ("Cs", "string", "Set cursor colour", r"\E]12;%p1%s\007"),
    ("Cr", "string", "Reset cursor colour", r"\E]112\007"),
    ("Smulx", "string", "Styled underscore (curly, dotted, …)", r"\E[4::%p1%dm"),
    ("Setulc", "string", "Set underscore colour (RGB)",
     r"\E[58::2::%p1%{65536}%/%d::%p1%{256}%/%{255}%&%d::%p1%{255}%&%d%;m"),
    ("Ms", "string", "Set the clipboard (OSC 52)", r"\E]52;%p1%s;%p2%s\007"),
    ("Smol", "string", "Enable overline", r"\E[53m"),
    ("Hls", "string", "Set or clear a hyperlink", r"\E]8;%?%p1%l%tid=%p1%s%;;%p2%s\E\\"),
    ("Sync", "string", "Start/end synchronized update", r"\EP=%p1%ds\E\\"),
    ("Swd", "string", "Working directory notification (OSC 7)", r"\E]7;"),
    ("Enbp", "string", "Enable bracketed paste", r"\E[?2004h"),
    ("Dsbp", "string", "Disable bracketed paste", r"\E[?2004l"),
    ("Enfcs", "string", "Enable focus reporting", r"\E[?1004h"),
    ("Dsfcs", "string", "Disable focus reporting", r"\E[?1004l"),
    ("Eneks", "string", "Enable extended keys", r"\E[>4;1m"),
    ("Dseks", "string", "Disable extended keys", r"\E[>4m"),
    ("Sxl", "flag", "Terminal supports SIXEL", ""),
    ("Rect", "flag", "Terminal supports rectangle operations", ""),
    ("Nobr", "flag", "Bold is not shown with bright colours", ""),
    ("AX", "flag", "Terminal supports default colours", ""),
    ("XT", "flag", "xterm-compatible (title, and enables several of the above)", ""),
    ("smcup", "string", "Enter the alternate screen (unset with @ to keep scrollback)", r"\E[?1049h"),
    ("rmcup", "string", "Leave the alternate screen", r"\E[?1049l"),
    ("colors", "number", "Number of colours", "256"),
    ("kbs", "string", "Backspace key", r"^?"),
    ("sitm", "string", "Enter italics", r"\E[3m"),
    ("ritm", "string", "Leave italics", r"\E[23m"),
    ("smxx", "string", "Enter strikethrough", r"\E[9m"),
    ("clear", "string", "Clear screen", r"\E[H\E[2J"),
]
CAPABILITY_INFO = {c[0]: c for c in CAPABILITIES}

# Suggested terminal type patterns (fnmatch).
PATTERNS = [
    ("*", "every terminal"),
    ("xterm*", "xterm and most terminals that call themselves xterm"),
    ("xterm-256color", "exactly xterm-256color"),
    ("*256col*", "any 256-colour terminal"),
    ("alacritty*", "Alacritty"), ("xterm-kitty", "kitty"),
    ("foot*", "foot"), ("wezterm", "WezTerm"), ("xterm-ghostty", "Ghostty"),
    ("gnome*", "GNOME Terminal / VTE"), ("vte*", "VTE-based terminals"),
    ("rxvt*", "rxvt / urxvt"), ("st-*", "st"), ("screen*", "screen"),
    ("tmux*", "tmux (nested)"), ("linux", "Linux console"),
]

# Ready-made entries: (label, entry).
FEATURE_RECIPES = [
    ("True colour for xterm-like terminals", "xterm*:RGB"),
    ("True colour everywhere", "*:RGB"),
    ("256 colour terminals get true colour", "*256col*:RGB"),
    ("Clipboard + cursor style/colour", "xterm*:clipboard:ccolour:cstyle"),
    ("Undercurl and coloured underlines", "xterm*:usstyle"),
    ("Hyperlinks (OSC 8)", "xterm*:hyperlinks"),
    ("Kitty: modern features", "xterm-kitty:RGB:usstyle:hyperlinks:clipboard:ccolour:cstyle:focus:sync:extkeys"),
    ("Alacritty: modern features", "alacritty*:RGB:clipboard:ccolour:cstyle:focus:hyperlinks:usstyle:sync"),
    ("WezTerm: modern features", "wezterm:RGB:usstyle:hyperlinks:clipboard:ccolour:cstyle:focus:sync:sixel"),
    ("foot: modern features", "foot*:RGB:usstyle:hyperlinks:clipboard:ccolour:cstyle:focus:sync:sixel"),
]
OVERRIDE_RECIPES = [
    ("True colour (Tc) for 256-colour terminals", "*256col*:Tc"),
    ("True colour (RGB) for xterm-like terminals", "xterm*:RGB"),
    ("Cursor shape changes (e.g. for vim/neovim)", r"*:Ss=\E[%p1%d q:Se=\E[2 q"),
    ("Undercurl", r"*:Smulx=\E[4::%p1%dm"),
    ("Coloured underlines",
     r"*:Setulc=\E[58::2::%p1%{65536}%/%d::%p1%{256}%/%{255}%&%d::%p1%{255}%&%d%;m"),
    ("Keep scrollback: disable alternate screen", "xterm*:smcup@:rmcup@"),
    ("Clipboard (OSC 52) where terminfo lacks Ms", r"xterm*:Ms=\E]52;%p1%s;%p2%s\007"),
]


def split_entry(entry: str) -> list[str]:
    """Split a terminal-features/overrides entry on ':'.

    As in tmux, '::' stands for a literal colon; parts come back unescaped.
    """
    parts, buf, i = [], [], 0
    while i < len(entry):
        if entry[i] == ":":
            if entry.startswith("::", i):
                buf.append(":")
                i += 2
                continue
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(entry[i])
        i += 1
    parts.append("".join(buf))
    return parts


def join_entry(parts: list[str]) -> str:
    """Inverse of split_entry: escape ':' as '::' and join with ':'."""
    return ":".join(p.replace(":", "::") for p in parts)


def parse_override(item: str):
    """'cap=value' -> (cap, 'set', value); 'cap@' -> (cap, 'unset', '');
    'cap' -> (cap, 'flag', '')."""
    if "=" in item:
        cap, value = item.split("=", 1)
        return cap, "set", value
    if item.endswith("@"):
        return item[:-1], "unset", ""
    return item, "flag", ""


def format_override(cap: str, mode: str, value: str = "") -> str:
    """Build one override item (unescaped; join_entry escapes colons)."""
    if mode == "unset":
        return f"{cap}@"
    if mode == "set":
        return f"{cap}={value}"
    return cap


def terminfo_dirs() -> list[Path]:
    dirs = []
    if os.environ.get("TERMINFO"):
        dirs.append(Path(os.environ["TERMINFO"]))
    dirs.append(Path.home() / ".terminfo")
    for d in os.environ.get("TERMINFO_DIRS", "").split(":"):
        if d:
            dirs.append(Path(d))
    dirs += [Path(p) for p in ("/etc/terminfo", "/lib/terminfo", "/usr/share/terminfo",
                               "/usr/lib/terminfo", "/usr/local/share/terminfo",
                               "/opt/homebrew/share/terminfo")]
    return dirs


def terminfo_available(name: str) -> bool | None:
    """True/False if the terminfo entry is (not) installed; None if unknown
    (no terminfo database found, e.g. on Windows)."""
    if not name:
        return False
    dirs = [d for d in terminfo_dirs() if d.is_dir()]
    if not dirs:
        return None
    for d in dirs:
        # Linux uses the first letter as directory; macOS uses its hex code.
        for sub in (name[0], f"{ord(name[0]):x}"):
            if (d / sub / name).exists():
                return True
    return False
