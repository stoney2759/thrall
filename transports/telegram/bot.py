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
    text = (
        "*Thrall Commands*\n\n"
        "/start — initialise session\n"
        "/help — this message\n"
        "/status — active tasks, uptime, cost\n"
        "/clear — clear session memory\n"
        "/model `<name>` — switch LLM model\n"
        "/tasks — list active tasks\n"
        "/cost — token usage and spend"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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


async def _add_job_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str) -> None:
    if not _is_allowed(update):
        return
    args = list(context.args or [])
    if len(args) < 2:
        usage = f"Usage: /{job_type} <schedule> <task> [agent=<name>] [silent]"
        if job_type == "heartbeat":
            usage += "\nExample: /heartbeat 30m summarise the workspace"
        else:
            usage += "\nExample: /cron 'every monday at 9am' check the news and report"
        await update.message.reply_text(usage)
        return

    raw_schedule = args[0]
    output_mode = "silent" if "silent" in args else "verbose"
    agent = next((a.split("=", 1)[1] for a in args if a.startswith("agent=")), None)
    task_parts = [a for a in args[1:] if not a.startswith("agent=") and a != "silent"]
    task = " ".join(task_parts)

    from scheduler.job import Job
    from scheduler.parser import parse_schedule
    from scheduler import store
    import uuid as _uuid
    from datetime import datetime, timezone as _tz

    try:
        parsed = await parse_schedule(raw_schedule)
    except ValueError as e:
        await update.message.reply_text(f"Could not parse schedule: {e}")
        return

    job = Job(
        id=_uuid.uuid4().hex[:8],
        type=job_type,
        schedule=raw_schedule,
        cron_expr=parsed.cron_expr,
        human_summary=parsed.human_summary,
        task=task,
        agent=agent,
        output_mode=output_mode,
        created_at=datetime.now(_tz.utc).isoformat(),
    )
    store.add_job(job)
    agent_str = f" | agent: {agent}" if agent else ""
    await update.message.reply_text(
        f"Job {job.id} scheduled\nSchedule: {parsed.human_summary}\nTask: {task[:100]}{agent_str}"
    )


async def cmd_heartbeat_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _add_job_handler(update, context, "heartbeat")


async def cmd_cron(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _add_job_handler(update, context, "cron")


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


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised. Your user ID is not on the allowlist.")
        return

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    message = _build_message(update)

    try:
        response = await receive(message)
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
        await _send(update, response)

    except Exception as e:
        state.log_error(f"Voice handler error: {e}")
        await update.message.reply_text(f"Voice transcription failed: {e}")


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

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("heartbeat", cmd_heartbeat_add))
    app.add_handler(CommandHandler("cron", cmd_cron))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("deljob", cmd_deljob))
    app.add_handler(CommandHandler("compact", cmd_compact))
    app.add_handler(CommandHandler("compact_ok", cmd_compact_ok))
    app.add_handler(CommandHandler("compact_cancel", cmd_compact_cancel))

    # Voice and audio messages
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

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
        BotCommand("health", "System health and errors"),
        BotCommand("heartbeat", "Add recurring job: /heartbeat 30m <task>"),
        BotCommand("cron", "Add timed job: /cron 18:00 <task>"),
        BotCommand("jobs", "List scheduled jobs"),
        BotCommand("deljob", "Delete a job by ID"),
        BotCommand("compact", "Compact session memory"),
        BotCommand("compact_ok", "Confirm and apply compact"),
        BotCommand("compact_cancel", "Discard compact draft"),
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
