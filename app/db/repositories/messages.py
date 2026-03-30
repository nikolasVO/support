from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MessageType, SenderType
from app.db.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        ticket_id: int,
        sender_type: SenderType,
        sender_id: int | None,
        text: str,
        message_type: MessageType,
    ) -> Message:
        message = Message(
            ticket_id=ticket_id,
            sender_type=sender_type,
            sender_id=sender_id,
            text=text,
            type=message_type,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_last_for_ticket(self, ticket_id: int) -> Message | None:
        query = (
            select(Message)
            .where(Message.ticket_id == ticket_id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
