from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import TicketStatus
from app.db.models import Ticket


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        query = select(Ticket).where(Ticket.id == ticket_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_open_by_user_id(self, user_id: int) -> Ticket | None:
        query = (
            select(Ticket)
            .where(Ticket.user_id == user_id, Ticket.status != TicketStatus.CLOSED)
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, username: str | None, category: str) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            username=username,
            category=category,
            status=TicketStatus.NEW,
        )
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def list_active(self, limit: int = 50) -> list[Ticket]:
        query = (
            select(Ticket)
            .where(Ticket.status != TicketStatus.CLOSED)
            .order_by(Ticket.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_in_progress(self, limit: int = 50) -> list[Ticket]:
        query = (
            select(Ticket)
            .where(Ticket.status == TicketStatus.IN_PROGRESS)
            .order_by(Ticket.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_closed(self, limit: int = 20) -> list[Ticket]:
        query = (
            select(Ticket)
            .where(Ticket.status == TicketStatus.CLOSED)
            .order_by(Ticket.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_assignee(self, assignee_id: int, limit: int = 100) -> list[Ticket]:
        query = (
            select(Ticket)
            .where(Ticket.assigned_to == assignee_id)
            .order_by(Ticket.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
