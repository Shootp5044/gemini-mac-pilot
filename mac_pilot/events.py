"""Event system — bridge between brain/voice and the UI.

The EventBus provides a simple pub/sub mechanism. Listeners receive
(event_type, data) and may be sync or async callables.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class StepEvent:
    """A single tool-execution step within a brain loop."""

    step: int
    tool_name: str
    tool_args: str
    status: str = "running"   # running | done | error
    result: str = ""
    elapsed: float = 0.0


@dataclass
class PilotState:
    """Observable state that the UI reflects."""

    status: str = "idle"      # idle | listening | processing | speaking
    transcript: str = ""
    task: str = ""
    steps: list[StepEvent] = field(default_factory=list)
    final_result: str = ""


class EventBus:
    """Simple pub/sub for pushing state changes to UI listeners."""

    def __init__(self) -> None:
        self._listeners: list[Callable[..., Any]] = []
        self.state: PilotState = PilotState()

    def subscribe(self, callback: Callable[..., Any]) -> None:
        """Register a listener. It will be called with (event_type, data)."""
        self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[..., Any]) -> None:
        """Remove a previously registered listener."""
        self._listeners = [l for l in self._listeners if l is not callback]

    async def emit(self, event_type: str, data: Optional[dict] = None) -> None:
        """Notify all listeners of an event. Handles both sync and async callbacks."""
        for listener in self._listeners:
            try:
                result = listener(event_type, data or {})
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"[EventBus] listener error: {e}")

    # ── Convenience setters ───────────────────────────────────────

    async def set_status(self, status: str) -> None:
        """Update the global status and broadcast it."""
        self.state.status = status
        await self.emit("status", {"status": status})

    async def set_transcript(self, text: str) -> None:
        """Update the live voice transcript."""
        self.state.transcript = text
        await self.emit("transcript", {"text": text})

    async def set_task(self, task: str) -> None:
        """Begin a new task — resets steps and result."""
        self.state.task = task
        self.state.steps = []
        self.state.final_result = ""
        await self.emit("task", {"task": task})

    async def add_step(self, step: StepEvent) -> None:
        """Append a new step and broadcast it."""
        self.state.steps.append(step)
        await self.emit("step", {
            "step": step.step,
            "tool_name": step.tool_name,
            "tool_args": step.tool_args,
            "status": step.status,
        })

    async def update_step(self, step_idx: int, status: str,
                          result: str = "", elapsed: float = 0.0) -> None:
        """Update an existing step with its outcome."""
        if step_idx < len(self.state.steps):
            s = self.state.steps[step_idx]
            s.status = status
            s.result = result
            s.elapsed = elapsed
        await self.emit("step_update", {
            "step": step_idx,
            "status": status,
            "result": result[:80],
            "elapsed": elapsed,
        })

    async def set_result(self, result: str) -> None:
        """Store and broadcast the final result of a task."""
        self.state.final_result = result
        await self.emit("result", {"result": result})


# Global event bus — single instance shared across all modules.
bus = EventBus()
