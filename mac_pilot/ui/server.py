"""WebSocket server — pushes events from brain/voice to UI, receives commands."""

import asyncio
import json
import websockets
from ..events import bus

_clients: set = set()
_server = None
_command_queue: asyncio.Queue | None = None


def get_command_queue() -> asyncio.Queue:
    """Return the shared command queue, creating it on first call."""
    global _command_queue
    if _command_queue is None:
        _command_queue = asyncio.Queue()
    return _command_queue


async def _handler(websocket) -> None:
    """Handle a single WebSocket connection lifecycle."""
    _clients.add(websocket)
    try:
        from ..setup_check import get_setup_status
        state = bus.state
        await websocket.send(json.dumps({
            "type": "init",
            "status": state.status,
            "transcript": state.transcript,
            "task": state.task,
            "steps": [
                {
                    "step": s.step,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args,
                    "status": s.status,
                    "result": s.result[:80],
                    "elapsed": s.elapsed,
                }
                for s in state.steps
            ],
            "result": state.final_result,
            "setup": get_setup_status(),
        }))
        # Listen for commands from UI
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg.get("type") == "command" and msg.get("text"):
                    queue = get_command_queue()
                    await queue.put(msg["text"])
                elif msg.get("type") == "toggle_voice":
                    from ..voice import toggle_mic
                    await toggle_mic()
                elif msg.get("type") == "cancel":
                    from ..brain import cancel_brain
                    from ..voice import flush_audio
                    cancel_brain()
                    flush_audio()
                elif msg.get("type") == "connect_google":
                    from ..setup_check import run_gws_auth, check_gws_authenticated
                    run_gws_auth()
                    # Poll until authenticated (max 60s)
                    for _ in range(30):
                        await asyncio.sleep(2)
                        if check_gws_authenticated():
                            await websocket.send(json.dumps({
                                "type": "setup_update",
                                "gws_authenticated": True,
                            }))
                            break
            except json.JSONDecodeError:
                pass
    finally:
        _clients.discard(websocket)


async def _broadcast(event_type: str, data: dict) -> None:
    """Send an event to all connected WebSocket clients."""
    if not _clients:
        return
    msg = json.dumps({"type": event_type, **data})
    await asyncio.gather(
        *[c.send(msg) for c in _clients.copy()],
        return_exceptions=True,
    )


async def start_server(host: str = "127.0.0.1", port: int = 8765):
    """Start WebSocket server and subscribe to the event bus."""
    global _server
    bus.subscribe(_broadcast)
    _server = await websockets.serve(_handler, host, port)
    print(f"   UI WebSocket: ws://{host}:{port}")
    return _server


async def stop_server() -> None:
    """Gracefully stop the WebSocket server."""
    global _server
    if _server:
        _server.close()
        await _server.wait_closed()
    bus.unsubscribe(_broadcast)
