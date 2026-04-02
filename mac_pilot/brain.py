"""Brain — Gemini decision-making loop with native function calling.

Keeps a short conversation history for context between tasks.
The system prompt lives in prompts.py; tool declarations in tools/schema.py.
"""

import asyncio
import json
import time

from google.genai import types

from .config import client, BRAIN_MODEL
from .prompts import BRAIN_SYSTEM
from .tools import accessibility
from .tools.schema import BRAIN_TOOLS, TOOL_DISPATCH
from .events import bus, StepEvent

_cancelled = False
_MAX_STEPS = 50
_HISTORY_WINDOW = 6

BRAIN_CONFIG = types.GenerateContentConfig(
    system_instruction=BRAIN_SYSTEM, tools=BRAIN_TOOLS, temperature=0.5,
)

_conversation_history: list = []


def cancel_brain() -> None:
    """Set the cancel flag so the current loop exits early."""
    global _cancelled
    _cancelled = True


async def run_brain_loop(user_request: str, keep_context: bool = True) -> str:
    """Execute a task using Gemini as the brain. Returns a text summary."""
    global _conversation_history, _cancelled
    _cancelled = False
    accessibility.target_app = None
    await bus.set_task(user_request)
    await bus.set_status("processing")

    if not user_request or not user_request.strip():
        return "No command provided."

    task_start = time.time()
    tools_used = set()

    user_msg = types.Content(role="user", parts=[types.Part.from_text(text=user_request)])
    if keep_context and _conversation_history:
        contents = _conversation_history[-4:] + [user_msg]
    else:
        contents = [user_msg]

    for step in range(_MAX_STEPS):
        if _cancelled:
            return await _finish(contents, "Task cancelled.")

        t0 = time.time()
        print(f"  {step + 1}. thinking...", end="", flush=True)

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=BRAIN_MODEL, contents=contents, config=BRAIN_CONFIG,
            )
        except Exception as e:
            print(f" API error: {e}")
            await bus.set_result(f"API error: {str(e)[:200]}")
            _conversation_history = contents[-_HISTORY_WINDOW:]
            return f"Error: {e}"

        elapsed = time.time() - t0
        if _cancelled:
            return await _finish(contents, "Task cancelled.")
        if not response.candidates:
            await bus.set_status("idle")
            _conversation_history = contents[-_HISTORY_WINDOW:]
            return "Error: Gemini returned no candidates."

        model_content = response.candidates[0].content
        contents.append(model_content)

        # Collect ALL function calls from this turn (Gemini may send multiple)
        fcs = [p.function_call for p in model_content.parts if p.function_call]

        if not fcs:
            text = "".join(p.text for p in model_content.parts if p.text)
            total_time = time.time() - task_start
            steps_taken = step + 1
            print(f" -> done ({elapsed:.1f}s)")
            print(f"  Result: {text.strip()}")
            await bus.emit("result", {
                "result": text or "Done.",
                "stats": {
                    "time": round(total_time, 1),
                    "steps": steps_taken,
                    "tools": sorted(tools_used),
                },
            })
            _conversation_history = contents[-_HISTORY_WINDOW:]
            return text or "Done."

        # Execute all function calls and collect responses
        response_parts = []
        for fc in fcs:
            name, args = fc.name, dict(fc.args) if fc.args else {}
            tools_used.add(name)
            args_str = json.dumps(args)[:60]
            print(f" -> {name}({args_str}) ({elapsed:.1f}s)", end="")
            await bus.add_step(StepEvent(step=step, tool_name=name, tool_args=args_str))

            if name in TOOL_DISPATCH:
                result = await asyncio.to_thread(TOOL_DISPATCH[name], args)
                short = result.split("\n")[0][:60]
                print(f" -> {short}")
                await bus.update_step(step, "done", short, time.time() - t0)
            else:
                result = f"Unknown tool: {name}"
                print(f" -> {result}")
                await bus.update_step(step, "error", result, time.time() - t0)

            response_parts.append(types.Part.from_function_response(
                name=name, response={"result": result[:4000]},
            ))

        if _cancelled:
            return await _finish(contents, "Task cancelled.")

        contents.append(types.Content(role="user", parts=response_parts))
        _trim_old_ui_data(contents)

    await bus.set_status("idle")
    _conversation_history = contents[-_HISTORY_WINDOW:]
    return "Could not complete the task."


# ── Helpers ───────────────────────────────────────────────────────

async def _finish(contents: list, message: str) -> str:
    """Common exit path for cancellation."""
    global _conversation_history
    print("  Cancelled by user")
    await bus.set_result(message)
    _conversation_history = contents[-_HISTORY_WINDOW:]
    return message


def _trim_old_ui_data(contents: list) -> None:
    """Replace stale CURRENT UI blobs with a placeholder to save tokens."""
    if len(contents) <= 8:
        return
    for i in range(len(contents) - 4):
        if contents[i].role != "user":
            continue
        for j, part in enumerate(contents[i].parts):
            if not (hasattr(part, "function_response") and part.function_response):
                continue
            resp = str(part.function_response.response.get("result", ""))
            if "CURRENT UI:" in resp and len(resp) > 200:
                truncated = resp.split("CURRENT UI:")[0] + "CURRENT UI: [truncated]"
                contents[i].parts[j] = types.Part.from_function_response(
                    name=part.function_response.name,
                    response={"result": truncated},
                )
