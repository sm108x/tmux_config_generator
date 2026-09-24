import shutil

import pytest

from tmux_config_generator.config import (Binding, Config, Unbind, generate,
                                          parse, quote, tokenize)
from tmux_config_generator.default_bindings import DEFAULT_BINDINGS
from tmux_config_generator.keys import event_to_tmux
from tmux_config_generator.options import OPTIONS, OPTIONS_BY_NAME
from tmux_config_generator.presets import QUICK_PRESETS
from tmux_config_generator.styles import colour_to_rgb, parse_style
from tmux_config_generator.validate import validate

needs_tmux = pytest.mark.skipif(not shutil.which("tmux"), reason="tmux not installed")


@pytest.mark.parametrize("value", [
    "", "on", "C-a", "#{pane_current_path}", "it's", 'say "hi" $HOME \\x',
    "a b", ";", "#", "~", "{", "-", "'", '"', "%H:%M",
])
def test_quote_round_trips(value):
    tokens = tokenize(f"x {quote(value)}")
    assert [t.text for t in tokens] == ["x", value]


def test_generate_scopes():
    cfg = Config(values={"escape-time": "10", "mouse": "on",
                         "mode-keys": "vi", "synchronize-panes": "on"})
    text = generate(cfg, header=False)
    assert "set -s escape-time 10" in text
    assert "set -g mouse on" in text
    assert "set -gw mode-keys vi" in text
    assert "set -gw synchronize-panes on" in text


def test_list_replace_and_append():
    cfg = Config(values={"update-environment": ["A", "B"],
                         "terminal-features": ["xterm*:RGB"]},
                 list_append={"terminal-features"})
    text = generate(cfg, header=False)
    assert "set -g update-environment ''\n" in text
    assert "set -g update-environment[1] B" in text
    assert "set -as terminal-features xterm*:RGB" in text


def test_bindings_render():
    assert Binding("|", 'split-window -h').render() == "bind | split-window -h"
    assert Binding("M-Left", "select-pane -L", table="root").render() == \
        "bind -n M-Left select-pane -L"
    assert Binding("v", "send -X begin-selection", table="copy-mode-vi",
                   repeat=True, note="Select").render() == \
        "bind -r -N Select -T copy-mode-vi v send -X begin-selection"
    assert Unbind("C-b").render() == "unbind C-b"
    assert Unbind("", "root").render() == "unbind -a -n"
    assert Unbind('"').render() == "unbind '\"'"


def full_config() -> Config:
    cfg = Config()
    for _label, _desc, values, bindings, unbinds in QUICK_PRESETS:
        cfg.values.update(values)
        cfg.bindings += [Binding(k, c, t, r) for t, k, r, c in bindings]
        cfg.unbinds += [Unbind(k, t) for t, k in unbinds]
    cfg.values["status-format"] = ["#[align=left]#S, #W", "second line"]
    cfg.values["word-separators"] = " -_@'\"$"
    cfg.values["user-keys"] = ["\\e[1;5A"]
    cfg.bindings.append(Binding('"', 'display "quote; key"'))
    cfg.bindings.append(Binding("F5", "if -F '#{pane_in_mode}' { send q } { copy-mode }"))
    cfg.extra = "set-hook -g after-new-window 'display hi'\nset -g @plugin 'tmux-plugins/tpm'"
    return cfg


def test_parse_round_trip():
    cfg = full_config()
    text = generate(cfg)
    back = parse(text)
    assert back.values == cfg.values
    key = lambda b: (b.table, b.key)  # noqa: E731 - generate groups by table
    assert sorted(back.bindings, key=key) == sorted(cfg.bindings, key=key)
    assert back.unbinds == cfg.unbinds
    assert generate(back) == text


def test_parse_foreign_config():
    text = """
# my config
set-option -g prefix C-a
setw -g mode-keys vi
set -g default-terminal "screen-256color"   # trailing comment
set -ga terminal-overrides ",xterm-256color:Tc"
bind-key -n C-h select-pane -L
bind r source-file ~/.tmux.conf \\; display "Reloaded"
unbind-key C-b
if-shell "test -f ~/.local.conf" "source ~/.local.conf"
set -g status-left "#[fg=green]#S" \\; set -g status-right ""
"""
    cfg = parse(text)
    assert cfg.values["prefix"] == "C-a"
    assert cfg.values["mode-keys"] == "vi"
    assert cfg.values["default-terminal"] == "screen-256color"
    assert cfg.values["terminal-overrides"] == [",xterm-256color:Tc"]
    assert "terminal-overrides" in cfg.list_append
    assert cfg.bindings[0] == Binding("C-h", "select-pane -L", "root")
    assert cfg.bindings[1].command == 'source-file ~/.tmux.conf \\; display "Reloaded"'
    assert cfg.unbinds == [Unbind("C-b")]
    assert "if-shell" in cfg.extra and "# my config" in cfg.extra
    assert "status-left" in cfg.extra  # chained commands kept verbatim


def test_default_bindings_loaded():
    assert len(DEFAULT_BINDINGS) > 200
    assert ("prefix", "c", False, "new-window", "Create a new window") in DEFAULT_BINDINGS


def test_options_catalogue():
    assert len(OPTIONS) == len(OPTIONS_BY_NAME) > 100
    for o in OPTIONS:
        assert o.description
        if o.type in ("choice", "flag"):
            assert o.default in o.choices, o.name


@pytest.mark.parametrize("args,expected", [
    (("a", "a", False, False, False), "a"),
    (("A", "A", False, False, True), "A"),
    (("a", "a", True, False, False), "C-a"),
    (("A", "A", True, False, True), "C-S-a"),
    (("percent", "%", False, False, True), "%"),
    (("Left", "", False, True, False), "M-Left"),
    (("Up", "", True, False, True), "C-S-Up"),
    (("ISO_Left_Tab", "", False, False, True), "BTab"),
    (("space", " ", True, False, False), "C-Space"),
    (("Page_Up", "", False, False, False), "PPage"),
    (("F5", "", False, False, False), "F5"),
    (("Control_L", "", True, False, False), None),
])
def test_key_names(args, expected):
    assert event_to_tmux(*args) == expected


def test_styles():
    s = parse_style("bg=colour235,fg=#ff0000,bold,noitalics")
    assert s.bg == "colour235" and "bright" in s.attrs and "italics" in s.noattrs
    assert s.to_string() == "fg=#ff0000,bg=colour235,bright,noitalics"
    assert parse_style("#{?pane_in_mode,fg=red,fg=green}") is None
    assert colour_to_rgb("colour196") == (255, 0, 0)
    assert colour_to_rgb("brightblue") == (0, 0, 255)
    assert colour_to_rgb("default") is None


@needs_tmux
def test_tmux_accepts_generated_config():
    ok, msg = validate(generate(full_config()))
    assert ok, msg


@needs_tmux
def test_tmux_accepts_every_option_default():
    cfg = Config()
    for o in OPTIONS:
        if o.type == "list":
            cfg.values[o.name] = list(o.default)
        elif o.default != "":
            cfg.values[o.name] = o.default
    ok, msg = validate(generate(cfg))
    assert ok, msg


@needs_tmux
def test_tmux_rejects_bad_config():
    ok, msg = validate("set -g not-an-option 1\n")
    assert not ok and "not-an-option" in msg
    ok, msg = validate("bind x { unterminated\n", "")
    assert not ok


@needs_tmux
def test_tmux_accepts_every_choice():
    lines = []
    for o in OPTIONS:
        for choice in o.choices:
            lines.append(generate(Config(values={o.name: choice}), header=False))
    ok, msg = validate("".join(lines))
    assert ok, msg
