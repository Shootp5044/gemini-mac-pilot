"""App management tools — open and find macOS applications."""

import shlex
import subprocess
import time
from . import accessibility
from .accessibility import _with_ui


def tool_open_app(app_name: str) -> str:
    """Open and activate a macOS application, then return its UI state."""
    safe_name = app_name.replace('"', '\\"')
    subprocess.run(["open", "-a", app_name], capture_output=True)
    time.sleep(1)
    subprocess.run(["osascript", "-e", f'tell application "{safe_name}" to activate'],
                   capture_output=True)
    time.sleep(0.5)
    accessibility.target_app = app_name
    return _with_ui(f"Opened {app_name}.")


def tool_find_app(name: str) -> str:
    """Search /Applications for apps matching the given name."""
    r = subprocess.run(f'ls /Applications/ | grep -i {shlex.quote(name)}',
                       shell=True, capture_output=True, text=True)
    return r.stdout.strip() or f"No app matching '{name}' found."
