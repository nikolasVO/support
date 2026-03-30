from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.enums import StaffRole
from app.db.models import StaffUser
from app.db.repositories.staff_users import StaffUserRepository


class StaffService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def is_staff(self, telegram_id: int) -> bool:
        async with self._session_factory() as session:
            repo = StaffUserRepository(session)
            return await repo.is_active_staff(telegram_id)

    async def list_active_staff(self) -> list[StaffUser]:
        async with self._session_factory() as session:
            repo = StaffUserRepository(session)
            return await repo.list_active()

    async def list_active_dev_staff(self) -> list[StaffUser]:
        async with self._session_factory() as session:
            repo = StaffUserRepository(session)
            return await repo.list_active_by_role(StaffRole.DEV)

    async def seed_staff(self, telegram_ids: list[int]) -> None:
        if not telegram_ids:
            return

        async with self._session_factory() as session:
            repo = StaffUserRepository(session)
            await repo.seed_ids(telegram_ids)
            await session.commit()
