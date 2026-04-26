from __future__ import annotations
import asyncio
import sys
import uuid
from datetime import datetime, timezone

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


def _print_status() -> None:
    cfg = state.get_config()
    uptime = datetime.now(timezone.utc) - datetime.fromisoformat(
        cfg.get("thrall", {}).get("started_at", datetime.now(timezone.utc).isoformat())
    )
    print(f"  Active tasks : {state.get_active_task_count()}")
    print(f"  Total cost   : ${state.get_total_cost():.4f}")
    print(f"  Provider     : {cfg.get('llm', {}).get('provider', 'unknown')}")
    print(f"  Model        : {state.get_model_override() or cfg.get('llm', {}).get('model', 'unknown')}")
    print(f"  Session      : {_CLI_SESSION_ID}")


def _handle_command(line: str) -> bool:
    """Returns True if the line was a command (consumed), False if it should be forwarded to Thrall."""
    parts = line.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/exit", "/quit", "/q"):
        print("Goodbye.")
        sys.exit(0)

    if cmd == "/help":
        from commands.base import CommandContext
        from commands.registry import dispatch
        from schemas.message import Transport
        ctx = CommandContext(user_id=_CLI_USER_ID, session_id=_CLI_SESSION_ID, transport=Transport.CLI, args=[])
        result = asyncio.get_event_loop().run_until_complete(dispatch("help", ctx))
        print(result or "No commands found.")
        print("  /exit, /quit, /q   — exit")
        return True

    if cmd == "/status":
        _print_status()
        return True

    if cmd == "/clear":
        from services import session_memory
        session_memory.clear(_CLI_SESSION_ID)
        print("Session memory cleared.")
        return True

    if cmd == "/model":
        if len(parts) < 2:
            current = state.get_model_override() or state.get_config().get("llm", {}).get("model", "unknown")
            print(f"Current model: {current}")
        else:
            state.set_model_override(parts[1])
            print(f"Model switched to: {parts[1]}")
        return True

    if cmd == "/memory":
        from commands.base import CommandContext
        from commands.registry import dispatch
        from schemas.message import Transport
        args = parts[1:] if len(parts) > 1 else []
        ctx = CommandContext(user_id=_CLI_USER_ID, session_id=_CLI_SESSION_ID, transport=Transport.CLI, args=args)
        result = asyncio.get_event_loop().run_until_complete(dispatch("memory", ctx))
        print(result or "No memory data.")
        return True

    if cmd == "/heartbeat":
        from commands.base import CommandContext
        from commands.registry import dispatch
        from schemas.message import Transport
        args = parts[1:] if len(parts) > 1 else []
        ctx = CommandContext(user_id=_CLI_USER_ID, session_id=_CLI_SESSION_ID, transport=Transport.CLI, args=args)
        result = asyncio.get_event_loop().run_until_complete(dispatch("heartbeat", ctx))
        print(result or "Done.")
        return True

    if cmd == "/cron":
        from commands.base import CommandContext
        from commands.registry import dispatch
        from schemas.message import Transport
        args = parts[1:] if len(parts) > 1 else []
        ctx = CommandContext(user_id=_CLI_USER_ID, session_id=_CLI_SESSION_ID, transport=Transport.CLI, args=args)
        result = asyncio.get_event_loop().run_until_complete(dispatch("cron", ctx))
        print(result or "Done.")
        return True

    if cmd == "/profile":
        from commands.base import CommandContext
        from commands.registry import dispatch
        from schemas.message import Transport
        args = parts[1:] if len(parts) > 1 else []
        ctx = CommandContext(user_id=_CLI_USER_ID, session_id=_CLI_SESSION_ID, transport=Transport.CLI, args=args)
        result = asyncio.get_event_loop().run_until_complete(dispatch("profile", ctx))
        print(result or "Done.")
        return True

    return False


async def _loop() -> None:
    from thrall.coordinator import receive

    print("Thrall CLI — type /help for commands, /exit to quit.\n")

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, lambda: input("> "))
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            if _handle_command(line):
                continue

        message = _build_message(line)
        try:
            response = await receive(message)
            print(f"\n{response}\n")
        except Exception as e:
            state.log_error(f"CLI handler error: {e}")
            print(f"Error: {e}\n")


def run() -> None:
    asyncio.run(_loop())
