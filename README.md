# tmux Config Generator

A cross-platform GTK 4 desktop app for building a `tmux.conf` without memorising the manual.

- **Every tmux option** (118 server, session, window and pane options from tmux 3.4) is sorted into category tabs: General, Input & Keys, Status Line, Window List, Windows, Panes, Copy Mode & Menus, Alerts, Terminal. Each option shows a description from the man page and a matching editor: a switch, dropdown, number field, colour picker, style editor, key-capture field or list editor.
- **Colour pickers:** each colour has a swatch button. It opens a grid of all 256 tmux palette colours (hover to see the name and hex), plus Default, Terminal, and a Custom colour… RGB picker. You can also type `red`, `colour33`, `#ff8800`, `ff8800`, `#f80` or `rgb(255,136,0)`; typed values are converted to tmux syntax and invalid ones are highlighted. Style options also have **fg** and **bg** swatches in the row, so you can set colours without opening the style editor.
- **Only the options you change are written.** Tick or untick an option to include or exclude it. The undo button resets it to the tmux default.
- **Key binding editor:**
  - Add, edit, duplicate and remove bindings in any key table (`prefix`, `root`/`-n`, `copy-mode`, `copy-mode-vi`, or a custom table).
  - Press the key you want in the capture dialog, or pick a mouse or special key from a list.
  - Choose from about 60 common commands, or look up any tmux command's usage.
  - Set `-r` (repeat) and `-N` (note).
  - Get warnings when a key is already bound or when it overrides a tmux default.
  - Browse all 260 tmux default bindings, then override or unbind them.
  - Unbind single keys or whole tables (`unbind -a`).
- **Visual preview:** the Status Line, Window List, Windows, Panes, Copy Mode & Menus and Alerts tabs show a live mock-up of a tmux client. It uses a sample session and redraws as you edit. It renders your formats (`#{...}`, conditionals, `#[...]` styles, strftime codes), colours and attributes; the status line layout (lengths, justification, multiple lines, custom `status-format`); and pane borders (line types, border status lines, arrows). Scenes cover normal use, copy mode (selection, search matches, mark), menus, popups, messages, the command prompt, clock mode, display-panes and alerts. The scene switches automatically when you edit a related option, and there's a light/dark terminal toggle.
- **Live preview** of the generated file.
- **Import** an existing `tmux.conf`. `set`, `bind` and `unbind` lines load into the editor. Everything else (hooks, `if-shell`, plugins…) is kept verbatim on the Custom tab.
- **Check with tmux**, if tmux is installed. The file is loaded on a throwaway tmux server (`tmux -L …`), so tmux reports bad option names and values. Custom-tab lines are only syntax-checked, never run.
- **Presets:** sensible defaults, a Ctrl-a prefix, intuitive splits, vim navigation, Alt-arrow pane switching, a reload key and a minimal dark status bar.
- Saving over an existing file first keeps a one-time `.bak` copy.

## Requirements

- Python 3.9+
- GTK 4.10+ and PyGObject

### Linux

```sh
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0
# Fedora
sudo dnf install python3-gobject gtk4
# Arch
sudo pacman -S python-gobject gtk4
```

### macOS (Homebrew)

```sh
brew install pygobject3 gtk4
```

### Windows (MSYS2 UCRT64 shell)

```sh
pacman -S mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-python-gobject
```

tmux doesn't run natively on Windows, but you can still generate configs there, for example to copy into WSL. The "Check with tmux" button needs `tmux` on `PATH`.

## Running

```sh
python3 -m tmux_config_generator
```

Or install it to get a `tmux-config-generator` launcher:

```sh
pip install --no-build-isolation .   # uses the system PyGObject
```

You can also pass a file to open: `python3 -m tmux_config_generator ~/.tmux.conf`.

### Adding it to your application menu

```sh
python3 -m tmux_config_generator --install-launcher     # or: tmux-config-generator --install-launcher
python3 -m tmux_config_generator --uninstall-launcher   # remove it again
```

This registers the app for the current user only, and needs no admin rights:

| Platform | What gets installed |
|---|---|
| Linux / BSD | `.desktop` entry, icons (hicolor theme) and AppStream metainfo under `~/.local/share` (or `$XDG_DATA_HOME`) |
| Windows | Start Menu shortcut with the app icon |
| macOS | `~/Applications/tmux Config Generator.app` |

The launcher runs the Python interpreter you used for `--install-launcher`, or the `tmux-config-generator` command if it's on `PATH`. Re-run it if you move the source checkout or change Python environments.

For distro packaging, the static files are in `tmux_config_generator/data/`: the desktop file, metainfo, and icons as SVG, PNG, `.ico` and `.icns`. To regenerate the icons from their source, run `python3 tools/build_icons.py` (needs Inkscape).

Shortcuts:

| Shortcut | Action |
|---|---|
| Ctrl+O | Open |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+Shift+C | Copy to clipboard |
| Ctrl+R | Check with tmux |
| Ctrl+F | Filter options |
| Ctrl+N | New |

After saving, reload a running tmux with `tmux source-file ~/.tmux.conf`.

## Development

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

The tests cover quoting, generation, round-trip parsing and key-name translation. When tmux is installed, they also check that tmux accepts every option default, every dropdown choice and a config built from all presets.

Layout:

| Path | Purpose |
|---|---|
| `tmux_config_generator/options.py` | Option catalogue (scope, category, type, default, choices, description) |
| `tmux_config_generator/config.py` | Config model, `tmux.conf` generation and parsing |
| `tmux_config_generator/keys.py` | GTK key event → tmux key name |
| `tmux_config_generator/styles.py` | Style strings and colour parsing |
| `tmux_config_generator/default_bindings.py`, `commands.py` | tmux 3.4 default key bindings and command reference |
| `tmux_config_generator/presets.py` | Command presets and quick-start presets |
| `tmux_config_generator/render/` | tmux format expander and screen mock-up used by the visual preview |
| `tmux_config_generator/validate.py` | Checks a config with a real tmux binary |
| `tmux_config_generator/launcher.py` | Adds the app to the desktop's application menu |
| `tmux_config_generator/data/` | Desktop file, AppStream metainfo, icons |
| `tools/build_icons.py` | Generates the icons |
| `tmux_config_generator/ui/` | GTK 4 interface |

Array options (`update-environment`, `terminal-features`, `status-format`, …) are written by clearing the array and then setting indexed entries (`set -g name[0] …`), or with `set -a` in "append to tmux defaults" mode. Writing them this way stops tmux from splitting values on commas.

## License

Copyright (C) 2026 Stephen Martina

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more details.
