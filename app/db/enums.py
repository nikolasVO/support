from __future__ import annotations

from enum import Enum


class TicketStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_USER = "WAITING_USER"
    CLOSED = "CLOSED"


class SenderType(str, Enum):
    CLIENT = "client"
    STAFF = "staff"
    SYSTEM = "system"


class MessageType(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"


class StaffRole(str, Enum):
    SUPPORT = "support"
    DEV = "dev"
    MANAGER = "manager"
    OWNER = "owner"
