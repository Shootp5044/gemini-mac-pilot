"""Gemini Mac Pilot — Entry Point.

Voice-controlled macOS agent powered by Gemini.
Launches the WebSocket backend, voice pipeline, and PyWebView overlay.
"""

import asyncio
import atexit
import signal
import sys
import threading

sys.stdout.reconfigure(line_buffering=True)


def _cleanup() -> None:
    """Release browser resources on exit."""
    try:
        from mac_pilot.tools.browser import cleanup_browser
        cleanup_browser()
    except Exception as e:
        print(f"Cleanup error: {e}")


atexit.register(_cleanup)


async def run_backend() -> None:
    """Run the full backend: WebSocket server + voice + UI commands."""
    from mac_pilot.ui.server import start_server, get_command_queue
    from mac_pilot.brain import run_brain_loop
    from mac_pilot.voice import run_voice, mic_active
    from mac_pilot.events import bus

    await start_server()
    queue = get_command_queue()

    async def handle_ui_commands() -> None:
        """Process text commands submitted through the UI bar."""
        while True:
            task = await queue.get()
            if not task or not task.strip():
                continue
            print(f"\nTask (text): {task}")
            try:
                result = await run_brain_loop(task)
                print(f"Done: {result[:100]}\n")
            except Exception as e:
                print(f"Error: {e}\n")
            from mac_pilot.voice import mic_active as _mic
            await bus.set_status("listening" if _mic else "idle")

    async with asyncio.TaskGroup() as tg:
        tg.create_task(handle_ui_commands())
        tg.create_task(run_voice())


async def run_cli() -> None:
    """CLI mode — text input only, no voice, no UI."""
    import time
    from mac_pilot.brain import run_brain_loop

    print("   Mode: CLI (type commands, 'q' to quit)\n")
    while True:
        try:
            task = input("🎯 → ")
        except EOFError:
            break
        if not task or task.strip().lower() == "q":
            break
        t0 = time.time()
        try:
            result = await run_brain_loop(task)
            print(f"\n✅ {result} ({time.time()-t0:.0f}s)\n")
        except Exception as e:
            print(f"\n❌ {e}\n")


def _handle_signal(sig: int, _frame) -> None:
    """Handle SIGINT / SIGTERM for graceful shutdown."""
    print("\nShutting down...")
    _cleanup()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    from mac_pilot.config import BRAIN_MODEL, VOICE_MODEL

    mode = sys.argv[1] if len(sys.argv) > 1 else "voice"

    print("Gemini Mac Pilot v1.0")
    print(f"   Brain: {BRAIN_MODEL} (Vertex AI)")
    print(f"   Voice: {VOICE_MODEL}")
    print("=" * 50)

    if mode == "cli":
        try:
            asyncio.run(run_cli())
        except KeyboardInterrupt:
            print("\nBye!")
    else:
        from mac_pilot.ui.app import create_window, start_webview

        create_window()

        def _run() -> None:
            asyncio.run(run_backend())

        threading.Thread(target=_run, daemon=True).start()

        try:
            start_webview()
        except KeyboardInterrupt:
            print("\nBye!")
        finally:
            _cleanup()
