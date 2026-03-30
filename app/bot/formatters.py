from __future__ import annotations

from datetime import datetime

from app.db.models import Message, Ticket


def format_user_ref(username: str | None, user_id: int) -> str:
    if username:
        return f"@{username} ({user_id})"
    return f"{user_id}"


def format_assignee(telegram_id: int | None) -> str:
    return str(telegram_id) if telegram_id else "не назначен"


def public_ticket_id(ticket_id: int, offset: int) -> int:
    return ticket_id + offset


def ticket_label(ticket_id: int, offset: int) -> str:
    return f"#{public_ticket_id(ticket_id, offset)}"


def format_ticket_created(ticket: Ticket, text: str, offset: int) -> str:
    return (
        f"📌 Новый тикет {ticket_label(ticket.id, offset)}\n"
        f"👤 Пользователь: {format_user_ref(ticket.username, ticket.user_id)}\n"
        f"📂 Категория: {ticket.category}\n"
        f"📊 Статус: {ticket.status.value}\n\n"
        f"💬 Сообщение:\n{text}"
    )


def format_ticket_update(ticket: Ticket, text: str, offset: int) -> str:
    return (
        f"📩 Новое сообщение в тикете {ticket_label(ticket.id, offset)}\n"
        f"👤 {format_user_ref(ticket.username, ticket.user_id)}\n\n"
        f"{text}"
    )


def short_text(text: str, limit: int = 90) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def format_last_message(message: Message | None) -> str:
    if message is None:
        return "нет сообщений"
    return short_text(message.text)


def format_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")
