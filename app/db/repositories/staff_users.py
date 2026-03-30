from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import StaffRole
from app.db.models import StaffUser


class StaffUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> StaffUser | None:
        query = select(StaffUser).where(StaffUser.telegram_id == telegram_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def is_active_staff(self, telegram_id: int) -> bool:
        query = select(StaffUser.telegram_id).where(
            StaffUser.telegram_id == telegram_id,
            StaffUser.active.is_(True),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_active(self) -> list[StaffUser]:
        query = select(StaffUser).where(StaffUser.active.is_(True)).order_by(StaffUser.telegram_id.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_active_by_role(self, role: StaffRole) -> list[StaffUser]:
        query = select(StaffUser).where(StaffUser.active.is_(True), StaffUser.role == role)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def seed_ids(self, telegram_ids: list[int], default_role: StaffRole = StaffRole.SUPPORT) -> None:
        for telegram_id in telegram_ids:
            existing = await self.get_by_telegram_id(telegram_id)
            if existing:
                existing.active = True
                if not existing.role:
                    existing.role = default_role
                continue
            self.session.add(StaffUser(telegram_id=telegram_id, role=default_role, active=True))
        await self.session.flush()
