from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy import text
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from app.config import get_settings
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.handlers.staff import build_staff_router
from app.handlers.user import build_user_router
from app.logging import configure_logging
from app.services.staff_service import StaffService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


async def setup_database(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def wait_for_database(engine, attempts: int = 30, delay_seconds: int = 2) -> None:
    for attempt in range(1, attempts + 1):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.warning(
                "Database is not reachable yet (attempt %s/%s): %s",
                attempt,
                attempts,
                exc,
            )
            await asyncio.sleep(delay_seconds)


async def set_bot_commands(bot: Bot, support_group_id: int) -> None:
    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Создать обращение в поддержку")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        commands=[
            BotCommand(command="active", description="Список открытых тикетов"),
            BotCommand(command="in_progress", description="Тикеты в работе"),
            BotCommand(command="closed", description="Последние закрытые тикеты"),
            BotCommand(command="my", description="Мои тикеты"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
        ],
        scope=BotCommandScopeChat(chat_id=support_group_id),
    )


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    await wait_for_database(engine)
    await setup_database(engine)

    ticket_service = TicketService(session_factory)
    staff_service = StaffService(session_factory)
    await staff_service.seed_staff(settings.parsed_staff_seed_ids)

    if settings.redis_url:
        storage = RedisStorage.from_url(settings.redis_url)
    else:
        storage = MemoryStorage()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )

    webhook_info = await bot.get_webhook_info()
    if webhook_info.url:
        logger.warning("Webhook is configured (%s), removing for polling mode", webhook_info.url)
        await bot.delete_webhook(drop_pending_updates=False)

    dp = Dispatcher(storage=storage)
    dp.include_router(build_user_router(settings=settings, ticket_service=ticket_service))
    dp.include_router(build_staff_router(settings=settings, ticket_service=ticket_service, staff_service=staff_service))

    await set_bot_commands(bot, settings.support_group_id)

    logger.info("Support bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
