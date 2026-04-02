"""macOS Accessibility API — read UI tree, click, focus, set value."""

import time
import ApplicationServices as AS
from Cocoa import NSWorkspace

element_cache: dict[int, object] = {}
target_app: str | None = None


def ax_get(el, attr: str):
    """Read a single accessibility attribute from an element."""
    err, val = AS.AXUIElementCopyAttributeValue(el, attr, None)
    return val if err == 0 else None


def walk_tree(el, depth: int = 0, max_depth: int = 10, idx_counter=None) -> list[str]:
    """Recursively walk the AX tree, caching interactive elements by index."""
    if idx_counter is None:
        idx_counter = [0]
    if depth > max_depth:
        return []
    role = ax_get(el, "AXRole") or "?"
    if role == "AXMenuBar":
        return []
    title = ax_get(el, "AXTitle") or ""
    desc = ax_get(el, "AXDescription") or ""
    value = ax_get(el, "AXValue") or ""
    label = " | ".join(filter(None, [title, desc, str(value)[:60] if value else ""]))

    USEFUL_ROLES = {
        "AXButton", "AXTextField", "AXTextArea", "AXLink",
        "AXCheckBox", "AXRadioButton", "AXPopUpButton",
        "AXComboBox", "AXSearchField", "AXSlider",
        "AXMenuItem", "AXCell", "AXTab", "AXHeading",
        "AXStaticText", "AXWindow", "AXApplication",
    }
    nodes = []
    if label and role in USEFUL_ROLES:
        idx = idx_counter[0]
        idx_counter[0] += 1
        element_cache[idx] = el
        nodes.append(f"[{idx}] {role}: {label}")
    children = ax_get(el, "AXChildren")
    if children:
        for c in children[:50]:
            nodes.extend(walk_tree(c, depth + 1, max_depth, idx_counter))
    return nodes


def read_ui() -> str:
    """Read the accessibility tree of the target/frontmost app."""
    global element_cache
    element_cache.clear()

    pid, name = None, None

    if target_app:
        for a in NSWorkspace.sharedWorkspace().runningApplications():
            if target_app.lower() in a.localizedName().lower():
                pid = a.processIdentifier()
                name = a.localizedName()
                break

    if not pid:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        name = app.localizedName()
        if any(t in name.lower() for t in ["warp", "terminal", "iterm"]):
            return "No app focused. Open an app first."
        pid = app.processIdentifier()

    ax_app = AS.AXUIElementCreateApplication(pid)
    nodes = walk_tree(ax_app)
    return f"[{name}] {len(nodes)} elements:\n" + "\n".join(nodes[:100])


def _with_ui(result: str) -> str:
    """Append current UI state to any action result."""
    time.sleep(0.3)
    ui = read_ui()
    return f"{result}\n\nCURRENT UI:\n{ui}"


def tool_click(element_id: int) -> str:
    """Click a UI element by its cached ID."""
    el = element_cache.get(element_id)
    if not el:
        return _with_ui(f"Element [{element_id}] not found.")
    AS.AXUIElementPerformAction(el, "AXPress")
    return _with_ui(f"Clicked [{element_id}].")


def tool_set_value(element_id: int, text: str) -> str:
    """Set the AXValue of a UI element. Falls back to focus + type_text."""
    el = element_cache.get(element_id)
    if not el:
        return _with_ui(f"Element [{element_id}] not found.")
    AS.AXUIElementSetAttributeValue(el, "AXFocused", True)
    time.sleep(0.1)
    if AS.AXUIElementSetAttributeValue(el, "AXValue", text) == 0:
        return _with_ui(f"Set [{element_id}] to '{text[:40]}'.")
    return _with_ui("Could not set value. Try focus + type_text instead.")


def tool_focus(element_id: int) -> str:
    """Focus a UI element by its cached ID."""
    el = element_cache.get(element_id)
    if not el:
        return f"Element [{element_id}] not found."
    AS.AXUIElementSetAttributeValue(el, "AXFocused", True)
    return f"Focused [{element_id}]."
