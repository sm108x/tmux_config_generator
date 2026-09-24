"""Key names: translating GTK key events to tmux key names, plus presets."""

from __future__ import annotations

# GDK key names -> tmux key names for non-printable keys.
_SPECIAL = {
    "Return": "Enter",
    "KP_Enter": "KPEnter",
    "Escape": "Escape",
    "Tab": "Tab",
    "ISO_Left_Tab": "BTab",
    "BackSpace": "BSpace",
    "Delete": "DC",
    "KP_Delete": "KP.",
    "Insert": "IC",
    "KP_Insert": "KP0",
    "Home": "Home",
    "KP_Home": "KP7",
    "End": "End",
    "KP_End": "KP1",
    "Page_Up": "PPage",
    "KP_Page_Up": "KP9",
    "Prior": "PPage",
    "Page_Down": "NPage",
    "KP_Page_Down": "KP3",
    "Next": "NPage",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
    "KP_Up": "KP8",
    "KP_Down": "KP2",
    "KP_Left": "KP4",
    "KP_Right": "KP6",
    "KP_Begin": "KP5",
    "space": "Space",
    "KP_Divide": "KP/",
    "KP_Multiply": "KP*",
    "KP_Subtract": "KP-",
    "KP_Add": "KP+",
    "KP_Decimal": "KP.",
}
_SPECIAL.update({f"KP_{i}": f"KP{i}" for i in range(10)})
_SPECIAL.update({f"F{i}": f"F{i}" for i in range(1, 25)})

_MODIFIER_KEYS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R", "Hyper_L", "Hyper_R",
    "ISO_Level3_Shift", "ISO_Level5_Shift", "Caps_Lock", "Num_Lock",
    "Mode_switch",
}


def event_to_tmux(keyname: str | None, char: str, ctrl: bool, alt: bool,
                  shift: bool) -> str | None:
    """Convert a key press to a tmux key name.

    *keyname* is the GDK key name (Gdk.keyval_name), *char* the printable
    character for the key (may be empty). Returns None for lone modifier
    presses and keys tmux cannot bind.
    """
    if not keyname or keyname in _MODIFIER_KEYS:
        return None
    if keyname == "ISO_Left_Tab":
        shift = False  # BTab already implies shift
    if keyname in _SPECIAL:
        base = _SPECIAL[keyname]
    elif char and char.isprintable() and not char.isspace():
        base = char
        if not ctrl:
            shift = False  # shift is already reflected in the character
        elif char.isalpha():
            base = char.lower()
    else:
        return None
    mods = ""
    if ctrl:
        mods += "C-"
    if alt:
        mods += "M-"
    if shift:
        mods += "S-"
    return mods + base


# Keys that cannot be captured from the keyboard, offered in a menu.
MOUSE_KEYS = [
    f"{event}{button}{where}"
    for event in ("MouseDown", "MouseUp", "MouseDrag", "MouseDragEnd",
                  "SecondClick", "DoubleClick", "TripleClick")
    for button in (1, 2, 3)
    for where in ("Pane", "Border", "Status", "StatusLeft", "StatusRight",
                  "StatusDefault")
] + [
    f"{wheel}{where}"
    for wheel in ("WheelUp", "WheelDown")
    for where in ("Pane", "Border", "Status", "StatusLeft", "StatusRight",
                  "StatusDefault")
]

SPECIAL_KEYS = [
    "Enter", "Escape", "Tab", "BTab", "Space", "BSpace", "IC", "DC", "Home",
    "End", "PPage", "NPage", "Up", "Down", "Left", "Right", "Any", "None",
] + [f"F{i}" for i in range(1, 13)] + [f"User{i}" for i in range(10)]
