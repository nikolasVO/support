from __future__ import annotations

from datetime import datetime

from sqlalchemy import BIGINT, BOOLEAN, DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import MessageType, SenderType, StaffRole, TicketStatus


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"),
        default=TicketStatus.NEW,
        nullable=False,
    )
    assigned_to: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("staff_users.telegram_id"), nullable=True)
    closed_by: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("staff_users.telegram_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(back_populates="ticket", lazy="selectin")

    __table_args__ = (
        Index(
            "uq_tickets_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status <> 'CLOSED'"),
        ),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType, name="sender_type"), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[MessageType] = mapped_column(Enum(MessageType, name="message_type"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class StaffUser(Base):
    __tablename__ = "staff_users"

    telegram_id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole, name="staff_role"), nullable=False)
    active: Mapped[bool] = mapped_column(BOOLEAN, default=True, nullable=False)
