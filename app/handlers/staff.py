from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_assignee, format_date, format_last_message, format_user_ref
from app.bot.keyboards import assign_staff_keyboard
from app.config import Settings
from app.services.staff_service import StaffService
from app.services.ticket_service import TicketClosedError, TicketNotFoundError, TicketService
from app.states.staff import StaffActionState
from app.utils.content import extract_message_text


def build_staff_router(
    settings: Settings,
    ticket_service: TicketService,
    staff_service: StaffService,
) -> Router:
    router = Router(name="staff-router")

    def staff_label(user_id: int, username: str | None) -> str:
        if username:
            return f"@{username}"
        return str(user_id)

    async def is_authorized(user_id: int) -> bool:
        return await staff_service.is_staff(user_id)

    async def ensure_staff_message_access(message: Message) -> bool:
        if message.chat.id != settings.support_group_id:
            return False
        if not message.from_user:
            return False
        if not await is_authorized(message.from_user.id):
            await message.answer("Команда доступна только сотрудникам поддержки.")
            return False
        return True

    async def ensure_staff_callback_access(query: CallbackQuery) -> bool:
        if not query.message or query.message.chat.id != settings.support_group_id:
            await query.answer()
            return False
        if not query.from_user:
            await query.answer()
            return False
        if not await is_authorized(query.from_user.id):
            await query.answer("Нет доступа", show_alert=True)
            return False
        return True

    @router.message(Command("cancel"), F.chat.id == settings.support_group_id)
    async def cancel_state_handler(message: Message, state: FSMContext) -> None:
        if not await ensure_staff_message_access(message):
            return
        await state.clear()
        await message.answer("Действие отменено.")

    @router.message(Command("active"), F.chat.id == settings.support_group_id)
    async def active_tickets_handler(message: Message) -> None:
        if not await ensure_staff_message_access(message):
            return

        tickets = await ticket_service.list_active_tickets()
        if not tickets:
            await message.answer("Открытых тикетов нет.")
            return

        lines = ["📌 Открытые тикеты:"]
        for ticket in tickets:
            lines.append(
                f"#{ticket.id} | {ticket.category} | {format_user_ref(ticket.username, ticket.user_id)} | "
                f"{ticket.status.value} | {format_assignee(ticket.assigned_to)}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("in_progress"), F.chat.id == settings.support_group_id)
    async def in_progress_handler(message: Message) -> None:
        if not await ensure_staff_message_access(message):
            return

        tickets = await ticket_service.list_in_progress_tickets()
        if not tickets:
            await message.answer("Тикетов в работе нет.")
            return

        lines = ["👤 Тикеты в работе:"]
        for item in tickets:
            lines.append(
                f"#{item.ticket.id} | assigned: {format_assignee(item.ticket.assigned_to)} | "
                f"{item.ticket.category} | {format_last_message(item.last_message)}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("closed"), F.chat.id == settings.support_group_id)
    async def closed_handler(message: Message) -> None:
        if not await ensure_staff_message_access(message):
            return

        tickets = await ticket_service.list_closed_tickets(limit=20)
        if not tickets:
            await message.answer("Закрытых тикетов пока нет.")
            return

        lines = ["📦 Последние закрытые тикеты:"]
        for ticket in tickets:
            closed_by = ticket.closed_by if ticket.closed_by else "неизвестно"
            lines.append(
                f"#{ticket.id} | закрыт: {closed_by} | дата: {format_date(ticket.updated_at)}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("my"), F.chat.id == settings.support_group_id)
    async def my_handler(message: Message) -> None:
        if not await ensure_staff_message_access(message):
            return

        tickets = await ticket_service.list_my_tickets(assignee_id=message.from_user.id)
        if not tickets:
            await message.answer("На вас не назначено тикетов.")
            return

        lines = ["📊 Ваши тикеты:"]
        for ticket in tickets:
            lines.append(
                f"#{ticket.id} | {ticket.status.value} | {ticket.category} | "
                f"{format_user_ref(ticket.username, ticket.user_id)}"
            )
        await message.answer("\n".join(lines))

    @router.callback_query(F.data.startswith("ticket:"))
    async def ticket_action_handler(query: CallbackQuery, state: FSMContext) -> None:
        if not await ensure_staff_callback_access(query):
            return

        chunks = query.data.split(":")
        if len(chunks) != 3:
            await query.answer("Неверный формат кнопки", show_alert=True)
            return

        _, action, ticket_id_raw = chunks
        if not ticket_id_raw.isdigit():
            await query.answer("Неверный тикет", show_alert=True)
            return
        ticket_id = int(ticket_id_raw)

        try:
            if action == "take":
                await ticket_service.take_ticket(ticket_id=ticket_id, staff_id=query.from_user.id)
                await query.message.answer(
                    f"Тикет #{ticket_id} взял {staff_label(query.from_user.id, query.from_user.username)}"
                )
                await query.answer("Тикет взят")
                return

            if action == "reply":
                await state.set_state(StaffActionState.waiting_reply_text)
                await state.update_data(ticket_id=ticket_id)
                await query.message.answer(
                    f"Введите ответ пользователю для тикета #{ticket_id}. "
                    "Для отмены: /cancel"
                )
                await query.answer()
                return

            if action == "comment":
                await state.set_state(StaffActionState.waiting_comment_text)
                await state.update_data(ticket_id=ticket_id)
                await query.message.answer(
                    f"Введите внутренний комментарий для тикета #{ticket_id}. "
                    "Для отмены: /cancel"
                )
                await query.answer()
                return

            if action == "assign":
                staff_users = await staff_service.list_active_staff()
                if not staff_users:
                    await query.answer("Нет активных сотрудников", show_alert=True)
                    return
                await query.message.answer(
                    f"Выберите сотрудника для тикета #{ticket_id}:",
                    reply_markup=assign_staff_keyboard(ticket_id, staff_users),
                )
                await query.answer()
                return

            if action == "close":
                await ticket_service.close_ticket(ticket_id=ticket_id, closed_by=query.from_user.id)
                await query.message.answer(
                    f"Тикет #{ticket_id} закрыт {staff_label(query.from_user.id, query.from_user.username)}"
                )
                await query.answer("Тикет закрыт")
                return

            if action == "escalate":
                result = await ticket_service.escalate_to_dev(ticket_id=ticket_id, actor_id=query.from_user.id)
                if result is None:
                    await query.answer("Нет активных разработчиков для эскалации", show_alert=True)
                    return
                await query.message.answer(
                    f"Тикет #{ticket_id} эскалирован разработчику {result.assigned_to}."
                )
                await query.answer("Эскалация выполнена")
                return

        except TicketNotFoundError:
            await query.answer("Тикет не найден", show_alert=True)
            return
        except TicketClosedError:
            await query.answer("Тикет уже закрыт", show_alert=True)
            return

        await query.answer("Неизвестное действие", show_alert=True)

    @router.callback_query(F.data.startswith("assign:"))
    async def assign_handler(query: CallbackQuery) -> None:
        if not await ensure_staff_callback_access(query):
            return

        chunks = query.data.split(":")
        if len(chunks) != 3:
            await query.answer("Неверный формат назначения", show_alert=True)
            return

        _, ticket_id_raw, assignee_raw = chunks
        if not ticket_id_raw.isdigit() or not assignee_raw.isdigit():
            await query.answer("Некорректные данные", show_alert=True)
            return

        ticket_id = int(ticket_id_raw)
        assignee_id = int(assignee_raw)
        try:
            await ticket_service.assign_ticket(ticket_id=ticket_id, assignee_id=assignee_id, actor_id=query.from_user.id)
        except TicketNotFoundError:
            await query.answer("Тикет или сотрудник не найден", show_alert=True)
            return
        except TicketClosedError:
            await query.answer("Тикет уже закрыт", show_alert=True)
            return

        await query.message.answer(
            f"Тикет #{ticket_id} назначен сотруднику {assignee_id} "
            f"по запросу {staff_label(query.from_user.id, query.from_user.username)}."
        )
        await query.answer("Назначено")

    @router.message(F.chat.id == settings.support_group_id, StaffActionState.waiting_reply_text)
    async def process_reply_text_handler(message: Message, state: FSMContext) -> None:
        if not await ensure_staff_message_access(message):
            return
        if not message.text:
            await message.answer("Для ответа пользователю нужен текст.")
            return

        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await state.clear()
            await message.answer("Не удалось определить тикет. Запустите действие заново.")
            return

        ticket = await ticket_service.get_ticket(ticket_id=ticket_id)
        if ticket is None:
            await state.clear()
            await message.answer(f"Тикет #{ticket_id} не найден.")
            return
        if ticket.status.value == "CLOSED":
            await state.clear()
            await message.answer(f"Тикет #{ticket_id} уже закрыт.")
            return

        try:
            await message.bot.send_message(
                chat_id=ticket.user_id,
                text=f"💬 Ответ поддержки по тикету #{ticket.id}:\n{message.text}",
            )
        except Exception:
            await message.answer(
                "Не удалось отправить сообщение пользователю. Возможно, он заблокировал бота."
            )
            return

        try:
            await ticket_service.save_staff_public_reply(
                ticket_id=ticket.id,
                staff_id=message.from_user.id,
                text=message.text,
            )
        except TicketClosedError:
            await message.answer("Тикет уже закрыт.")
            await state.clear()
            return
        except TicketNotFoundError:
            await message.answer("Тикет не найден.")
            await state.clear()
            return

        await state.clear()
        await message.answer(f"Ответ отправлен пользователю в тикете #{ticket.id}.")

    @router.message(F.chat.id == settings.support_group_id, StaffActionState.waiting_comment_text)
    async def process_comment_text_handler(message: Message, state: FSMContext) -> None:
        if not await ensure_staff_message_access(message):
            return

        comment_text = extract_message_text(message)
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await state.clear()
            await message.answer("Не удалось определить тикет. Запустите действие заново.")
            return

        try:
            await ticket_service.save_internal_comment(
                ticket_id=int(ticket_id),
                staff_id=message.from_user.id,
                text=comment_text,
            )
        except TicketClosedError:
            await message.answer("Тикет уже закрыт.")
            await state.clear()
            return
        except TicketNotFoundError:
            await message.answer("Тикет не найден.")
            await state.clear()
            return

        await state.clear()
        await message.answer(f"Комментарий сохранен для тикета #{ticket_id}.")

    return router
