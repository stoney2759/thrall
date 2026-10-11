from __future__ import annotations
import asyncio
import sys
import uuid

from schemas.message import Message, Role, Transport
from bootstrap import state

_CLI_SESSION_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "thrall:cli:local")
_CLI_USER_ID = "cli"


def _build_message(content: str) -> Message:
    return Message(
        session_id=_CLI_SESSION_ID,
        role=Role.USER,
        content=content,
        transport=Transport.CLI,
        user_id=_CLI_USER_ID,
    )


def _handle_command(line: str) -> bool:
    """Returns True if the line was a command (consumed), False if it should be forwarded to Thrall."""
    parts = line.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/exit", "/quit", "/q"):
        print("Goodbye.")
        sys.exit(0)

    from commands.base import CommandContext
    from commands.registry import dispatch
    ctx = CommandContext(
        user_id=_CLI_USER_ID,
        session_id=_CLI_SESSION_ID,
        transport=Transport.CLI,
        args=parts[1:] if len(parts) > 1 else [],
    )
    result = asyncio.get_event_loop().run_until_complete(dispatch(cmd, ctx))
    if result is None:
        return False

    print(result)
    if cmd == "/help":
        print("  /exit, /quit, /q   — exit")
    return True


async def _loop() -> None:
    from thrall.coordinator import receive
    from services import ask_user_channel, progress

    print("Thrall CLI — type /help for commands, /exit to quit.\n")
    running: asyncio.Task | None = None

    async def show(text: str) -> None:
        print(f"\n{text}\n")

    async def show_step(text: str) -> None:
        print(f"  · {text}")

    async def run(message) -> None:
        # Tasks run in the background so the prompt stays live for permission
        # answers and mid-task messages (the coordinator queues those).
        progress.register(message.session_id, show_step)
        try:
            response = await receive(message)
            print(f"\n{response}\n")
        except Exception as e:
            state.log_error(f"CLI handler error: {e}")
            print(f"Error: {e}\n")
        finally:
            progress.unregister(message.session_id, show_step)

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, lambda: input("> "))
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        line = line.strip()
        if not line:
            continue

        message = _build_message(line)
        ask_user_channel.register_sender(message.session_id, show)
        # An answer to a pending question (e.g. a permission prompt) goes to the waiting tool
        if ask_user_channel.has_pending(message.session_id):
            ask_user_channel.deliver_reply(message.session_id, line)
            continue

        if line.startswith("/"):
            if _handle_command(line):
                continue

        if running is not None and not running.done():
            print(f"  {await receive(message)}")  # queued into the running task
            continue
        running = asyncio.create_task(run(message))


def run() -> None:
    asyncio.run(_loop())
