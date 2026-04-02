"""Tool declarations for Gemini function calling + dispatch table.

Declarations are grouped by category. TOOL_DISPATCH maps each function
name to a callable that accepts the raw args dict from Gemini.
"""

from google.genai import types


def _safe_int(a: dict, key: str, default: int = 0) -> int:
    try: return int(a[key])
    except (KeyError, ValueError, TypeError): return default

from .accessibility import tool_click, tool_set_value, tool_focus
from .keyboard import tool_type_text, tool_press_keys
from .apps import tool_open_app, tool_find_app
from .browser import (
    tool_browse, tool_chrome_js, tool_browser_click,
    tool_browser_type, tool_read_page, tool_get_links, tool_click_text,
    tool_search,
)
from .shell import tool_shell
from .workspace import (
    tool_gmail_read, tool_gmail_read_message, tool_gmail_send,
    tool_calendar_read, tool_calendar_create,
    tool_drive_list, tool_drive_upload, tool_docs_create,
)


def _decl(name, desc, props=None, required=None):
    """Shorthand for building a FunctionDeclaration."""
    schema_props = {
        k: types.Schema(type=v[0], description=v[1] if len(v) > 1 else None)
        for k, v in (props or {}).items()
    }
    return types.FunctionDeclaration(
        name=name, description=desc,
        parameters=types.Schema(type="OBJECT", properties=schema_props, required=required or []),
    )


# ── Native macOS tools ────────────────────────────────────────────
_NATIVE = [
    _decl("open_app", "Open and activate a macOS app. Returns updated UI state.",
          {"app_name": ("STRING",)}, ["app_name"]),
    _decl("find_app", "Search installed apps by name.",
          {"name": ("STRING",)}, ["name"]),
    _decl("click", "Click a native macOS UI element by [ID]. For native apps only.",
          {"element_id": ("INTEGER",)}, ["element_id"]),
    _decl("set_value", "Set text of a native field by [ID]. If fails, use focus + type_text.",
          {"element_id": ("INTEGER",), "text": ("STRING",)}, ["element_id", "text"]),
    _decl("focus", "Focus a native macOS UI element by [ID]. Use before type_text.",
          {"element_id": ("INTEGER",)}, ["element_id"]),
    _decl("type_text", "Type text via keyboard into the currently focused element.",
          {"text": ("STRING",)}, ["text"]),
    _decl("press_keys", "Press keyboard shortcut. Examples: 'command+n', 'enter', 'tab'.",
          {"keys": ("STRING",)}, ["keys"]),
    _decl("shell", "Run a shell command. Use for system info, file ops, etc.",
          {"cmd": ("STRING",)}, ["cmd"]),
]

# ── Browser tools (Playwright) ────────────────────────────────────
_BROWSER = [
    _decl("browse", "Navigate to a URL and return the page text.",
          {"url": ("STRING",)}, ["url"]),
    _decl("read_page", "Read current browser page text. Use after browse or clicking."),
    _decl("get_links", "List interactive elements (links, buttons, inputs) on the page."),
    _decl("click_text", "Click a browser element by its visible text.",
          {"text": ("STRING", "The visible text of the element")}, ["text"]),
    _decl("browser_click", "Click a browser element by CSS selector.",
          {"selector": ("STRING",)}, ["selector"]),
    _decl("browser_type", "Type text into a browser input by CSS selector.",
          {"selector": ("STRING",), "text": ("STRING",)}, ["selector", "text"]),
    _decl("chrome_js", "Execute JavaScript on the current page. Returns the result.",
          {"code": ("STRING",)}, ["code"]),
    _decl("search", "Search the web using DuckDuckGo. Returns top 5 results with title, snippet, and URL.",
          {"query": ("STRING", "The search query")}, ["query"]),
]

# ── Google Workspace tools ────────────────────────────────────────
_WORKSPACE = [
    _decl("gmail_read", "Read unread emails. Returns sender, subject, date."),
    _decl("gmail_read_message", "Read the full body of a specific email.",
          {"message_id": ("STRING", "The message ID from gmail_read")}, ["message_id"]),
    _decl("gmail_send", "Send an email.",
          {"to": ("STRING", "Recipient email"), "subject": ("STRING",), "body": ("STRING",)},
          ["to", "subject", "body"]),
    _decl("calendar_read", "Read calendar agenda. days=1 today, days=7 week.",
          {"days": ("INTEGER", "Days ahead. Default 1.")}),
    _decl("calendar_create", "Create a calendar event.",
          {"summary": ("STRING", "Event title"),
           "start": ("STRING", "ISO: 2026-03-15T10:00:00"),
           "end": ("STRING", "ISO: 2026-03-15T11:00:00")}, ["summary", "start", "end"]),
    _decl("docs_create", "Create a Google Doc. Returns URL.",
          {"title": ("STRING",), "content": ("STRING",)}, ["title", "content"]),
    _decl("drive_list", "List recent Google Drive files."),
    _decl("drive_upload", "Upload a local file to Google Drive.",
          {"file_path": ("STRING", "Path to the local file")}, ["file_path"]),
]

# ── Exported aggregates ───────────────────────────────────────────
BRAIN_TOOLS = [types.Tool(function_declarations=_NATIVE + _BROWSER + _WORKSPACE)]

TOOL_DISPATCH: dict[str, object] = {
    # Native macOS
    "open_app":       lambda a: tool_open_app(a.get("app_name", "")),
    "find_app":       lambda a: tool_find_app(a.get("name", "")),
    "click":          lambda a: tool_click(_safe_int(a, "element_id")),
    "set_value":      lambda a: tool_set_value(_safe_int(a, "element_id"), a.get("text", "")),
    "focus":          lambda a: tool_focus(_safe_int(a, "element_id")),
    "type_text":      lambda a: tool_type_text(a.get("text", "")),
    "press_keys":     lambda a: tool_press_keys(a.get("keys", "")),
    "shell":          lambda a: tool_shell(a.get("cmd", "")),
    # Browser
    "browse":         lambda a: tool_browse(a.get("url", "")),
    "read_page":      lambda a: tool_read_page(),
    "get_links":      lambda a: tool_get_links(),
    "click_text":     lambda a: tool_click_text(a.get("text", "")),
    "browser_click":  lambda a: tool_browser_click(a.get("selector", "")),
    "browser_type":   lambda a: tool_browser_type(a.get("selector", ""), a.get("text", "")),
    "chrome_js":      lambda a: tool_chrome_js(a.get("code", "")),
    "search":         lambda a: tool_search(a.get("query", "")),
    # Google Workspace
    "gmail_read":         lambda a: tool_gmail_read(),
    "gmail_read_message": lambda a: tool_gmail_read_message(a.get("message_id", "")),
    "gmail_send":         lambda a: tool_gmail_send(a.get("to", ""), a.get("subject", ""), a.get("body", "")),
    "calendar_read":      lambda a: tool_calendar_read(_safe_int(a, "days", 1)),
    "calendar_create":    lambda a: tool_calendar_create(a.get("summary", ""), a.get("start", ""), a.get("end", "")),
    "drive_list":         lambda a: tool_drive_list(),
    "drive_upload":       lambda a: tool_drive_upload(a.get("file_path", "")),
    "docs_create":        lambda a: tool_docs_create(a.get("title", ""), a.get("content", "")),
}
