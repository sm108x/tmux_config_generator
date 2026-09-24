"""Application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from .ui.window import MainWindow  # noqa: E402

APP_ID = "io.github.tmux_config_generator"


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        win = self.props.active_window or MainWindow(self)
        win.present()


def main(argv=None) -> int:
    if Gtk.get_major_version() == 4 and Gtk.get_minor_version() < 10:
        print("tmux-config-generator needs GTK 4.10 or newer.", file=sys.stderr)
        return 1
    return Application().run(argv if argv is not None else sys.argv)
