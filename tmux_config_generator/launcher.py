"""Register the app with the desktop's application menu (per user).

Linux/BSD: freedesktop .desktop entry, icons and AppStream metainfo under
$XDG_DATA_HOME. Windows: a Start Menu shortcut. macOS: a small .app bundle
in ~/Applications.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ID = "io.github.sm108x.TmuxConfigGenerator"
APP_NAME = "tmux Config Generator"
DATA_DIR = Path(__file__).resolve().parent / "data"
ICON_DIR = DATA_DIR / "icons"
# Directory that must be on sys.path for `-m tmux_config_generator`.
PACKAGE_PARENT = Path(__file__).resolve().parent.parent


def launch_command(gui: bool = False) -> list[str]:
    """Command that starts the app from a menu.

    Prefers the installed `tmux-config-generator` script; otherwise runs the
    package with the current interpreter (pythonw on Windows when *gui*).
    """
    script = shutil.which("tmux-config-generator")
    if script:
        return [script]
    python = Path(sys.executable)
    if gui and os.name == "nt":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.exists():
            python = pythonw
    return [str(python), "-m", "tmux_config_generator"]


# -- freedesktop ----------------------------------------------------------------


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _desktop_quote(arg: str) -> str:
    if not any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
    escaped = escaped.replace("$", "\\$")
    return f'"{escaped}"'


def desktop_entry() -> str:
    """The .desktop template with Exec (and Path) pointing at this install."""
    cmd = launch_command()
    exec_line = " ".join(_desktop_quote(a) for a in cmd).replace("%", "%%") + " %f"
    lines = []
    for line in (DATA_DIR / f"{APP_ID}.desktop").read_text().splitlines():
        if line.startswith("Exec="):
            line = f"Exec={exec_line}"
            if cmd[1:2] == ["-m"]:
                lines.append(line)
                line = f"Path={PACKAGE_PARENT}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _freedesktop_targets():
    base = _xdg_data_home()
    targets = [(base / "applications" / f"{APP_ID}.desktop", None),
               (base / "metainfo" / f"{APP_ID}.metainfo.xml",
                DATA_DIR / f"{APP_ID}.metainfo.xml")]
    for src in sorted((ICON_DIR / "hicolor").glob("*/apps/*")):
        targets.append((base / "icons" / src.relative_to(ICON_DIR), src))
    return targets


def _refresh_freedesktop_caches():
    base = _xdg_data_home()
    for cmd in (["update-desktop-database", str(base / "applications")],
                ["gtk-update-icon-cache", "-f", "-t", str(base / "icons" / "hicolor")],
                ["gtk4-update-icon-cache", "-f", "-t", str(base / "icons" / "hicolor")]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, capture_output=True)


def install_freedesktop() -> list[Path]:
    written = []
    for dest, src in _freedesktop_targets():
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src is None:
            dest.write_text(desktop_entry())
        else:
            shutil.copyfile(src, dest)
        written.append(dest)
    _refresh_freedesktop_caches()
    return written


def uninstall_freedesktop() -> list[Path]:
    removed = []
    for dest, _src in _freedesktop_targets():
        if dest.exists():
            dest.unlink()
            removed.append(dest)
    _refresh_freedesktop_caches()
    return removed


# -- Windows --------------------------------------------------------------------


def _start_menu_shortcut() -> Path:
    appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return (appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / f"{APP_NAME}.lnk")


_PS_SHORTCUT = r"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TCG_LNK)
$s.TargetPath = $env:TCG_TARGET
$s.Arguments = $env:TCG_ARGS
$s.WorkingDirectory = $env:TCG_CWD
$s.IconLocation = $env:TCG_ICON + ",0"
$s.Description = $env:TCG_DESC
$s.Save()
"""


def install_windows() -> list[Path]:
    lnk = _start_menu_shortcut()
    lnk.parent.mkdir(parents=True, exist_ok=True)
    cmd = launch_command(gui=True)
    env = dict(os.environ,
               TCG_LNK=str(lnk), TCG_TARGET=cmd[0],
               TCG_ARGS=subprocess.list2cmdline(cmd[1:]),
               TCG_CWD=str(PACKAGE_PARENT),
               TCG_ICON=str(ICON_DIR / f"{APP_ID}.ico"),
               TCG_DESC="Build a tmux.conf with a GUI")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-Command", _PS_SHORTCUT],
                   env=env, check=True, capture_output=True)
    return [lnk]


def uninstall_windows() -> list[Path]:
    lnk = _start_menu_shortcut()
    if lnk.exists():
        lnk.unlink()
        return [lnk]
    return []


# -- macOS ----------------------------------------------------------------------


def _app_bundle() -> Path:
    return Path.home() / "Applications" / f"{APP_NAME}.app"


_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{name}</string>
  <key>CFBundleDisplayName</key><string>{name}</string>
  <key>CFBundleIdentifier</key><string>{app_id}</string>
  <key>CFBundleExecutable</key><string>tmux-config-generator</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""


def install_macos() -> list[Path]:
    from . import __version__
    app = _app_bundle()
    if app.exists():
        shutil.rmtree(app)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir()
    (app / "Contents" / "Info.plist").write_text(_INFO_PLIST.format(
        name=APP_NAME, app_id=APP_ID, version=__version__))
    shutil.copyfile(ICON_DIR / f"{APP_ID}.icns",
                    app / "Contents" / "Resources" / "AppIcon.icns")
    import shlex
    script = app / "Contents" / "MacOS" / "tmux-config-generator"
    # Apps started from Finder get a minimal PATH; add Homebrew's.
    script.write_text(
        "#!/bin/sh\n"
        'export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\n'
        f"cd {shlex.quote(str(PACKAGE_PARENT))}\n"
        f'exec {" ".join(shlex.quote(a) for a in launch_command())} "$@"\n')
    script.chmod(0o755)
    return [app]


def uninstall_macos() -> list[Path]:
    app = _app_bundle()
    if app.exists():
        shutil.rmtree(app)
        return [app]
    return []


# -- dispatch -------------------------------------------------------------------


def install() -> list[Path]:
    if os.name == "nt":
        return install_windows()
    if sys.platform == "darwin":
        return install_macos()
    return install_freedesktop()


def uninstall() -> list[Path]:
    if os.name == "nt":
        return uninstall_windows()
    if sys.platform == "darwin":
        return uninstall_macos()
    return uninstall_freedesktop()


def main(action: str) -> int:
    try:
        paths = install() if action == "install" else uninstall()
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Failed to {action} the launcher: {e}", file=sys.stderr)
        return 1
    verb = "Installed" if action == "install" else "Removed"
    if not paths:
        print("Nothing to remove.")
    for p in paths:
        print(f"{verb} {p}")
    return 0
