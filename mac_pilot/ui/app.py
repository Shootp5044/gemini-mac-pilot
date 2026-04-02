"""PyWebView overlay — slim floating bar anchored to top."""

import os
import webview

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
ICON_PATH = os.path.abspath(os.path.join(PROJECT_DIR, "icon.png"))


def create_window():
    """Create the slim bar window. Must call start_webview() after."""
    # Get screen width to center the bar
    try:
        import subprocess
        r = subprocess.run(["osascript", "-e",
            'tell application "Finder" to get bounds of window of desktop'],
            capture_output=True, text=True)
        parts = r.stdout.strip().split(", ")
        screen_w = int(parts[2])
    except Exception:
        screen_w = 1728  # fallback

    bar_w = 680
    x = (screen_w - bar_w) // 2

    window = webview.create_window(
        "Mac Pilot",
        url=os.path.join(STATIC_DIR, "index.html"),
        width=bar_w,
        height=400,
        x=x,
        y=6,
        resizable=True,
        on_top=True,
        frameless=True,
        transparent=True,
        background_color="#000000",
    )
    return window


def _set_dock_icon():
    """Set the dock icon to our custom Gemini icon."""
    try:
        from AppKit import NSApplication, NSImage
        icon = NSImage.alloc().initWithContentsOfFile_(ICON_PATH)
        if icon:
            NSApplication.sharedApplication().setApplicationIconImage_(icon)
    except Exception:
        pass


def start_webview():
    """Start webview event loop. MUST be called from main thread on macOS."""
    _set_dock_icon()
    webview.start(debug=False)
