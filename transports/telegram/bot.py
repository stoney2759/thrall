from __future__ import annotations
import asyncio
import os
import uuid
import tempfile
from dataclasses import dataclass, field

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.error import TimedOut as TelegramTimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from schemas.message import Message, Role, Transport
from thrall.coordinator import receive
from transports.telegram import auth
from bootstrap import state
from constants.telegram import TG_MAX_LENGTH, TG_MEDIA_GROUP_DELAY_SECONDS, TG_CHOICE_PREFIX
from constants.permissions import PERMISSION_CHOICE_LABELS


# ── Bot reference (for proactive sends from other transports) ─────────────────

_app: Application | None = None


@dataclass
class _MediaGroupItem:
    update_id: int
    kind: str
    file_id: str
    media_type: str
    filename: str
    caption: str


@dataclass
class _MediaGroup:
    chat_id: int
    user_id: str
    session_id: uuid.UUID
    bot: object
    items: list[_MediaGroupItem] = field(default_factory=list)
    flush_task: asyncio.Task | None = None


_media_groups: dict[tuple[int, str], _MediaGroup] = {}
_media_group_lock = asyncio.Lock()


async def send_to_primary_user(text: str) -> None:
    """Send a message to the primary Telegram user. Used by webapp transport for bidirectional sync."""
    if _app is None:
        return
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    if not allowed:
        return
    chunks = [text[i:i + TG_MAX_LENGTH] for i in range(0, len(text), TG_MAX_LENGTH)]
    for chunk in chunks:
        try:
            await _app.bot.send_message(chat_id=allowed[0], text=chunk)
        except Exception:
            pass


_choice_prompts: dict[uuid.UUID, object] = {}  # session -> last question message sent with buttons


def _register_choice_ui(bot, chat_id: int, session_id: uuid.UUID) -> None:
    """Questions with choices (permission prompts) get tap buttons; once answered the message is
    edited to a one-line record of the outcome (buttons removed)."""
    from services import ask_user_channel

    async def show(question: str, choices: list[str]) -> None:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(PERMISSION_CHOICE_LABELS.get(c, c), callback_data=f"{TG_CHOICE_PREFIX}{c}")
            for c in choices
        ]])
        _choice_prompts[session_id] = await bot.send_message(chat_id=chat_id, text=question, reply_markup=keyboard)

    async def resolve(outcome: str) -> None:
        prompt = _choice_prompts.pop(session_id, None)
        if prompt is not None:
            await bot.edit_message_text(chat_id=chat_id, message_id=prompt.message_id, text=outcome, reply_markup=None)

    ask_user_channel.register_choice_ui(session_id, show, resolve)


async def handle_choice_tap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A tap on a question button — delivered exactly like a typed answer."""
    from services import ask_user_channel
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        return
    session = _session_id(update.effective_user.id)
    if ask_user_channel.has_pending(session):
        ask_user_channel.deliver_reply(session, query.data[len(TG_CHOICE_PREFIX):])
        await query.answer()
    else:
        await query.answer("That question has already been answered or expired.")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


async def _receive_with_progress(bot, chat_id: int, message: Message) -> str:
    """receive() with a live "⏳ Working…" status message, edited as steps happen and removed at the end.
    A message sent while a task is already running is just queued — the running task's board stays."""
    from services import progress
    if state.has_active_task(str(message.session_id)):
        return await receive(message)
    board = progress.StatusBoard(
        send=lambda text: bot.send_message(chat_id=chat_id, text=text),
        edit=lambda handle, text: bot.edit_message_text(chat_id=chat_id, message_id=handle.message_id, text=text),
        delete=lambda handle: bot.delete_message(chat_id=chat_id, message_id=handle.message_id),
    )
    listener = board.add
    progress.register(message.session_id, listener)
    try:
        return await receive(message)
    finally:
        progress.unregister(message.session_id, listener)
        await board.close()


# ── Session ID ────────────────────────────────────────────────────────────────

def _session_id(user_id: int) -> uuid.UUID:
    # Stable UUID per Telegram user — persists across bot restarts
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{user_id}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send(update: Update, text: str) -> None:
    """Split and send long responses within Telegram's 4096 char limit."""
    chunks = [text[i:i + TG_MAX_LENGTH] for i in range(0, len(text), TG_MAX_LENGTH)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except TelegramTimedOut:
            await asyncio.sleep(3)
            await update.message.reply_text(chunk)


async def _send_to_chat(bot, chat_id: int, text: str) -> None:
    chunks = [text[i:i + TG_MAX_LENGTH] for i in range(0, len(text), TG_MAX_LENGTH)]
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk)


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
        args=list(context.args or []),
    )
    response = await dispatch("help", ctx)
    await update.message.reply_text(response or "No commands found.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("status", ctx)
    await update.message.reply_text(response or "OK")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("clear", ctx)
    await update.message.reply_text(response or "Done.")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    response = await dispatch("model", ctx)
    await update.message.reply_text(response or "Done.")


async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    response = await dispatch("auth", ctx)
    await update.message.reply_text(response or "Done.")


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
    from commands.base import CommandContext
    from commands.registry import dispatch
    from scheduler import runner
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    await dispatch("restart", ctx)
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
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("tasks", ctx)
    await update.message.reply_text(response or "No active tasks.")


async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("cost", ctx)
    await update.message.reply_text(response or "No usage data.", parse_mode=ParseMode.MARKDOWN)


async def cmd_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM,
                         args=list(context.args or []))
    response = await dispatch("permissions", ctx)
    await update.message.reply_text(response or "Unavailable.")


async def cmd_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    from commands.base import CommandContext
    from commands.registry import dispatch
    user = update.effective_user
    ctx = CommandContext(user_id=str(user.id), session_id=_session_id(user.id), transport=Transport.TELEGRAM, args=[])
    response = await dispatch("tokens", ctx)
    await update.message.reply_text(response or "No token data.", parse_mode=ParseMode.MARKDOWN)


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
        args=list(context.args or []),
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
    try:
        response = await dispatch("watch", ctx)
        if not response:
            await update.message.reply_text("Usage: /watch <video_url>")
            return
        use_audio = user.id in _voice_mode
        if use_audio:
            await _send_audio(update, response)
        else:
            await _send(update, response)
    except Exception as e:
        import traceback
        state.log_error(f"cmd_watch error: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(f"Error: {e}")


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

    uid = update.effective_user.id
    session_id = _session_id(uid)
    user_text = update.message.text or ""

    # Register a sender so interaction_ask_user can push questions to this user
    from services import ask_user_channel
    chat_id = update.effective_chat.id

    async def _send_to_user(text: str) -> None:
        await context.bot.send_message(chat_id=chat_id, text=text)

    ask_user_channel.register_sender(session_id, _send_to_user)
    _register_choice_ui(context.bot, chat_id, session_id)

    # If a tool is waiting for user input, deliver the reply directly and stop
    if ask_user_channel.has_pending(session_id):
        ask_user_channel.deliver_reply(session_id, user_text)
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    message = _build_message(update)

    response: str | None = None
    try:
        response = await _receive_with_progress(update.get_bot(), update.effective_chat.id, message)
        use_audio = uid in _voice_mode or _wants_audio(user_text)
        if use_audio:
            await _send_audio(update, response)
        else:
            await _send(update, response)
        # Mirror conversation to webapp (API server is a separate process — local HTTP)
        from services.transport_sync import push_to_webapp
        if await push_to_webapp("user", user_text):
            await push_to_webapp("assistant", response)
    except Exception as e:
        import traceback
        state.log_error(f"Telegram handler error: {e}\n{traceback.format_exc()}")
        if response is not None:
            # Coordinator finished — delivery failed; retry once with plain text
            try:
                await update.message.reply_text(response[:TG_MAX_LENGTH])
            except Exception:
                pass
        else:
            await update.message.reply_text(f"Error: {e}")


# ── Voice handler ─────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return

    from services import ask_user_channel
    _session = _session_id(update.effective_user.id)
    _chat_id = update.effective_chat.id

    async def _send_to_user(text: str) -> None:
        await context.bot.send_message(chat_id=_chat_id, text=text)

    ask_user_channel.register_sender(_session, _send_to_user)
    _register_choice_ui(context.bot, _chat_id, _session)

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
        response = await _receive_with_progress(update.get_bot(), update.effective_chat.id, message)
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


def _unique_upload_path(filename: str):
    save_path = _uploads_dir() / filename
    if save_path.exists():
        stem, suffix = save_path.stem, save_path.suffix
        counter = 1
        while save_path.exists():
            save_path = _uploads_dir() / f"{stem}_{counter}{suffix}"
            counter += 1
    return save_path


def _document_supported(filename: str, mime: str) -> bool:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return (
        ext in ("pdf", "docx", "txt", "csv", "xlsx")
        or "pdf" in mime
        or "wordprocessingml" in mime
        or "text/plain" in mime
        or "text/csv" in mime
        or "spreadsheetml" in mime
    )


async def _register_ask_sender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services import ask_user_channel
    session = _session_id(update.effective_user.id)
    chat_id = update.effective_chat.id

    async def _send_to_user(text: str) -> None:
        await context.bot.send_message(chat_id=chat_id, text=text)

    ask_user_channel.register_sender(session, _send_to_user)
    _register_choice_ui(context.bot, chat_id, session)


async def _enqueue_media_group(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item: _MediaGroupItem,
) -> None:
    key = (update.effective_chat.id, update.message.media_group_id)
    async with _media_group_lock:
        group = _media_groups.get(key)
        if group is None:
            group = _MediaGroup(
                chat_id=update.effective_chat.id,
                user_id=str(update.effective_user.id),
                session_id=_session_id(update.effective_user.id),
                bot=context.bot,
            )
            _media_groups[key] = group

        group.items.append(item)
        if group.flush_task and not group.flush_task.done():
            group.flush_task.cancel()
        group.flush_task = asyncio.create_task(_flush_media_group_after_delay(key))


async def _flush_media_group_after_delay(key: tuple[int, str]) -> None:
    try:
        await asyncio.sleep(TG_MEDIA_GROUP_DELAY_SECONDS)
    except asyncio.CancelledError:
        return

    async with _media_group_lock:
        group = _media_groups.pop(key, None)

    if group is None:
        return

    await _process_media_group(group)


async def _process_media_group(group: _MediaGroup) -> None:
    try:
        await group.bot.send_chat_action(chat_id=group.chat_id, action=ChatAction.TYPING)
        lines: list[str] = [f"[Telegram media group: {len(group.items)} item(s)]"]

        for index, item in enumerate(sorted(group.items, key=lambda x: x.update_id), start=1):
            if item.kind == "image":
                lines.extend(await _describe_media_group_image(group.bot, item, index))
            else:
                lines.extend(await _save_media_group_document(group.bot, item, index))

        message = Message(
            session_id=group.session_id,
            role=Role.USER,
            content="\n".join(lines),
            transport=Transport.TELEGRAM,
            user_id=group.user_id,
        )
        response = await _receive_with_progress(group.bot, group.chat_id, message)
        await _send_to_chat(group.bot, group.chat_id, response)
    except Exception as e:
        state.log_error(f"Telegram media group handler error: {e}")
        await _send_to_chat(group.bot, group.chat_id, f"Media group handling failed: {e}")


async def _describe_media_group_image(bot, item: _MediaGroupItem, index: int) -> list[str]:
    tg_file = await bot.get_file(item.file_id)
    image_bytes = await tg_file.download_as_bytearray()

    from services.vision.openai import describe
    description = await describe(bytes(image_bytes), media_type=item.media_type)

    lines = [f"\n[Image {index}]", description or "Could not analyse image."]
    if item.caption:
        lines.append(f"User note: {item.caption}")
    return lines


async def _save_media_group_document(bot, item: _MediaGroupItem, index: int) -> list[str]:
    tg_file = await bot.get_file(item.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    save_path = _unique_upload_path(item.filename)
    save_path.write_bytes(bytes(file_bytes))

    lines = [f"\n[Uploaded file {index}: {item.filename}]", f"Path: {save_path}"]
    if item.caption:
        lines.append(f"User note: {item.caption}")
    return lines


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorised.")
        return

    await _register_ask_sender(update, context)

    doc = update.message.document
    if not doc:
        return

    mime = doc.mime_type or ""
    filename = doc.file_name or "file"

    if not _document_supported(filename, mime):
        await update.message.reply_text(f"Unsupported file type: {mime or filename}\nSupported: pdf, docx, txt, csv, xlsx")
        return

    if update.message.media_group_id:
        await _enqueue_media_group(
            update,
            context,
            _MediaGroupItem(
                update_id=update.update_id,
                kind="document",
                file_id=doc.file_id,
                media_type=mime,
                filename=filename,
                caption=(update.message.caption or "").strip(),
            ),
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        save_path = _unique_upload_path(filename)
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
        response = await _receive_with_progress(update.get_bot(), update.effective_chat.id, message)
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

    await _register_ask_sender(update, context)

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            media_type = "image/jpeg"
            filename = "image.jpg"
        elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
            photo = update.message.document
            media_type = update.message.document.mime_type or "image/jpeg"
            filename = update.message.document.file_name or "image"
        else:
            await update.message.reply_text("No image found in message.")
            return

        if update.message.media_group_id:
            await _enqueue_media_group(
                update,
                context,
                _MediaGroupItem(
                    update_id=update.update_id,
                    kind="image",
                    file_id=photo.file_id,
                    media_type=media_type,
                    filename=filename,
                    caption=(update.message.caption or "").strip(),
                ),
            )
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
        response = await _receive_with_progress(update.get_bot(), update.effective_chat.id, message)
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
    app.add_handler(CommandHandler("auth", cmd_auth))
    app.add_handler(CommandHandler("tokens", cmd_tokens))
    app.add_handler(CommandHandler("permissions", cmd_permissions))
    app.add_handler(CallbackQueryHandler(handle_choice_tap, pattern=f"^{TG_CHOICE_PREFIX}"))

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
    # Shared with the API server — when both run in one process MCP connects only once
    from services.mcp import lifecycle as mcp_lifecycle
    await mcp_lifecycle.start()


async def _register_task_delivery(app: Application) -> None:
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])

    async def _deliver(task) -> None:
        from schemas.task import TaskStatus
        from schemas.message import Transport
        from services import background_wake
        if getattr(task, "silent", False):
            return
        if task.status == TaskStatus.DONE and task.result and task.profile and task.profile.name and task.profile.name != "default":
            from thrall.tasks.continuation_store import save
            save(task.profile.name, task.brief, task.result)
        # Hand the result to Thrall so it reasons and replies; raw post below is the fallback
        if background_wake.should_wake(task) and allowed:
            try:
                reply = await background_wake.wake(task, Transport.TELEGRAM, str(allowed[0]))
                if reply:
                    await _send_to_chat(app.bot, allowed[0], reply)
                return
            except Exception as e:
                state.log_error(f"Background wake failed for task {task.id}: {type(e).__name__}: {e}")
        if task.status == TaskStatus.DONE:
            result = task.result or "(agent completed but returned no output)"
            text = f"Agent task complete:\n\n{result}"
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
        BotCommand("stop", "Cancel the current task or /stop <task_id>"),
        BotCommand("approve", "Approve a pending proposal and execute"),
        BotCommand("watch", "Process a video: download, transcribe, extract frames, store in memory"),
        BotCommand("tokens", "Show token usage, context size, and cost for the current session"),
        BotCommand("permissions", "Permission mode: ask, trusted, read_only"),
    ])
    from scheduler import runner
    runner.start(app.bot)
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    for uid in allowed:
        try:
            await app.bot.send_message(chat_id=uid, text="Thrall online.")
        except Exception:
            pass


async def run() -> None:
    global _app
    from scheduler import runner

    app = build_application()
    _app = app

    async with app:
        await app.initialize()
        await set_commands(app)
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            runner.stop()
            await app.updater.stop()
            await app.stop()
