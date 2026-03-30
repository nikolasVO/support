from __future__ import annotations

from contextlib import suppress
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_ticket_created, format_ticket_update, ticket_label
from app.bot.keyboards import category_keyboard, ticket_actions_keyboard
from app.config import Settings
from app.constants import CATEGORY_BY_KEY
from app.services.ticket_service import TicketAccessDeniedError, TicketNotFoundError, TicketService
from app.states.user import UserTicketState
from app.utils.content import extract_message_text

logger = logging.getLogger(__name__)


def build_user_router(settings: Settings, ticket_service: TicketService) -> Router:
    router = Router(name="user-router")

    @router.callback_query(F.data.startswith("user_ticket:"))
    async def user_ticket_feedback_handler(query: CallbackQuery) -> None:
        if not query.from_user:
            return
        if not query.message or query.message.chat.type != "private":
            await query.answer()
            return

        parts = query.data.split(":")
        if len(parts) != 3:
            await query.answer("Некорректная кнопка", show_alert=True)
            return

        _, action, ticket_id_raw = parts
        if not ticket_id_raw.isdigit():
            await query.answer("Некорректный тикет", show_alert=True)
            return
        ticket_id = int(ticket_id_raw)

        ticket = await ticket_service.get_ticket(ticket_id)
        if ticket is None or ticket.user_id != query.from_user.id:
            await query.answer("Тикет не найден", show_alert=True)
            return

        ticket_public_label = ticket_label(ticket.id, settings.ticket_id_offset)

        if action == "resolved":
            try:
                await ticket_service.close_ticket_by_user(ticket_id=ticket.id, user_id=query.from_user.id)
            except TicketNotFoundError:
                await query.answer("Тикет не найден", show_alert=True)
                return
            except TicketAccessDeniedError:
                await query.answer("Нет доступа к тикету", show_alert=True)
                return

            with suppress(Exception):
                await query.message.edit_reply_markup(reply_markup=None)

            await query.answer("Спасибо! Тикет закрыт.")
            await query.message.answer(
                f"Спасибо за ответ. Тикет {ticket_public_label} закрыт."
            )
            await query.message.bot.send_message(
                chat_id=settings.support_group_id,
                text=(
                    f"✅ Тикет {ticket_public_label} закрыт пользователем "
                    f"{'@' + query.from_user.username if query.from_user.username else query.from_user.id}."
                ),
            )
            return

        if action == "not_resolved":
            await query.answer()
            await query.message.answer(
                "Понял. Напишите одним сообщением, что именно осталось нерешенным, "
                "и мы продолжим работу по тикету."
            )
            return

        await query.answer("Неизвестное действие", show_alert=True)

    @router.message(CommandStart(), F.chat.type == "private")
    async def start_handler(message: Message, state: FSMContext) -> None:
        existing_ticket = await ticket_service.get_open_ticket_for_user(message.from_user.id)
        if existing_ticket:
            await state.clear()
            await message.answer(
                f"У вас уже есть открытый тикет {ticket_label(existing_ticket.id, settings.ticket_id_offset)}. "
                "Напишите сообщение в этот чат, и я добавлю его в текущий тикет."
            )
            return

        await state.clear()
        await message.answer(
            "Выберите категорию обращения:",
            reply_markup=category_keyboard(),
        )

    @router.callback_query(F.data.startswith("category:"))
    async def category_selected_handler(query: CallbackQuery, state: FSMContext) -> None:
        if not query.from_user:
            return

        if query.message and query.message.chat.type != "private":
            await query.answer()
            return

        category_key = query.data.split(":", 1)[1]
        category = CATEGORY_BY_KEY.get(category_key)
        if category is None:
            await query.answer("Категория не найдена", show_alert=True)
            return

        existing_ticket = await ticket_service.get_open_ticket_for_user(query.from_user.id)
        if existing_ticket:
            await state.clear()
            await query.answer("У вас уже есть активный тикет", show_alert=True)
            if query.message:
                await query.message.answer(
                    f"Активный тикет {ticket_label(existing_ticket.id, settings.ticket_id_offset)} уже открыт. "
                    "Просто отправьте следующее сообщение."
                )
            return

        await state.set_state(UserTicketState.waiting_description)
        await state.update_data(category=category.title)

        await query.answer()
        if query.message:
            await query.message.answer("Опишите проблему одним сообщением. Можно отправить текст, фото или документ.")

    @router.message(F.chat.type == "private", UserTicketState.waiting_description)
    async def create_ticket_handler(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        category = data.get("category")
        if not category:
            await state.clear()
            await message.answer("Сначала выберите категорию через /start.")
            return

        user_text = extract_message_text(message)
        ticket, created = await ticket_service.create_ticket(
            user_id=message.from_user.id,
            username=message.from_user.username,
            category=category,
            first_message=user_text,
        )
        await state.clear()

        if not created:
            await message.answer(
                f"У вас уже есть открытый тикет {ticket_label(ticket.id, settings.ticket_id_offset)}. "
                "Добавил ваше сообщение в текущий диалог."
            )
            await ticket_service.add_client_message_to_open_ticket(
                user_id=message.from_user.id,
                username=message.from_user.username,
                text=user_text,
            )
            return

        await message.answer(
            f"Тикет {ticket_label(ticket.id, settings.ticket_id_offset)} создан. "
            "Мы получили ваше обращение и скоро ответим."
        )

        group_notice = await message.bot.send_message(
            chat_id=settings.support_group_id,
            text=format_ticket_created(ticket=ticket, text=user_text, offset=settings.ticket_id_offset),
            reply_markup=ticket_actions_keyboard(ticket.id),
        )

        if message.photo or message.document or message.video or message.voice:
            try:
                await message.bot.copy_message(
                    chat_id=settings.support_group_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_to_message_id=group_notice.message_id,
                )
            except Exception:
                logger.exception("Failed to copy media for ticket #%s", ticket.id)

    @router.message(F.chat.type == "private")
    async def user_message_handler(message: Message) -> None:
        user_text = extract_message_text(message)
        ticket = await ticket_service.add_client_message_to_open_ticket(
            user_id=message.from_user.id,
            username=message.from_user.username,
            text=user_text,
        )

        if ticket is None:
            await message.answer(
                "Сначала создайте обращение через /start и выберите категорию."
            )
            return

        group_notice = await message.bot.send_message(
            chat_id=settings.support_group_id,
            text=format_ticket_update(ticket=ticket, text=user_text, offset=settings.ticket_id_offset),
            reply_markup=ticket_actions_keyboard(ticket.id),
        )

        if message.photo or message.document or message.video or message.voice:
            try:
                await message.bot.copy_message(
                    chat_id=settings.support_group_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_to_message_id=group_notice.message_id,
                )
            except Exception:
                logger.exception("Failed to copy media update for ticket #%s", ticket.id)

        await message.answer(
            f"Сообщение добавлено в тикет {ticket_label(ticket.id, settings.ticket_id_offset)}."
        )

    return router
