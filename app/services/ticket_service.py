from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.enums import MessageType, SenderType, StaffRole, TicketStatus
from app.db.models import Message, Ticket
from app.db.repositories.messages import MessageRepository
from app.db.repositories.staff_users import StaffUserRepository
from app.db.repositories.tickets import TicketRepository


class TicketNotFoundError(Exception):
    pass


class TicketClosedError(Exception):
    pass


@dataclass(slots=True)
class InProgressTicketView:
    ticket: Ticket
    last_message: Message | None


class TicketService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    async def get_ticket(self, ticket_id: int) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            return await ticket_repo.get_by_id(ticket_id)

    async def get_open_ticket_for_user(self, user_id: int) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            return await ticket_repo.get_open_by_user_id(user_id)

    async def create_ticket(self, user_id: int, username: str | None, category: str, first_message: str) -> tuple[Ticket, bool]:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)

            existing_open_ticket = await ticket_repo.get_open_by_user_id(user_id)
            if existing_open_ticket:
                return existing_open_ticket, False

            ticket = await ticket_repo.create(user_id=user_id, username=username, category=category)
            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.CLIENT,
                sender_id=user_id,
                text=first_message,
                message_type=MessageType.PUBLIC,
            )

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                recovered = await ticket_repo.get_open_by_user_id(user_id)
                if recovered is None:
                    raise
                return recovered, False

            await session.refresh(ticket)
            return ticket, True

    async def add_client_message_to_open_ticket(
        self,
        user_id: int,
        username: str | None,
        text: str,
    ) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)

            ticket = await ticket_repo.get_open_by_user_id(user_id)
            if ticket is None:
                return None

            ticket.username = username
            if ticket.status == TicketStatus.WAITING_USER:
                ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = self._utc_now()

            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.CLIENT,
                sender_id=user_id,
                text=text,
                message_type=MessageType.PUBLIC,
            )
            await session.commit()
            return ticket

    async def take_ticket(self, ticket_id: int, staff_id: int) -> Ticket:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                raise TicketClosedError

            ticket.assigned_to = staff_id
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = self._utc_now()
            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.SYSTEM,
                sender_id=staff_id,
                text=f"TICKET_TAKEN:{staff_id}",
                message_type=MessageType.INTERNAL,
            )
            await session.commit()
            return ticket

    async def save_staff_public_reply(self, ticket_id: int, staff_id: int, text: str) -> Ticket:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                raise TicketClosedError

            ticket.assigned_to = staff_id
            ticket.status = TicketStatus.WAITING_USER
            ticket.updated_at = self._utc_now()
            await message_repo.create(
                ticket_id=ticket_id,
                sender_type=SenderType.STAFF,
                sender_id=staff_id,
                text=text,
                message_type=MessageType.PUBLIC,
            )
            await session.commit()
            return ticket

    async def save_internal_comment(self, ticket_id: int, staff_id: int, text: str) -> Ticket:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                raise TicketClosedError

            ticket.updated_at = self._utc_now()
            await message_repo.create(
                ticket_id=ticket_id,
                sender_type=SenderType.STAFF,
                sender_id=staff_id,
                text=text,
                message_type=MessageType.INTERNAL,
            )
            await session.commit()
            return ticket

    async def assign_ticket(self, ticket_id: int, assignee_id: int, actor_id: int) -> Ticket:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            staff_repo = StaffUserRepository(session)

            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                raise TicketClosedError

            assignee = await staff_repo.get_by_telegram_id(assignee_id)
            if assignee is None or not assignee.active:
                raise TicketNotFoundError

            ticket.assigned_to = assignee.telegram_id
            if ticket.status == TicketStatus.NEW:
                ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = self._utc_now()

            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.SYSTEM,
                sender_id=actor_id,
                text=f"TICKET_ASSIGNED:{assignee.telegram_id}",
                message_type=MessageType.INTERNAL,
            )
            await session.commit()
            return ticket

    async def escalate_to_dev(self, ticket_id: int, actor_id: int) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            staff_repo = StaffUserRepository(session)

            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                raise TicketClosedError

            dev_list = await staff_repo.list_active_by_role(StaffRole.DEV)
            if not dev_list:
                return None

            assignee_id = dev_list[0].telegram_id
            ticket.assigned_to = assignee_id
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = self._utc_now()

            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.SYSTEM,
                sender_id=actor_id,
                text=f"TICKET_ESCALATED_TO_DEV:{assignee_id}",
                message_type=MessageType.INTERNAL,
            )
            await session.commit()
            return ticket

    async def close_ticket(self, ticket_id: int, closed_by: int) -> Ticket:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            ticket = await ticket_repo.get_by_id(ticket_id)
            if ticket is None:
                raise TicketNotFoundError
            if ticket.status == TicketStatus.CLOSED:
                return ticket

            ticket.status = TicketStatus.CLOSED
            ticket.closed_by = closed_by
            ticket.updated_at = self._utc_now()
            await message_repo.create(
                ticket_id=ticket.id,
                sender_type=SenderType.SYSTEM,
                sender_id=closed_by,
                text=f"TICKET_CLOSED:{closed_by}",
                message_type=MessageType.INTERNAL,
            )
            await session.commit()
            return ticket

    async def list_active_tickets(self, limit: int = 50) -> list[Ticket]:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            return await ticket_repo.list_active(limit=limit)

    async def list_in_progress_tickets(self, limit: int = 50) -> list[InProgressTicketView]:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            message_repo = MessageRepository(session)
            tickets = await ticket_repo.list_in_progress(limit=limit)
            result: list[InProgressTicketView] = []
            for ticket in tickets:
                last_message = await message_repo.get_last_for_ticket(ticket.id)
                result.append(InProgressTicketView(ticket=ticket, last_message=last_message))
            return result

    async def list_closed_tickets(self, limit: int = 20) -> list[Ticket]:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            return await ticket_repo.list_closed(limit=limit)

    async def list_my_tickets(self, assignee_id: int, limit: int = 100) -> list[Ticket]:
        async with self._session_factory() as session:
            ticket_repo = TicketRepository(session)
            return await ticket_repo.list_by_assignee(assignee_id=assignee_id, limit=limit)
