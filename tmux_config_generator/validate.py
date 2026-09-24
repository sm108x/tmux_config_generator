"""Check a generated config with a real tmux binary, if one is installed."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def tmux_available() -> str | None:
    return shutil.which("tmux")


def validate(text: str, safe_text: str | None = None, tmux: str | None = None,
             timeout: float = 10) -> tuple[bool, str]:
    """Check a config on a throwaway tmux server. Returns (ok, message).

    *text* is only parsed (`source-file -n`), so nothing in it is run.
    *safe_text* (defaults to *text*) is really executed so tmux also checks
    option names and values; it must only contain set/bind/unbind lines.
    """
    tmux = tmux or tmux_available()
    if not tmux:
        return False, "tmux was not found on PATH, so the config cannot be checked."
    if safe_text is None:
        safe_text = text
    socket = f"tcg-validate-{os.getpid()}"
    paths = []
    try:
        for content in (text, safe_text):
            fd, path = tempfile.mkstemp(suffix=".conf", prefix="tcg-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            paths.append(path)
        cmd = [tmux, "-L", socket, "-f", os.devnull, "new-session", "-d",
               ";", "source-file", "-n", paths[0],
               ";", "source-file", paths[1]]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
        out = (proc.stdout + proc.stderr).strip()
        for path in paths:
            out = out.replace(path, "tmux.conf")
        if proc.returncode == 0 and not out:
            return True, "tmux accepted the configuration without errors."
        return False, out or f"tmux exited with status {proc.returncode}."
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Could not run tmux: {e}"
    finally:
        try:
            subprocess.run([tmux, "-L", socket, "kill-server"],
                           capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            pass
        for path in paths:
            os.unlink(path)
