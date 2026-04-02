"""Voice — Gemini Live API for bidirectional audio I/O.

Module-level mutable state: mic_active, audio_out, audio_in, audio_stream, pya.
"""

import asyncio
import threading
import pyaudio
from google.genai import types

from .config import voice_client, VOICE_MODEL, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE
from .prompts import VOICE_SYSTEM
from .brain import run_brain_loop
from .events import bus

# ── Constants ─────────────────────────────────────────────────────
FORMAT = pyaudio.paInt16
CHANNELS = 1
BACKOFF_INITIAL = 2
BACKOFF_MAX = 30

# ── Voice session config ─────────────────────────────────────────
VOICE_TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="execute_task",
        description="Execute a task on the user's Mac. Pass exactly what the user asked.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"task": types.Schema(type="STRING")},
            required=["task"]),
    ),
])]

VOICE_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(parts=[types.Part(text=VOICE_SYSTEM)]),
    tools=VOICE_TOOLS,
)

# ── Mutable state ─────────────────────────────────────────────────
audio_out: asyncio.Queue = asyncio.Queue()          # PCM chunks -> speakers
audio_in: asyncio.Queue = asyncio.Queue(maxsize=5)  # mic PCM chunks
audio_stream = None                                  # PyAudio input stream
pya: pyaudio.PyAudio = pyaudio.PyAudio()
mic_active: bool = True
_mic_lock = threading.Lock()


def flush_audio() -> None:
    """Clear the audio output queue to stop playback immediately."""
    while not audio_out.empty():
        try:
            audio_out.get_nowait()
        except Exception:
            break


async def toggle_mic() -> None:
    """Toggle microphone on/off and notify the UI."""
    global mic_active
    with _mic_lock:
        mic_active = not mic_active
        active = mic_active
    await bus.set_status("listening" if active else "idle")
    await bus.emit("mic_toggle", {"active": active})


async def _listen_mic() -> None:
    """Continuously read PCM frames from the default input device."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
        input=True, input_device_index=mic_info["index"], frames_per_buffer=CHUNK_SIZE,
    )
    await bus.set_status("listening")
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, exception_on_overflow=False)
        with _mic_lock:
            active = mic_active
        if active:
            await audio_in.put({"data": data, "mime_type": "audio/pcm"})


async def _send_audio(session) -> None:
    """Forward microphone chunks to the Live API session."""
    while True:
        msg = await audio_in.get()
        with _mic_lock:
            active = mic_active
        if active:
            await session.send_realtime_input(audio=msg)


async def _receive_and_handle(session) -> None:
    """Process server responses: audio playback and tool calls."""
    while True:
        print("[Voice] Waiting for turn...", flush=True)
        turn = session.receive()
        async for response in turn:
            if response.server_content and response.server_content.model_turn:
                await bus.set_status("speaking")
                for part in response.server_content.model_turn.parts:
                    if part.inline_data and isinstance(part.inline_data.data, bytes):
                        audio_out.put_nowait(part.inline_data.data)
            if response.server_content and response.server_content.turn_complete:
                print("[Voice] Turn complete", flush=True)
                await bus.set_status("listening" if mic_active else "idle")
            if response.tool_call:
                for fc in response.tool_call.function_calls:
                    task = dict(fc.args).get("task", "")
                    print(f"\n  Task: {task}")
                    await bus.set_transcript(task)
                    summary = await run_brain_loop(task)
                    print(f"  Result: {summary.strip()}\n")
                    print("[Voice] Sending tool response...", flush=True)
                    await session.send_tool_response(function_responses=[
                        types.FunctionResponse(
                            id=fc.id, name="execute_task",
                            response={"result": summary[:500]}),
                    ])
                    print("[Voice] Tool response sent, waiting for voice reply...", flush=True)
                    await bus.set_status("listening" if mic_active else "idle")


async def _play_audio() -> None:
    """Write queued PCM data to the output device."""
    stream = await asyncio.to_thread(
        pya.open, format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE, output=True,
    )
    while True:
        data = await audio_out.get()
        await asyncio.to_thread(stream.write, data)


async def run_voice() -> None:
    """Start the voice session with auto-reconnect and exponential backoff."""
    backoff = BACKOFF_INITIAL
    while True:
        try:
            async with voice_client.aio.live.connect(
                model=VOICE_MODEL, config=VOICE_CONFIG,
            ) as session:
                print("Mac Pilot ready -- start talking!")
                backoff = BACKOFF_INITIAL
                await bus.set_status("listening")
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(_listen_mic())
                    tg.create_task(_send_audio(session))
                    tg.create_task(_receive_and_handle(session))
                    tg.create_task(_play_audio())
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"\nDisconnected: {e}")
            print(f"   Reconnecting in {backoff}s...\n")
            await bus.set_status("idle")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)
