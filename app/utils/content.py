from __future__ import annotations

from aiogram.types import Message


def extract_message_text(message: Message) -> str:
    if message.text:
        return message.text.strip()

    if message.photo:
        caption = (message.caption or "").strip()
        if caption:
            return f"[photo] {caption}"
        return "[photo]"

    if message.document:
        filename = message.document.file_name or "document"
        caption = (message.caption or "").strip()
        if caption:
            return f"[document:{filename}] {caption}"
        return f"[document:{filename}]"

    if message.voice:
        return "[voice message]"

    if message.video:
        caption = (message.caption or "").strip()
        if caption:
            return f"[video] {caption}"
        return "[video]"

    return "[unsupported message]"
