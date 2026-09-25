import time

import pytest

from tmux_config_generator.config import Config
from tmux_config_generator.options import OPTIONS, OPTIONS_BY_NAME
from tmux_config_generator.render.format import Context, expand, expand_time, trim
from tmux_config_generator.render.screen import (DEFAULT, SCENES, CellStyle,
                                                 apply_style, build_screen,
                                                 effective_values, runs)

NOW = time.strptime("2026-09-25 14:05:09", "%Y-%m-%d %H:%M:%S")


@pytest.fixture
def ctx():
    return Context({"session_name": "main", "window_index": "1",
                    "window_name": "vim", "window_flags": "*",
                    "pane_title": "host", "pane_in_mode": "0",
                    "window_bigger": "0"},
                   {"status-left-length": "10", "synchronize-panes": "off",
                    "status-left": "[#S]"},
                   windows=[{"window_index": "0", "window_name": "a", "window_active": "0"},
                            {"window_index": "1", "window_name": "b", "window_active": "1"}],
                   now=NOW)


@pytest.mark.parametrize("fmt,expected", [
    ("#S:#I:#W#F", "main:1:vim*"),
    ("##S", "##S"),  # escape kept until split_styles; shown as "#S"
    ("#{session_name}", "main"),
    ("#{?pane_in_mode,copy,normal}", "normal"),
    ("#{?#{==:#W,vim},yes,no}", "yes"),
    ("#{?synchronize-panes,sync,}", ""),
    ("#{=2:session_name}", "ma"),
    ("#{=-2:session_name}", "in"),
    ("#{=/2/…:window_name}", "vi…"),
    ("#{p6:session_name}|", "  main|"),
    ("#{p-6:session_name}|", "main  |"),
    ("#{&&:1,#{==:a,a}}#{||:0,0}#{!:0}", "101"),
    ("#{m:v*,#W}#{m/r:^x,vim}", "10"),
    ("#{E:status-left}", "[main]"),
    ("#{W:#{window_name} ,[#{window_name}]}", "a [b]"),
    ("#{l:#{session_name}}", "#{session_name}"),
    ("#(uptime)", "…"),
    ("#[fg=#FF0000]x", "#[fg=#FF0000]x"),
    ("#{?pane_in_mode,fg=yellow,#{?synchronize-panes,fg=red,fg=green}}", "fg=green"),
])
def test_expand(ctx, fmt, expected):
    assert expand(fmt, ctx) == expected


def test_expand_time(ctx):
    assert expand_time("%H:%M %d-%b-%y #S %%", ctx) == "14:05 25-Sep-26 main %"


def test_escaped_hash_shown_literally(ctx):
    rs = runs(expand("##S #S", ctx), DEFAULT)
    assert "".join(t for t, _s, _a in rs) == "#S main"


def test_trim_keeps_styles():
    assert trim("#[fg=red]abc#[default]def", 4) == "#[fg=red]abc#[default]d"


def test_apply_style():
    s, align = apply_style(DEFAULT, "fg=red,bg=colour33,bold,align=right")
    assert s == CellStyle(fg="red", bg="colour33", attrs=frozenset({"bright"}))
    assert align == "right"
    assert apply_style(s, "nobold,default")[0] == DEFAULT
    assert apply_style(s, "none")[0].attrs == frozenset()


def test_runs_split_and_style():
    base = CellStyle(bg="green")
    rs = runs("a#[fg=red]b#[default]c", base)
    assert [(t, s.fg, s.bg) for t, s, _a in rs] == [
        ("a", "default", "green"), ("b", "red", "green"), ("c", "default", "green")]


def text_of(screen):
    return ["".join(c for c, _s in row) for row in screen.cells]


def test_default_status_line():
    scr = build_screen(effective_values(Config()), "normal", 90, 22, now=NOW)
    status = text_of(scr)[-1]
    assert status.startswith("[main] 0:bash- 1:vim* 2:htop# 3:logs!")
    assert status.rstrip().endswith('"workstation" 14:05 25-Sep-26')


def test_status_options_applied():
    cfg = Config(values={"status-position": "top", "base-index": "1",
                         "status-justify": "right", "status-right": "",
                         "window-status-current-style": "bg=red"})
    scr = build_screen(effective_values(cfg), "normal", 90, 22, now=NOW)
    top = text_of(scr)[0]
    assert top.rstrip().endswith("1:bash- 2:vim* 3:htop# 4:logs!")
    x = top.index("2:vim*")
    assert scr.cells[0][x][1].bg == "red"


def test_custom_status_format():
    cfg = Config(values={"status-format": ["#[align=right]#S right"]})
    scr = build_screen(effective_values(cfg), "normal", 40, 10, now=NOW)
    assert text_of(scr)[-1] == " " * 30 + "main right"


def test_pane_border_status_and_lines():
    cfg = Config(values={"pane-border-status": "top", "pane-border-lines": "double"})
    scr = build_screen(effective_values(cfg), "normal", 90, 22, now=NOW)
    first = text_of(scr)[0]
    assert '0 "workstation"' in first and "═" in first and "╦" in first


@pytest.mark.parametrize("scene", [s for s, _ in SCENES])
def test_every_scene_with_defaults(scene):
    for cols, rows in [(90, 22), (40, 14), (160, 40)]:
        build_screen(effective_values(Config()), scene, cols, rows, now=NOW)


def test_every_choice_in_every_scene():
    for o in OPTIONS:
        for choice in o.choices:
            vals = effective_values(Config(values={o.name: choice}))
            for scene, _label in SCENES:
                build_screen(vals, scene, 60, 14, now=NOW)


def test_odd_values_do_not_crash():
    weird = {"status-left": "#{", "status-right": "#{?,}", "status-style": "fg=",
             "window-status-format": "#[", "status-left-length": "x",
             "pane-border-format": "#{=/x/y:pane_title}", "base-index": "-1",
             "status-format": ["", "#{W:}"], "status": "5"}
    vals = effective_values(Config(values=weird))
    for scene, _label in SCENES:
        build_screen(vals, scene, 50, 12, now=NOW)
    assert OPTIONS_BY_NAME["status"].choices[-1] == "5"
