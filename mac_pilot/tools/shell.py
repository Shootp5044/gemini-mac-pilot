"""Shell tool — run system commands with safety guardrails."""

import re
import subprocess


BLOCKED_COMMANDS = ["say ", "afplay ", "espeak "]

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+/\*",
    r"mkfs\.",
    r"format\s+",
    r"dd\s+if=",
    r":\(\)\{:",           # fork bomb
    r">\s*/dev/sda",
    r"chmod\s+-R\s+777\s+/",
    r"shutdown",
    r"reboot",
    r"halt",
    r"init\s+0",
    r"init\s+6",
    r"sudo\s+",
    r"curl.*\|.*sh",
    r"wget.*\|.*sh",
    r"gws\s+auth",
]


def tool_shell(cmd: str) -> str:
    """Run a shell command after checking against blocklists. Returns output."""
    stripped = cmd.strip()
    # Block TTS commands — Gemini Live already handles voice output
    if any(stripped.startswith(b) for b in BLOCKED_COMMANDS):
        return "Voice output is handled automatically. Command skipped."
    # Block dangerous / destructive commands
    if any(re.search(pat, stripped) for pat in DANGEROUS_PATTERNS):
        return f"Blocked dangerous command: {stripped[:80]}"
    try:
        timeout = 30 if stripped.startswith("gws ") else 10
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip()[:3000]
        return out or "(no output)"
    except Exception as e:
        return f"Error: {e}"
