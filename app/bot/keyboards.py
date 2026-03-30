from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.constants import CATEGORIES
from app.db.models import StaffUser


def category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in CATEGORIES:
        builder.button(text=category.title, callback_data=f"category:{category.key}")
    builder.adjust(1)
    return builder.as_markup()


def ticket_actions_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Взять в работу", callback_data=f"ticket:take:{ticket_id}")
    builder.button(text="💬 Ответить", callback_data=f"ticket:reply:{ticket_id}")
    builder.button(text="📝 Комментарий", callback_data=f"ticket:comment:{ticket_id}")
    builder.button(text="👤 Назначить", callback_data=f"ticket:assign:{ticket_id}")
    builder.button(text="⚡ Эскалация разработчику", callback_data=f"ticket:escalate:{ticket_id}")
    builder.button(text="🔴 Закрыть", callback_data=f"ticket:close:{ticket_id}")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()


def assign_staff_keyboard(ticket_id: int, staff_users: list[StaffUser]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for staff in staff_users:
        builder.button(
            text=f"{staff.role.value} • {staff.telegram_id}",
            callback_data=f"assign:{ticket_id}:{staff.telegram_id}",
        )
    builder.adjust(1)
    return builder.as_markup()
