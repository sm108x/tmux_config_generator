import shutil

import pytest

from tmux_config_generator import terminal
from tmux_config_generator.config import Config, generate
from tmux_config_generator.terminal import (CAPABILITIES, DEFAULT_TERMINALS,
                                            FEATURE_RECIPES, FEATURES,
                                            OVERRIDE_RECIPES, join_entry,
                                            parse_override, split_entry)
from tmux_config_generator.validate import validate


@pytest.mark.parametrize("entry,parts", [
    ("xterm*:RGB", ["xterm*", "RGB"]),
    (r"*:Smulx=\E[4::%p1%dm", ["*", r"Smulx=\E[4:%p1%dm"]),
    ("*:a=x::y::z:b@", ["*", "a=x:y:z", "b@"]),
    ("*", ["*"]),
])
def test_split_join_round_trip(entry, parts):
    assert split_entry(entry) == parts
    assert join_entry(parts) == entry


def test_parse_override():
    assert parse_override(r"Ss=\E[%p1%d q") == ("Ss", "set", r"\E[%p1%d q")
    assert parse_override("smcup@") == ("smcup", "unset", "")
    assert parse_override("Tc") == ("Tc", "flag", "")


def test_recipes_use_known_names():
    features = {f for f, _d in FEATURES}
    caps = {c for c, *_ in CAPABILITIES}
    for _label, entry in FEATURE_RECIPES:
        assert set(split_entry(entry)[1:]) <= features, entry
    for _label, entry in OVERRIDE_RECIPES:
        assert {parse_override(i)[0] for i in split_entry(entry)[1:]} <= caps, entry
    assert len({f for f, _d in FEATURES}) == 19


def test_terminfo_lookup(tmp_path, monkeypatch):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "tmux-256color").write_bytes(b"")
    (tmp_path / "73").mkdir()  # macOS-style hex directory for 's'
    (tmp_path / "73" / "screen-256color").write_bytes(b"")
    monkeypatch.setattr(terminal, "terminfo_dirs", lambda: [tmp_path])
    assert terminal.terminfo_available("tmux-256color") is True
    assert terminal.terminfo_available("screen-256color") is True
    assert terminal.terminfo_available("nope") is False
    monkeypatch.setattr(terminal, "terminfo_dirs", lambda: [tmp_path / "missing"])
    assert terminal.terminfo_available("tmux-256color") is None


@pytest.mark.skipif(not shutil.which("tmux"), reason="tmux not installed")
def test_tmux_accepts_recipes_and_terminals():
    cfg = Config(values={
        "terminal-features": [e for _l, e in FEATURE_RECIPES],
        "terminal-overrides": [e for _l, e in OVERRIDE_RECIPES],
    })
    text = generate(cfg, header=False)
    text += "".join(generate(Config(values={"default-terminal": t}), header=False)
                    for t, _d in DEFAULT_TERMINALS)
    ok, msg = validate(text)
    assert ok, msg
