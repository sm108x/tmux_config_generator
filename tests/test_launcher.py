import configparser
import shutil
import subprocess

import pytest

from tmux_config_generator import launcher


def test_desktop_quote():
    assert launcher._desktop_quote("/usr/bin/python3") == "/usr/bin/python3"
    assert launcher._desktop_quote("/opt/my apps/py") == '"/opt/my apps/py"'
    assert launcher._desktop_quote('a"b$c') == '"a\\"b\\$c"'


def test_desktop_entry_points_at_this_install(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: None)
    entry = configparser.ConfigParser(interpolation=None)
    entry.read_string(launcher.desktop_entry())
    d = entry["Desktop Entry"]
    assert d["Exec"].endswith(" -m tmux_config_generator %f")
    assert d["Path"] == str(launcher.PACKAGE_PARENT)
    assert d["Icon"] == launcher.APP_ID

    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "/usr/bin/tmux-config-generator")
    entry = configparser.ConfigParser(interpolation=None)
    entry.read_string(launcher.desktop_entry())
    assert entry["Desktop Entry"]["Exec"] == "/usr/bin/tmux-config-generator %f"
    assert "Path" not in entry["Desktop Entry"]


def test_bundled_data_present():
    assert (launcher.DATA_DIR / f"{launcher.APP_ID}.desktop").exists()
    assert (launcher.ICON_DIR / f"{launcher.APP_ID}.ico").read_bytes()[:4] == b"\0\0\1\0"
    assert (launcher.ICON_DIR / f"{launcher.APP_ID}.icns").read_bytes()[:4] == b"icns"
    assert (launcher.ICON_DIR / "hicolor" / "scalable" / "apps" / f"{launcher.APP_ID}.svg").exists()


def test_freedesktop_install_uninstall(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    written = launcher.install_freedesktop()
    desktop = tmp_path / "applications" / f"{launcher.APP_ID}.desktop"
    assert desktop in written
    assert (tmp_path / "icons/hicolor/scalable/apps" / f"{launcher.APP_ID}.svg").exists()
    if shutil.which("desktop-file-validate"):
        subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    removed = launcher.uninstall_freedesktop()
    assert set(removed) == set(written)
    assert not desktop.exists()


def test_macos_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    app = launcher.install_macos()[0]
    assert (app / "Contents/Resources/AppIcon.icns").exists()
    script = app / "Contents/MacOS/tmux-config-generator"
    assert script.stat().st_mode & 0o111
    assert launcher.uninstall_macos() == [app] and not app.exists()


@pytest.mark.skipif(not shutil.which("desktop-file-validate"), reason="no validator")
def test_template_desktop_file_valid():
    subprocess.run(["desktop-file-validate",
                    str(launcher.DATA_DIR / f"{launcher.APP_ID}.desktop")], check=True)
