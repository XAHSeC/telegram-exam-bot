import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import init_db
from handlers import main_router
from admin import admin_router
from middlewares import RateLimitMiddleware, LoggingMiddleware, ProtectContentMiddleware
from utils.logger import logger


async def on_startup(bot: Bot):
    await init_db()
    logger.info("Database initialised")

    me = await bot.get_me()
    logger.info("Bot started: @%s (%s)", me.username, me.full_name)

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🟢 <b>{config.BOT_NAME} запущен!</b>\n"
                f"Бот: @{me.username}",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def on_shutdown(bot: Bot):
    logger.info("Bot shutting down...")
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🔴 Бот остановлен.")
        except Exception:
            pass


async def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    session = AiohttpSession()
    session.middleware(ProtectContentMiddleware())

    bot = Bot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # Routers — admin first so admin commands take priority
    dp.include_router(admin_router)
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
