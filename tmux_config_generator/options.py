"""Catalogue of tmux options (tmux 3.4), grouped into UI categories.

Descriptions are condensed from the tmux(1) manual page.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Option scopes and the `set-option` flags used to write them globally.
SCOPE_FLAGS = {
    "server": "-s",
    "session": "-g",
    "window": "-gw",
    "pane": "-gw",
}

# Value types understood by the UI and the generator.
#   flag    on/off
#   choice  one of a fixed set of words
#   number  integer
#   string  free text
#   format  free text containing #{...} formats
#   colour  a tmux colour (name, colourN or #rrggbb)
#   style   a tmux style string (fg=..,bg=..,attributes)
#   key     a tmux key name (C-a, M-x, F1, ...)
#   list    an array option; value is a list of strings
TYPES = ("flag", "choice", "number", "string", "format", "colour", "style", "key", "list")

CATEGORIES = [
    ("general", "General"),
    ("input", "Input & Keys"),
    ("status", "Status Line"),
    ("winlist", "Window List"),
    ("windows", "Windows"),
    ("panes", "Panes"),
    ("copy", "Copy Mode & Menus"),
    ("alerts", "Alerts"),
    ("terminal", "Terminal"),
]


@dataclass(frozen=True)
class Option:
    name: str
    scope: str
    category: str
    type: str
    default: object
    min: int = 0
    max: int = 2**31 - 1
    choices: tuple = ()
    description: str = ""

    def __post_init__(self):
        assert self.scope in SCOPE_FLAGS, self.name
        assert self.type in TYPES, self.name
        if self.type == "flag":
            object.__setattr__(self, "choices", ("off", "on"))
        elif self.choices:
            object.__setattr__(self, "choices", tuple(self.choices))

    @property
    def flags(self) -> str:
        return SCOPE_FLAGS[self.scope]


OPTIONS: list[Option] = [
    Option('default-shell', 'session', 'general', 'string', '',
           description='Specify the default shell. This is used as the login shell for new windows when the default-command option is set to empty, and must be the full path of the executable. When started tmux tries to set a default value from the first suitable of the SHELL environment variable, the shell returned by getpwuid(3), or /bin/sh.'),
    Option('default-command', 'session', 'general', 'string', '',
           description='Set the command used for new windows (if not specified when the window is created) to shell-command, which may be any sh(1) command. The default is an empty string, which instructs tmux to create a login shell using the value of the default-shell option.'),
    Option('base-index', 'session', 'general', 'number', '0', min=0, max=99,
           description='Set the base index from which an unused index should be searched when a new window is created. The default is zero.'),
    Option('pane-base-index', 'window', 'general', 'number', '0', min=0, max=99,
           description='Like base-index, but set the starting index for pane numbers.'),
    Option('renumber-windows', 'session', 'general', 'flag', 'off',
           description='If on, when a window is closed in a session, automatically renumber the other windows in numerical order. This respects the base-index option if it has been set. If off, do not renumber the windows.'),
    Option('history-limit', 'session', 'general', 'number', '2000', min=0, max=10000000,
           description='Set the maximum number of lines held in window history. This setting applies only to new windows - existing window histories are not resized and retain the limit at the point they were created.'),
    Option('buffer-limit', 'server', 'general', 'number', '50', min=1, max=100000,
           description='Set the number of buffers; as new buffers are added to the top of the stack, old ones are removed from the bottom if necessary to maintain this maximum length.'),
    Option('escape-time', 'server', 'general', 'number', '500', min=0, max=10000,
           description='Set the time in milliseconds for which tmux waits after an escape is input to determine if it is part of a function or meta key sequences. The default is 500 milliseconds.'),
    Option('exit-empty', 'server', 'general', 'flag', 'on',
           description='If enabled (the default), the server will exit when there are no active sessions.'),
    Option('exit-unattached', 'server', 'general', 'flag', 'off',
           description='If enabled, the server will exit when there are no attached clients.'),
    Option('destroy-unattached', 'session', 'general', 'choice', 'off', choices=['off', 'on', 'keep-last', 'keep-group'],
           description='If on, destroy the session after the last client has detached. If off (the default), leave the session orphaned. If keep-last, destroy the session only if it is in a group and has other sessions in that group.'),
    Option('detach-on-destroy', 'session', 'general', 'choice', 'on', choices=['off', 'on', 'no-detached', 'previous', 'next'],
           description='If on (the default), the client is detached when the session it is attached to is destroyed. If off, the client is switched to the most recently active of the remaining sessions.'),
    Option('default-size', 'session', 'general', 'string', '80x24',
           description="Set the default size of new windows when the window-size option is set to manual or when a session is created with new-session -d. The value is the width and height separated by an 'x' character. The default is 80x24."),
    Option('editor', 'server', 'general', 'string', 'vi',
           description='Set the command used when tmux runs an editor.'),
    Option('lock-after-time', 'session', 'general', 'number', '0', min=0, max=1000000,
           description='Lock the session (like the lock-session command) after number seconds of inactivity. The default is not to lock (set to 0).'),
    Option('lock-command', 'session', 'general', 'string', 'lock -np',
           description='Command to run when locking each client. The default is to run lock(1) with -np.'),
    Option('word-separators', 'session', 'general', 'string', '!"#$%&\'()*+,-./:;<=>?@[\\]^`{|}~',
           description="Sets the session's conception of what characters are considered word separators, for the purposes of the next and previous word commands in copy mode."),
    Option('message-limit', 'server', 'general', 'number', '1000', min=0, max=1000000,
           description='Set the number of error or information messages to save in the message log for each client.'),
    Option('prompt-history-limit', 'server', 'general', 'number', '100', min=0, max=1000000,
           description='Set the number of history items to save in the history file for each type of command prompt.'),
    Option('history-file', 'server', 'general', 'string', '',
           description='If not empty, a file to which tmux will write command prompt history on exit and load it from on start.'),
    Option('update-environment', 'session', 'general', 'list', ['DISPLAY', 'KRB5CCNAME', 'SSH_ASKPASS', 'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'SSH_CONNECTION', 'WINDOWID', 'XAUTHORITY'],
           description='Set list of environment variables to be copied into the session environment when a new session is created or an existing session is attached. Any variables that do not exist in the source environment are set to be removed from the session environment (as if -r was given to the set-environment command).'),
    Option('command-alias', 'server', 'general', 'list', ['split-pane=split-window', 'splitp=split-window', 'server-info=show-messages -JT', 'info=show-messages -JT', 'choose-window=choose-tree -w', 'choose-session=choose-tree -s'],
           description='This is an array of custom aliases for commands. If an unknown command matches name, it is replaced with value. Enter entries as name=value, e.g. zoom=resize-pane -Z.'),
    Option('prefix', 'session', 'input', 'key', 'C-b',
           description='Set the key accepted as a prefix key. In addition to the standard keys described under "KEY BINDINGS", prefix can be set to the special key \'None\' to set no prefix.'),
    Option('prefix2', 'session', 'input', 'key', 'None',
           description="Set a secondary key accepted as a prefix key. Like prefix, prefix2 can be set to 'None'."),
    Option('key-table', 'session', 'input', 'string', 'root',
           description='Set the default key table to key-table instead of root.'),
    Option('repeat-time', 'session', 'input', 'number', '500', min=0, max=100000,
           description='Allow multiple commands to be entered without pressing the prefix-key again in the specified time milliseconds (the default is 500). Whether a key repeats may be set when it is bound using the -r flag to bind-key. Repeat is enabled for the default keys bound to the resize-pane command.'),
    Option('assume-paste-time', 'session', 'input', 'number', '1', min=0, max=10000,
           description='If keys are entered faster than one in milliseconds, they are assumed to have been pasted rather than typed and tmux key bindings are not processed. The default is one millisecond and zero disables.'),
    Option('mouse', 'session', 'input', 'flag', 'off',
           description='If on, tmux captures the mouse and allows mouse events to be bound as key bindings. See the "MOUSE SUPPORT" section for details.'),
    Option('status-keys', 'session', 'input', 'choice', 'emacs', choices=['emacs', 'vi'],
           description="Use vi or emacs-style key bindings in the status line, for example at the command prompt. The default is emacs, unless the VISUAL or EDITOR environment variables are set and contain the string 'vi'."),
    Option('mode-keys', 'window', 'input', 'choice', 'emacs', choices=['emacs', 'vi'],
           description="Use vi or emacs-style key bindings in copy mode. The default is emacs, unless VISUAL or EDITOR contains 'vi'."),
    Option('backspace', 'server', 'input', 'key', 'C-?',
           description='Set the key sent by tmux for backspace.'),
    Option('extended-keys', 'server', 'input', 'choice', 'off', choices=['off', 'on', 'always'],
           description='When on or always, the escape sequence to enable extended keys is sent to the terminal, if tmux knows that it is supported. tmux always recognises extended keys itself. If this option is on, tmux will only forward extended keys to applications when they request them; if always, tmux will always forward the keys.'),
    Option('focus-events', 'server', 'input', 'flag', 'off',
           description='When enabled, focus events are requested from the terminal if supported and passed through to applications running in tmux. Attached clients should be detached and attached again after changing this option.'),
    Option('user-keys', 'server', 'input', 'list', [],
           description="Set list of user-defined key escape sequences. Each item is associated with a key named 'User0', 'User1', and so on."),
    Option('status', 'session', 'status', 'choice', 'on', choices=['off', 'on', '2', '3', '4', '5'],
           description='Show or hide the status line or specify its size. Using on gives a status line one row in height; 2, 3, 4 or 5 more rows.'),
    Option('status-position', 'session', 'status', 'choice', 'bottom', choices=['top', 'bottom'],
           description='Set the position of the status line.'),
    Option('status-interval', 'session', 'status', 'number', '15', min=0, max=86400,
           description='Update the status line every interval seconds. By default, updates will occur every 15 seconds. A setting of zero disables redrawing at interval.'),
    Option('status-justify', 'session', 'status', 'choice', 'left', choices=['left', 'centre', 'right', 'absolute-centre'],
           description='Set the position of the window list in the status line: left, centre or right. centre puts the window list in the relative centre of the available free space; absolute-centre uses the centre of the entire horizontal space.'),
    Option('status-style', 'session', 'status', 'style', 'bg=green,fg=black',
           description='Set status line style. For how to specify style, see the "STYLES" section.'),
    Option('status-left', 'session', 'status', 'format', '[#{session_name}] ',
           description='Display string (by default the session name) to the left of the status line. string will be passed through strftime(3). Also see the "FORMATS" and "STYLES" sections.'),
    Option('status-left-length', 'session', 'status', 'number', '10', min=0, max=1000,
           description='Set the maximum length of the left component of the status line. The default is 10.'),
    Option('status-left-style', 'session', 'status', 'style', 'default',
           description='Set the style of the left part of the status line. For how to specify style, see the "STYLES" section.'),
    Option('status-right', 'session', 'status', 'format', '#{?window_bigger,[#{window_offset_x}#,#{window_offset_y}] ,}"#{=21:pane_title}" %H:%M %d-%b-%y',
           description='Display string to the right of the status line. By default, the current pane title in double quotes, the date and the time are shown. As with status-left, string will be passed to strftime(3) and character pairs are replaced.'),
    Option('status-right-length', 'session', 'status', 'number', '40', min=0, max=1000,
           description='Set the maximum length of the right component of the status line. The default is 40.'),
    Option('status-right-style', 'session', 'status', 'style', 'default',
           description='Set the style of the right part of the status line. For how to specify style, see the "STYLES" section.'),
    Option('status-format', 'session', 'status', 'list', [],
           description='Specify the format to be used for each line of the status line. The default builds the top status line from the various individual status options below.'),
    Option('message-style', 'session', 'status', 'style', 'bg=yellow,fg=black',
           description='Set status line message style. This is used for messages and for the command prompt. For how to specify style, see the "STYLES" section.'),
    Option('message-command-style', 'session', 'status', 'style', 'bg=black,fg=yellow',
           description='Set status line message command style. This is used for the command prompt with vi(1) keys when in command mode. For how to specify style, see the "STYLES" section.'),
    Option('message-line', 'session', 'status', 'choice', '0', choices=['0', '1', '2', '3', '4'],
           description='Set line on which status line messages and the command prompt are shown.'),
    Option('display-time', 'session', 'status', 'number', '750', min=0, max=100000,
           description='Set the amount of time for which status line messages and other on-screen indicators are displayed. If set to 0, messages and indicators are displayed until a key is pressed. time is in milliseconds.'),
    Option('window-status-format', 'window', 'winlist', 'format', '#I:#W#{?window_flags,#{window_flags}, }',
           description='Set the format in which the window is displayed in the status line window list. See the "FORMATS" and "STYLES" sections.'),
    Option('window-status-current-format', 'window', 'winlist', 'format', '#I:#W#{?window_flags,#{window_flags}, }',
           description='Like window-status-format, but is the format used when the window is the current window.'),
    Option('window-status-separator', 'window', 'winlist', 'string', ' ',
           description='Sets the separator drawn between windows in the status line. The default is a single space character.'),
    Option('window-status-style', 'window', 'winlist', 'style', 'default',
           description='Set status line style for a single window. For how to specify style, see the "STYLES" section.'),
    Option('window-status-current-style', 'window', 'winlist', 'style', 'default',
           description='Set status line style for the currently active window. For how to specify style, see the "STYLES" section.'),
    Option('window-status-last-style', 'window', 'winlist', 'style', 'default',
           description='Set status line style for the last active window. For how to specify style, see the "STYLES" section.'),
    Option('window-status-activity-style', 'window', 'winlist', 'style', 'reverse',
           description='Set status line style for windows with an activity alert. For how to specify style, see the "STYLES" section.'),
    Option('window-status-bell-style', 'window', 'winlist', 'style', 'reverse',
           description='Set status line style for windows with a bell alert. For how to specify style, see the "STYLES" section.'),
    Option('automatic-rename', 'window', 'windows', 'flag', 'on',
           description='Control automatic window renaming. When this setting is enabled, tmux will rename the window automatically using the format specified by automatic-rename-format.'),
    Option('automatic-rename-format', 'window', 'windows', 'format', '#{?pane_in_mode,[tmux],#{pane_current_command}}#{?pane_dead,[dead],}',
           description='The format (see "FORMATS") used when the automatic-rename option is enabled.'),
    Option('allow-rename', 'window', 'windows', 'flag', 'off',
           description='Allow programs in the pane to change the window name using a terminal escape sequence (\\ek...\\e\\\\).'),
    Option('set-titles', 'session', 'windows', 'flag', 'off',
           description='Attempt to set the client terminal title using the tsl and fsl terminfo(5) entries if they exist. tmux automatically sets these to the \\e]0;...\\007 sequence if the terminal appears to be xterm(1). This option is off by default.'),
    Option('set-titles-string', 'session', 'windows', 'format', '#S:#I:#W - "#T" #{session_alerts}',
           description='String used to set the client terminal title if set-titles is on. Formats are expanded, see the "FORMATS" section.'),
    Option('aggressive-resize', 'window', 'windows', 'flag', 'off',
           description='Aggressively resize the chosen window. This means that tmux will resize the window to the size of the smallest or largest session (see the window-size option) for which it is the current window, rather than the session to which it is attached.'),
    Option('window-size', 'window', 'windows', 'choice', 'latest', choices=['largest', 'smallest', 'manual', 'latest'],
           description='Configure how tmux determines the window size. If set to largest, the size of the largest attached session is used; if smallest, the size of the smallest. If manual, the size of a new window is set from the default-size option and windows are resized automatically.'),
    Option('main-pane-height', 'window', 'windows', 'string', '24',
           description="Set the width or height of the main (left or top) pane in the main-horizontal or main-vertical layouts. If suffixed by '%', this is a percentage of the window size."),
    Option('main-pane-width', 'window', 'windows', 'string', '80',
           description="Set the width or height of the main (left or top) pane in the main-horizontal or main-vertical layouts. If suffixed by '%', this is a percentage of the window size."),
    Option('other-pane-height', 'window', 'windows', 'string', '0',
           description='Set the height of the other panes (not the main pane) in the main-horizontal layout. If this option is set to 0 (the default), it will have no effect.'),
    Option('other-pane-width', 'window', 'windows', 'string', '0',
           description='Like other-pane-height, but set the width of other panes in the main-vertical layout.'),
    Option('fill-character', 'window', 'windows', 'string', '',
           description='Set the character used to fill areas of the terminal unused by a window.'),
    Option('clock-mode-colour', 'window', 'windows', 'colour', 'blue',
           description='Set clock colour.'),
    Option('clock-mode-style', 'window', 'windows', 'choice', '24', choices=['12', '24'],
           description='Set clock hour format.'),
    Option('pane-border-style', 'window', 'panes', 'style', 'default',
           description='Set the pane border style for panes aside from the active pane. For how to specify style, see the "STYLES" section. Attributes are ignored.'),
    Option('pane-active-border-style', 'window', 'panes', 'style', '#{?pane_in_mode,fg=yellow,#{?synchronize-panes,fg=red,fg=green}}',
           description='Set the pane border style for the currently active pane. For how to specify style, see the "STYLES" section. Attributes are ignored.'),
    Option('pane-border-lines', 'window', 'panes', 'choice', 'single', choices=['single', 'double', 'heavy', 'simple', 'number'],
           description='Set the type of characters used for drawing pane borders: single, double, heavy (UTF-8 lines), simple (ASCII) or number (pane numbers).'),
    Option('pane-border-status', 'window', 'panes', 'choice', 'off', choices=['off', 'top', 'bottom'],
           description='Turn pane border status lines off or set their position.'),
    Option('pane-border-format', 'window', 'panes', 'format', '#{?pane_active,#[reverse],}#{pane_index}#[default] "#{pane_title}"',
           description='Set the text shown in pane border status lines.'),
    Option('pane-border-indicators', 'window', 'panes', 'choice', 'colour', choices=['off', 'colour', 'arrows', 'both'],
           description='Indicate active pane by colouring only half of the border in windows with exactly two panes, by displaying arrow markers, by drawing both or neither.'),
    Option('display-panes-colour', 'session', 'panes', 'colour', 'blue',
           description='Set the colour used by the display-panes command to show the indicators for inactive panes.'),
    Option('display-panes-active-colour', 'session', 'panes', 'colour', 'red',
           description='Set the colour used by the display-panes command to show the indicator for the active pane.'),
    Option('display-panes-time', 'session', 'panes', 'number', '1000', min=0, max=100000,
           description='Set the time in milliseconds for which the indicators shown by the display-panes command appear.'),
    Option('window-style', 'pane', 'panes', 'style', 'default',
           description='Set the pane style. For how to specify style, see the "STYLES" section.'),
    Option('window-active-style', 'pane', 'panes', 'style', 'default',
           description='Set the pane style when it is the active pane. For how to specify style, see the "STYLES" section.'),
    Option('synchronize-panes', 'pane', 'panes', 'flag', 'off',
           description='Duplicate input to all other panes in the same window where this option is also on (only for panes that are not in any mode).'),
    Option('remain-on-exit', 'pane', 'panes', 'choice', 'off', choices=['off', 'on', 'failed'],
           description='A pane with this flag set is not destroyed when the program running in it exits. If set to failed, then only when the program exit status is not zero. The pane may be reactivated with the respawn-pane command.'),
    Option('remain-on-exit-format', 'pane', 'panes', 'format', 'Pane is dead (#{?#{!=:#{pane_dead_status},},status #{pane_dead_status},}#{?#{!=:#{pane_dead_signal},},signal #{pane_dead_signal},}, #{t:pane_dead_time})',
           description='Set the text shown at the bottom of exited panes when remain-on-exit is enabled.'),
    Option('alternate-screen', 'pane', 'panes', 'flag', 'on',
           description='This option configures whether programs running inside the pane may use the terminal alternate screen feature, which allows the smcup and rmcup terminfo(5) capabilities.'),
    Option('scroll-on-clear', 'pane', 'panes', 'flag', 'on',
           description='When the entire screen is cleared and this option is on, scroll the contents of the screen into history before clearing it.'),
    Option('allow-passthrough', 'pane', 'panes', 'choice', 'off', choices=['off', 'on', 'all'],
           description='Allow programs in the pane to bypass tmux using a terminal escape sequence (\\ePtmux;...\\e\\\\). If set to on, passthrough sequences will be allowed only if the pane is visible. If set to all, they will be allowed even if the pane is invisible.'),
    Option('cursor-style', 'pane', 'panes', 'choice', 'default', choices=['default', 'blinking-block', 'block', 'blinking-underline', 'underline', 'blinking-bar', 'bar'],
           description='Set the style of the cursor. Available styles are: default, blinking-block, block, blinking-underline, underline, blinking-bar, bar.'),
    Option('cursor-colour', 'pane', 'panes', 'colour', 'default',
           description='Set the colour of the cursor.'),
    Option('pane-colours', 'pane', 'panes', 'list', [],
           description='The default colour palette. Each entry in the array defines the colour tmux uses when the colour with that index is requested. The index may be from zero to 255.'),
    Option('mode-style', 'window', 'copy', 'style', 'bg=yellow,fg=black',
           description='Set window modes style. For how to specify style, see the "STYLES" section.'),
    Option('copy-mode-match-style', 'window', 'copy', 'style', 'bg=cyan,fg=black',
           description='Set the style of search matches in copy mode. For how to specify style, see the "STYLES" section.'),
    Option('copy-mode-current-match-style', 'window', 'copy', 'style', 'bg=magenta,fg=black',
           description='Set the style of the current search match in copy mode. For how to specify style, see the "STYLES" section.'),
    Option('copy-mode-mark-style', 'window', 'copy', 'style', 'bg=red,fg=black',
           description='Set the style of the line containing the mark in copy mode. For how to specify style, see the "STYLES" section.'),
    Option('wrap-search', 'window', 'copy', 'flag', 'on',
           description='If this option is set, searches will wrap around the end of the pane contents. The default is on.'),
    Option('set-clipboard', 'server', 'copy', 'choice', 'external', choices=['off', 'external', 'on'],
           description='Attempt to set the terminal clipboard content using the xterm(1) escape sequence, if there is an Ms entry in the terminfo(5) description (see the "TERMINFO EXTENSIONS" section).'),
    Option('copy-command', 'server', 'copy', 'string', '',
           description='Give the command to pipe to if the copy-pipe copy mode command is used without arguments.'),
    Option('menu-style', 'window', 'copy', 'style', 'default',
           description='Set the menu style. See the "STYLES" section on how to specify style. Attributes are ignored.'),
    Option('menu-selected-style', 'window', 'copy', 'style', 'bg=yellow,fg=black',
           description='Set the selected menu item style. See the "STYLES" section on how to specify style. Attributes are ignored.'),
    Option('menu-border-style', 'window', 'copy', 'style', 'default',
           description='Set the menu border style. See the "STYLES" section on how to specify style. Attributes are ignored.'),
    Option('menu-border-lines', 'window', 'copy', 'choice', 'single', choices=['single', 'rounded', 'double', 'heavy', 'simple', 'padded', 'none'],
           description='Set the type of characters used for drawing menu borders. See popup-border-lines for possible values for border-lines.'),
    Option('popup-style', 'window', 'copy', 'style', 'default',
           description='Set the popup style. See the "STYLES" section on how to specify style. Attributes are ignored.'),
    Option('popup-border-style', 'window', 'copy', 'style', 'default',
           description='Set the popup border style. See the "STYLES" section on how to specify style. Attributes are ignored.'),
    Option('popup-border-lines', 'window', 'copy', 'choice', 'single', choices=['single', 'rounded', 'double', 'heavy', 'simple', 'padded', 'none'],
           description='Set the type of characters used for drawing popup borders: single, rounded, double, heavy (UTF-8 lines), simple (ASCII), padded (spaces) or none.'),
    Option('monitor-activity', 'window', 'alerts', 'flag', 'off',
           description='Monitor for activity in the window. Windows with activity are highlighted in the status line.'),
    Option('monitor-bell', 'window', 'alerts', 'flag', 'on',
           description='Monitor for a bell in the window. Windows with a bell are highlighted in the status line.'),
    Option('monitor-silence', 'window', 'alerts', 'number', '0', min=0, max=86400,
           description='Monitor for silence (no activity) in the window within interval seconds. Windows that have been silent for the interval are highlighted in the status line. An interval of zero disables the monitoring.'),
    Option('activity-action', 'session', 'alerts', 'choice', 'other', choices=['any', 'none', 'current', 'other'],
           description='Set action on window activity when monitor-activity is on. any means activity in any window linked to a session causes a bell or message (depending on visual-activity) in the current window of that session, none means all activity is ignored (equivalent to monitor-activity being off), current means only activity in windows other than the current window are ignored and other means activity in the current window is ignored but not those in other windows.'),
    Option('bell-action', 'session', 'alerts', 'choice', 'any', choices=['any', 'none', 'current', 'other'],
           description='Set action on a bell in a window when monitor-bell is on. The values are the same as those for activity-action.'),
    Option('silence-action', 'session', 'alerts', 'choice', 'other', choices=['any', 'none', 'current', 'other'],
           description='Set action on window silence when monitor-silence is on. The values are the same as those for activity-action.'),
    Option('visual-activity', 'session', 'alerts', 'choice', 'off', choices=['off', 'on', 'both'],
           description='If on, display a message instead of sending a bell when activity occurs in a window for which the monitor-activity window option is enabled. If set to both, a bell and a message are produced.'),
    Option('visual-bell', 'session', 'alerts', 'choice', 'off', choices=['off', 'on', 'both'],
           description='If on, a message is shown on a bell in a window for which the monitor-bell window option is enabled instead of it being passed through to the terminal (which normally makes a sound). If set to both, a bell and a message are produced. Also see the bell-action option.'),
    Option('visual-silence', 'session', 'alerts', 'choice', 'off', choices=['off', 'on', 'both'],
           description='If monitor-silence is enabled, prints a message after the interval has expired on a given window instead of sending a bell. If set to both, a bell and a message are produced.'),
    Option('default-terminal', 'server', 'terminal', 'string', 'tmux-256color',
           description="Set the default terminal for new windows created in this session - the default value of the TERM environment variable. For tmux to work correctly, this must be set to 'screen', 'tmux' or a derivative of them."),
    Option('terminal-features', 'server', 'terminal', 'list', ['xterm*:clipboard:ccolour:cstyle:focus:title', 'screen*:title', 'rxvt*:ignorefkeys'],
           description='Set terminal features for terminal types read from terminfo(5). tmux has a set of named terminal features. Each will apply appropriate changes to the terminfo(5) entry in use.'),
    Option('terminal-overrides', 'server', 'terminal', 'list', [],
           description='Allow terminal descriptions read using terminfo(5) to be overridden. Each entry is a colon-separated string made up of a terminal type pattern (matched using fnmatch(3)) and a set of name=value entries.'),
]

OPTIONS_BY_NAME: dict[str, Option] = {o.name: o for o in OPTIONS}


def options_in(category: str) -> list[Option]:
    return [o for o in OPTIONS if o.category == category]
