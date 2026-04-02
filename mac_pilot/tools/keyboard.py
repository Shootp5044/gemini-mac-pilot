"""Keyboard tools — type text and press key combinations."""

import re
import subprocess
from .accessibility import _with_ui


def tool_type_text(text: str) -> str:
    """Type text into the currently focused element via System Events."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e",
        f'tell application "System Events" to keystroke "{escaped}"'])
    return f"Typed '{text[:40]}'."


def tool_press_keys(keys: str) -> str:
    """Press a keyboard shortcut (e.g. 'command+n', 'enter', 'shift+tab')."""
    parts = keys.lower().split("+")
    key = parts[-1]
    mods = parts[:-1]
    mod_map = {
        "command": "command down", "cmd": "command down",
        "shift": "shift down", "option": "option down",
        "alt": "option down", "control": "control down", "ctrl": "control down",
    }
    mod_str = ", ".join(mod_map[m] for m in mods if m in mod_map)
    codes = {
        "return": 36, "enter": 36, "tab": 48, "escape": 53,
        "space": 49, "delete": 51, "up": 126, "down": 125,
        "left": 123, "right": 124,
    }
    if not re.match(r'^[a-z0-9]+$', key):
        if key not in codes:
            return f"Invalid key: {key}"
    if key in codes:
        s = f'tell application "System Events" to key code {codes[key]}'
        if mod_str:
            s += f' using {{{mod_str}}}'
    elif mod_str:
        s = f'tell application "System Events" to keystroke "{key}" using {{{mod_str}}}'
    else:
        s = f'tell application "System Events" to keystroke "{key}"'
    subprocess.run(["osascript", "-e", s])
    return _with_ui(f"Pressed {keys}.")
