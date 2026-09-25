"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from .launcher import APP_ID, ICON_DIR  # noqa: E402
from .ui.window import MainWindow  # noqa: E402

USAGE = """\
usage: tmux-config-generator [FILE]
       tmux-config-generator --install-launcher | --uninstall-launcher

  FILE                  tmux.conf to open
  --install-launcher    add the app to your desktop's application menu
                        (freedesktop menu, Windows Start Menu, ~/Applications)
  --uninstall-launcher  remove it again
"""


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.NON_UNIQUE
                         | Gio.ApplicationFlags.HANDLES_OPEN)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # Find the bundled icon even when running from a source checkout.
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(
            str(ICON_DIR))
        Gtk.Window.set_default_icon_name(APP_ID)

    def do_activate(self):
        win = self.props.active_window or MainWindow(self)
        win.present()

    def do_open(self, files, _n_files, _hint):
        for gfile in files:
            win = MainWindow(self)
            if gfile.get_path():
                win.load_path(Path(gfile.get_path()))
            win.present()


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv)
    if "-h" in argv[1:] or "--help" in argv[1:]:
        print(USAGE, end="")
        return 0
    for flag, action in (("--install-launcher", "install"),
                         ("--uninstall-launcher", "uninstall")):
        if flag in argv[1:]:
            from .launcher import main as launcher_main
            return launcher_main(action)
    if Gtk.get_major_version() == 4 and Gtk.get_minor_version() < 10:
        print("tmux-config-generator needs GTK 4.10 or newer.", file=sys.stderr)
        return 1
    return Application().run(argv)
