from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone

from telegram import Update, BotCommand
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import tempfile
import os

from schemas.message import Message, Role, Transport
from thrall.coordinator import receive
from transports.telegram import auth
from services import session_memory
from bootstrap import state

_TG_MAX_LENGTH = 4096


# ── Session ID ────────────────────────────────────────────────────────────────

def _session_id(user_id: int) -> uuid.UUID:
    # Stable UUID per Telegram user — persists across bot restarts
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{user_id}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send(update: Update, text: str) -> None:
    """Split and send long responses within Telegram's 4096 char limit."""
    chunks = [text[i:i + _TG_MAX_LENGTH] for i in range(0, len(text), _TG_MAX_LENGTH)]
    for chunk in chunks:
        await update.message.reply_text(chunk)


def _build_message(update: Update) -> Message:
    user = update.effective_user
    return Message(
        session_id=_session_id(user.id),
        role=Role.USER,
        content=update.message.text or "",
        transport=Transport.TELEGRAM,
        user_id=str(user.id),
    )


def _is_allowed(update: Update) -> bool:
    return auth.is_allowed(update.effective_user.id)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return
    user = update.effective_user
    await update.message.reply_text(
        f"Thrall online. Ready.\n\nSession: {_session_id(user.id)}\n\nType anything to begin."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=[],
    )
    response = await dispatch("help", ctx)
    await update.message.reply_text(response or "No commands found.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    uptime = datetime.now(timezone.utc) - datetime.fromisoformat(
        state.get_config().get("thrall", {}).get("started_at", datetime.now(timezone.utc).isoformat())
    )
    lines = [
        f"*Thrall Status*",
        f"Active tasks: {state.get_active_task_count()}",
        f"Total cost: ${state.get_total_cost():.4f}",
        f"Session: {_session_id(update.effective_user.id)}",
        f"Provider: {state.get_config().get('llm', {}).get('provider', 'unknown')}",
        f"Model: {state.get_model_override() or state.get_config().get('llm', {}).get('model', 'unknown')}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    user = update.effective_user
    session_memory.clear(_session_id(user.id))
    await update.message.reply_text("Session memory cleared.")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    if not context.args:
        current = state.get_model_override() or state.get_config().get("llm", {}).get("model", "unknown")
        await update.message.reply_text(f"Current model: `{current}`\n\nUsage: /model <model-name>", parse_mode=ParseMode.MARKDOWN)
        return
    model = context.args[0]
    state.set_model_override(model)
    await update.message.reply_text(f"Model switched to: `{model}`", parse_mode=ParseMode.MARKDOWN)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=list(context.args or []),
    )
    response = await dispatch("memory", ctx)
    await update.message.reply_text(response or "No memory data.")


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from bootstrap.startup import reload
    from scheduler import runner
    reload()
    runner.set_bot(context.bot)
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    for uid in allowed:
        try:
            await context.bot.send_message(chat_id=uid, text="Thrall online.")
        except Exception:
            pass


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("health", ctx)
    await update.message.reply_text(response or "OK")


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("jobs", ctx)
    await update.message.reply_text(response or "No jobs.")


async def cmd_deljob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=list(context.args or []))
    response = await dispatch("deljob", ctx)
    await update.message.reply_text(response or "Done.")


async def _compact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch(command, ctx)
    await _send(update, response or "Done.")


async def cmd_compact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    await _compact_handler(update, context, "compact")


async def cmd_compact_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _compact_handler(update, context, "compact_ok")


async def cmd_compact_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _compact_handler(update, context, "compact_cancel")


async def cmd_heartbeat_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=list(context.args or []),
    )
    response = await dispatch("heartbeat", ctx)
    await update.message.reply_text(response or "Done.")


async def cmd_cron(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=list(context.args or []),
    )
    response = await dispatch("cron", ctx)
    await update.message.reply_text(response or "Done.")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from thrall.tasks import pool
    active = pool.list_active()
    if not active:
        await update.message.reply_text("No active tasks.")
        return
    lines = [f"*Active Tasks* ({len(active)})"]
    for task in active:
        lines.append(f"• `{task.id}` [{task.type.value}] {task.status.value}\n  {task.brief[:60]}...")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    usage = state.get_model_usage()
    lines = [f"*Token Usage*\nTotal cost: ${state.get_total_cost():.4f}\n"]
    for model, u in usage.items():
        lines.append(f"`{model}`\n  In: {u.input_tokens:,}  Out: {u.output_tokens:,}  Cost: ${u.cost_usd:.4f}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── Voice mode state ──────────────────────────────────────────────────────────

_voice_mode: set[int] = set()  # user IDs with voice mode enabled

_SPEAK_TRIGGERS = (
    "read aloud", "say aloud", "speak that", "out loud", "voice that",
    "say it aloud", "read it aloud",
)


def _wants_audio(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in _SPEAK_TRIGGERS)


async def _send_audio(update: Update, text: str) -> None:
    import io
    try:
        from services.tts.router import synthesise, needs_approval, cost_summary
        from transports.telegram.audio import SEND_AS_VOICE, OUTPUT_FORMAT

        if needs_approval(text):
            await update.message.reply_text(
                f"Audio generation requires approval:\n{cost_summary(text)}\n\nSay 'yes, generate audio' to confirm."
            )
            return

        audio_bytes = await synthesise(text, output_format=OUTPUT_FORMAT)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "response.ogg"

        if SEND_AS_VOICE:
            await update.message.reply_voice(voice=audio_file)
        else:
            await update.message.reply_document(document=audio_file, filename="thrall_response.ogg")

    except Exception as e:
        state.log_error(f"TTS delivery error: {e}")
        await update.message.reply_text(f"{text}\n\n⚠️ Voice failed: {e}")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=list(context.args or []),
    )
    response = await dispatch("profile", ctx)
    await update.message.reply_text(response or "No profile info.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=[],
    )
    response = await dispatch("stop", ctx)
    await update.message.reply_text(response or "Done.")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=[],
    )
    response = await dispatch("approve", ctx)
    if not response:
        await update.message.reply_text("Nothing to approve.")
        return
    use_audio = user.id in _voice_mode
    if use_audio:
        await _send_audio(update, response)
    else:
        await _send(update, response)


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    url = " ".join(context.args) if context.args else ""
    ctx = CommandContext(
        user_id=str(user.id),
        session_id=_session_id(user.id),
        transport=Transport.TELEGRAM,
        args=url,
    )
    response = await dispatch("watch", ctx)
    if not response:
        await update.message.reply_text("Usage: /watch <video_url>")
        return
    use_audio = user.id in _voice_mode
    if use_audio:
        await _send_audio(update, response)
    else:
        await _send(update, response)


# ── Commands for voice mode ───────────────────────────────────────────────────

async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    uid = update.effective_user.id
    if uid in _voice_mode:
        _voice_mode.discard(uid)
        await update.message.reply_text("Voice mode off.")
    else:
        _voice_mode.add(uid)
        await update.message.reply_text("Voice mode on — responses will be spoken.")


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised. Your user ID is not on the allowlist.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    message = _build_message(update)
    user_text = update.message.text or ""
    uid = update.effective_user.id

    try:
        response = await receive(message)
        use_audio = uid in _voice_mode or _wants_audio(user_text)
        if use_audio:
            await _send_audio(update, response)
        else:
            await _send(update, response)
    except Exception as e:
        import traceback
        state.log_error(f"Telegram handler error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(f"Error: {e}")


# ── Voice handler ─────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        audio_bytes = await tg_file.download_as_bytearray()

        mime = getattr(voice, "mime_type", "") or ""
        ext = ".ogg" if "ogg" in mime else ".mp4" if "mp4" in mime or "mpeg" in mime else ".ogg"

        from services.transcription.router import transcribe
        transcript = await transcribe(bytes(audio_bytes), filename=f"audio{ext}")

        if not transcript:
            await update.message.reply_text("Could not transcribe audio — got empty result.")
            return

        await update.message.reply_text(f"_{transcript}_", parse_mode=ParseMode.MARKDOWN)

        message = Message(
            session_id=_session_id(update.effective_user.id),
            role=Role.USER,
            content=transcript,
            transport=Transport.TELEGRAM,
            user_id=str(update.effective_user.id),
        )
        response = await receive(message)
        # Voice in → voice out always
        await _send_audio(update, response)

    except Exception as e:
        state.log_error(f"Voice handler error: {e}")
        await update.message.reply_text(f"Voice transcription failed: {e}")


# ── Document handler ──────────────────────────────────────────────────────────

def _uploads_dir():
    from pathlib import Path
    workspace = state.get_workspace_dir() or "."
    d = Path(workspace) / "uploads"
    d.mkdir(exist_ok=True)
    return d


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return

    doc = update.message.document
    if not doc:
        return

    mime = doc.mime_type or ""
    filename = doc.file_name or "file"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    supported = ext in ("pdf", "docx", "txt") or "pdf" in mime or "wordprocessingml" in mime or "text/plain" in mime
    if not supported:
        await update.message.reply_text(f"Unsupported file type: {mime or filename}\nSupported: pdf, docx, txt")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        save_path = _uploads_dir() / filename
        if save_path.exists():
            stem, suffix = save_path.stem, save_path.suffix
            counter = 1
            while save_path.exists():
                save_path = _uploads_dir() / f"{stem}_{counter}{suffix}"
                counter += 1

        save_path.write_bytes(bytes(file_bytes))

        caption = (update.message.caption or "").strip()
        lines = [f"[Uploaded file: {filename}]", f"Path: {save_path}"]
        if caption:
            lines.append(f"User note: {caption}")

        message = Message(
            session_id=_session_id(update.effective_user.id),
            role=Role.USER,
            content="\n".join(lines),
            transport=Transport.TELEGRAM,
            user_id=str(update.effective_user.id),
        )
        response = await receive(message)
        await _send(update, response)

    except Exception as e:
        state.log_error(f"Document handler error: {e}")
        await update.message.reply_text(f"File handling failed: {e}")


# ── Photo handler ─────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            media_type = "image/jpeg"
        elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
            photo = update.message.document
            media_type = update.message.document.mime_type or "image/jpeg"
        else:
            await update.message.reply_text("No image found in message.")
            return

        tg_file = await context.bot.get_file(photo.file_id)
        image_bytes = await tg_file.download_as_bytearray()
        caption = (update.message.caption or "").strip()

        from services.vision.openai import describe
        description = await describe(bytes(image_bytes), media_type=media_type)

        if not description:
            await update.message.reply_text("Could not analyse image.")
            return

        content = f"[Image]\n{description}"
        if caption:
            content += f"\n\n[User context: {caption}]"

        message = Message(
            session_id=_session_id(update.effective_user.id),
            role=Role.USER,
            content=content,
            transport=Transport.TELEGRAM,
            user_id=str(update.effective_user.id),
        )
        response = await receive(message)
        await _send(update, response)

    except Exception as e:
        state.log_error(f"Photo handler error: {e}")
        await update.message.reply_text(f"Image processing failed: {e}")


# ── Error handler ─────────────────────────────────────────────────────────────

async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    state.log_error(f"Telegram error: {context.error}")


# ── Bot setup + run ───────────────────────────────────────────────────────────

def build_application() -> Application:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    # concurrent_updates=True lets /stop and other commands be dispatched
    # while a long-running receive() is still awaiting on another handler.
    # Without this, the bot processes updates sequentially and /stop cannot
    # interrupt an in-progress reasoning loop.
    app = Application.builder().token(token).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("heartbeat", cmd_heartbeat_add))
    app.add_handler(CommandHandler("cron", cmd_cron))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("deljob", cmd_deljob))
    app.add_handler(CommandHandler("compact", cmd_compact))
    app.add_handler(CommandHandler("compact_ok", cmd_compact_ok))
    app.add_handler(CommandHandler("compact_cancel", cmd_compact_cancel))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("watch", cmd_watch))

    # Voice and audio messages
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # PDF, DOCX, TXT document uploads
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.Document.IMAGE, handle_document))

    # Photo and image documents
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))

    # All other text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    app.add_error_handler(handle_error)

    return app


async def _start_mcp() -> None:
    try:
        from services.mcp.manager import MCPClientManager
        from services.mcp import executor as mcp_executor
        from thrall.tools import registry as tools
        mcp_config = state.get_config().get("mcp", {})
        manager = MCPClientManager()
        await manager.connect_all(mcp_config)
        mcp_executor.set_manager(manager)
        mcp_tools = manager.all_tools()
        if mcp_tools:
            tools.register_mcp_tools(mcp_tools)
            state.log_error(f"MCP: registered {len(mcp_tools)} tools from {manager.available_servers()}")
    except Exception as e:
        state.log_error(f"MCP startup error: {e}")


async def _register_task_delivery(app: Application) -> None:
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])

    async def _deliver(task) -> None:
        from schemas.task import TaskStatus
        if task.status == TaskStatus.DONE:
            result = task.result or "(agent completed but returned no output)"
            text = f"Agent task complete:\n\n{result}"
            if task.result and task.profile and task.profile.name and task.profile.name != "default":
                from thrall.tasks.continuation_store import save
                save(task.profile.name, task.brief, task.result)
        elif task.status == TaskStatus.FAILED:
            text = f"Agent task failed:\n\n{task.error or '(no error details)'}"
        else:
            return
        for uid in allowed:
            try:
                await app.bot.send_message(chat_id=uid, text=text[:4096])
            except Exception:
                pass

    from thrall.tasks.pool import register_completion_callback
    register_completion_callback(_deliver)


async def set_commands(app: Application) -> None:
    await _register_task_delivery(app)
    await _start_mcp()
    await app.bot.set_my_commands([
        BotCommand("start", "Initialise session"),
        BotCommand("help", "List commands"),
        BotCommand("status", "Active tasks, cost, model"),
        BotCommand("clear", "Clear session memory"),
        BotCommand("model", "Switch LLM model"),
        BotCommand("tasks", "List active tasks"),
        BotCommand("cost", "Token usage and spend"),
        BotCommand("restart", "Reload config and state"),
        BotCommand("memory", "Inspect session memory: /memory [list|clear|search <query>]"),
        BotCommand("health", "System health and errors"),
        BotCommand("heartbeat", "Add recurring job: /heartbeat 30m <task>"),
        BotCommand("cron", "Add timed job: /cron 18:00 <task>"),
        BotCommand("jobs", "List scheduled jobs"),
        BotCommand("deljob", "Delete a job by ID"),
        BotCommand("compact", "Compact session memory"),
        BotCommand("compact_ok", "Confirm and apply compact"),
        BotCommand("compact_cancel", "Discard compact draft"),
        BotCommand("profile", "Show or switch personality profile: /profile [name]"),
        BotCommand("voice", "Toggle voice mode on/off"),
        BotCommand("stop", "Cancel the currently running task"),
        BotCommand("approve", "Approve a pending proposal and execute"),
        BotCommand("watch", "Process a video: download, transcribe, extract frames, store in memory"),
    ])
    from scheduler import runner
    runner.start(app.bot)
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    for uid in allowed:
        try:
            await app.bot.send_message(chat_id=uid, text="Thrall online.")
        except Exception:
            pass


async def _shutdown(app) -> None:
    from scheduler import runner
    runner.stop()


def run() -> None:
    app = build_application()
    app.post_init = set_commands
    app.post_shutdown = _shutdown
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )
