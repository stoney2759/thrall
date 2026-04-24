from __future__ import annotations

# Telegram audio delivery config
# The TTS router reads output_format from here when delivering via Telegram.

OUTPUT_FORMAT = "opus"       # Telegram plays opus/ogg inline as voice messages
MIME_TYPE = "audio/ogg"
SEND_AS_VOICE = True         # True = voice message (inline playback), False = document (download)
