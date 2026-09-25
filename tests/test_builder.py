import shutil

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from tmux_config_generator.config import Config, generate  # noqa: E402
from tmux_config_generator.format_vars import FORMAT_VARIABLES  # noqa: E402
from tmux_config_generator.options import OPTIONS_BY_NAME  # noqa: E402
from tmux_config_generator.presets import FORMAT_EXAMPLES  # noqa: E402
from tmux_config_generator.render.screen import (build_border_screen,  # noqa: E402
                                                 build_status_screen,
                                                 build_text_screen,
                                                 effective_values)
from tmux_config_generator.ui.format_builder import (FORMAT_OPTIONS, LOGIC,  # noqa: E402
                                                     _check)
from tmux_config_generator.validate import validate  # noqa: E402


def test_builder_options_exist():
    for name in list(FORMAT_OPTIONS) + list(FORMAT_EXAMPLES):
        assert name in OPTIONS_BY_NAME, name
    # every option typed "format" gets a builder
    assert {o for o, opt in OPTIONS_BY_NAME.items() if opt.type == "format"} <= set(FORMAT_OPTIONS)


def test_variables_table():
    names = [n for n, _a, _d in FORMAT_VARIABLES]
    assert len(names) > 150 and len(names) == len(set(names))
    assert ("session_name", "#S", "Name of session") in FORMAT_VARIABLES


@pytest.mark.parametrize("text,warn", [
    ("#{session_name}", None), ("#[fg=red]x#[default]", None),
    ("#{?a,#{b},c}", None), ("#{broken", "Unclosed #{ … }"),
    ("#[fg=red", "Unclosed #[ … ]"),
])
def test_check(text, warn):
    assert _check(text) == warn


def test_logic_templates_are_balanced():
    for _label, template, _desc in LOGIC:
        assert _check(template) is None, template


def test_examples_render():
    vals = effective_values(Config())
    for opt, examples in FORMAT_EXAMPLES.items():
        for _label, fmt in examples:
            v = dict(vals)
            v[opt] = [fmt] if opt == "status-format" else fmt
            build_status_screen(v, 80)
            build_border_screen(v, 80)
            build_text_screen(v, fmt, 80)


@pytest.mark.skipif(not shutil.which("tmux"), reason="tmux not installed")
def test_tmux_accepts_examples():
    lines = []
    for opt, examples in FORMAT_EXAMPLES.items():
        for _label, fmt in examples:
            value = [fmt] if opt == "status-format" else fmt
            lines.append(generate(Config(values={opt: value}), header=False))
    ok, msg = validate("".join(lines))
    assert ok, msg
