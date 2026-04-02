"""Google Workspace tools — Gmail, Calendar, Drive, Docs via gws CLI.

All external commands run through _gws() for uniform timeout/truncation.
"""

import subprocess
import shlex
import json
import base64


def _gws(cmd: str, timeout: int = 30, max_output: int = 3000) -> str:
    """Run a gws CLI command and return combined stdout+stderr (truncated)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()[:max_output] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


def _esc(value: str) -> str:
    """Shell-escape a string for safe inclusion in a command."""
    return shlex.quote(value)


# ── Gmail ─────────────────────────────────────────────────────────

def tool_gmail_read() -> str:
    """Read recent emails summary."""
    result = _gws("gws gmail +triage")
    if "No messages found" in result:
        # Fallback: show all recent inbox emails, not just unread
        result = _gws("gws gmail +triage --query 'in:inbox' --max 10")
    return result


def tool_gmail_read_message(message_id: str) -> str:
    """Read the full content of a specific email by its message ID."""
    params = json.dumps({"id": message_id, "userId": "me", "format": "full"})
    try:
        r = subprocess.run(
            ["gws", "gmail", "users", "messages", "get", "--params", params],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return f"Error reading email: {e}"
    if "error" in data:
        return f"Error: {data['error'].get('message', 'Unknown error')}"
    headers = data.get("payload", {}).get("headers", [])
    hdr = lambda n: next((h["value"] for h in headers if h["name"] == n), "")
    body = _extract_body(data.get("payload", {}))
    return f"From: {hdr('From')}\nDate: {hdr('Date')}\nSubject: {hdr('Subject')}\n\n{body[:2000]}"


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail payload."""
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        nested = _extract_body(part)
        if nested:
            return nested
    return ""


def tool_gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email via gws."""
    return _gws(f"gws gmail +send --to {_esc(to)} --subject {_esc(subject)} --body {_esc(body)}")


# ── Calendar ──────────────────────────────────────────────────────

def tool_calendar_read(days: int = 1) -> str:
    """Read calendar agenda. days=1 for today, days=7 for the week."""
    if days <= 1:
        return _gws("gws calendar +agenda --today --format table")
    if days <= 2:
        return _gws("gws calendar +agenda --tomorrow --format table")
    return _gws(f"gws calendar +agenda --days {int(days)} --format table")


def tool_calendar_create(summary: str, start: str, end: str) -> str:
    """Create a calendar event. Dates must be ISO format."""
    return _gws(
        f"gws calendar +insert --summary {_esc(summary)} --start {_esc(start)} --end {_esc(end)}"
    )


# ── Drive ─────────────────────────────────────────────────────────

def tool_drive_list() -> str:
    """List the 10 most recent Google Drive files."""
    return _gws("gws drive files list --params '{\"pageSize\": 10}' --format table")


def tool_drive_upload(file_path: str) -> str:
    """Upload a local file to Google Drive."""
    return _gws(f"gws drive +upload {_esc(file_path)}")


# ── Docs ──────────────────────────────────────────────────────────

def tool_docs_create(title: str, content: str) -> str:
    """Create a Google Doc with the given title and text content."""
    try:
        r = subprocess.run(
            ["gws", "docs", "documents", "create", "--json", json.dumps({"title": title})],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return f"Error creating doc: {(r.stderr or r.stdout).strip()}"
        data = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        return f"Error creating doc: {e}"

    doc_id = data.get("documentId")
    if not doc_id:
        return "Error: no documentId in response"
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    update = json.dumps({"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]})
    try:
        subprocess.run(
            ["gws", "docs", "documents", "batchUpdate",
             "--params", json.dumps({"documentId": doc_id}), "--json", update],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"Doc created but content failed: {doc_url}\nError: {e}"

    return f"Created Google Doc: '{title}'\nURL: {doc_url}"
