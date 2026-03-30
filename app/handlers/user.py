from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_ticket_created, format_ticket_update
from app.bot.keyboards import category_keyboard, ticket_actions_keyboard
from app.config import Settings
from app.constants import CATEGORY_BY_KEY
from app.services.ticket_service import TicketService
from app.states.user import UserTicketState
from app.utils.content import extract_message_text

logger = logging.getLogger(__name__)


def build_user_router(settings: Settings, ticket_service: TicketService) -> Router:
    router = Router(name="user-router")

    @router.message(CommandStart(), F.chat.type == "private")
    async def start_handler(message: Message, state: FSMContext) -> None:
        existing_ticket = await ticket_service.get_open_ticket_for_user(message.from_user.id)
        if existing_ticket:
            await state.clear()
            await message.answer(
                f"У вас уже есть открытый тикет #{existing_ticket.id}. "
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
                    f"Активный тикет #{existing_ticket.id} уже открыт. Просто отправьте следующее сообщение."
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
                f"У вас уже есть открытый тикет #{ticket.id}. "
                "Добавил ваше сообщение в текущий диалог."
            )
            await ticket_service.add_client_message_to_open_ticket(
                user_id=message.from_user.id,
                username=message.from_user.username,
                text=user_text,
            )
            return

        await message.answer(
            f"Тикет #{ticket.id} создан. Мы получили ваше обращение и скоро ответим."
        )

        group_notice = await message.bot.send_message(
            chat_id=settings.support_group_id,
            text=format_ticket_created(ticket=ticket, text=user_text),
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
            text=format_ticket_update(ticket=ticket, text=user_text),
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

        await message.answer(f"Сообщение добавлено в тикет #{ticket.id}.")

    return router
