"""Main entrypoint for the Personal Telegram AI Video Generator Bot."""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.bot.handlers import router as bot_router
from app.bot.middlewares import PersonalAccessMiddleware
from app.core.config import TEMP_STORAGE_DIR, settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def cleanup_startup_temp_files() -> None:
    """Clean up any leftover temporary media files on bot startup."""
    count = 0
    for item in TEMP_STORAGE_DIR.glob("*"):
        if item.name != ".gitkeep" and item.is_file():
            item.unlink(missing_ok=True)
            count += 1
    if count:
        logger.info("Cleaned up %d leftover temporary files in storage/temp.", count)


async def configure_bot_commands(bot: Bot) -> None:
    """Set the Telegram slash commands menu."""
    commands = [
        BotCommand(command="start", description="Mở Menu chính & tạo video"),
        BotCommand(command="settings", description="Cài đặt thông số video (Tỷ lệ, Độ phân giải, Model)"),
        BotCommand(command="help", description="Hướng dẫn sử dụng"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    setup_logging()
    cleanup_startup_temp_files()

    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error(
            "Chưa cấu hình TELEGRAM_BOT_TOKEN! Hãy copy file .env.example thành .env và điền Bot Token."
        )
        sys.exit(1)

    if (
        not settings.GEMINI_MOCK_MODE
        and not settings.USE_VERTEX_AI
        and (not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here")
    ):
        logger.warning(
            "Chưa điền GEMINI_API_KEY. Hãy điền GEMINI_API_KEY trong .env hoặc bật GEMINI_MOCK_MODE=true để chạy thử."
        )

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register personal whitelist & anti-duplicate middleware
    access_middleware = PersonalAccessMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)

    dp.include_router(bot_router)

    await configure_bot_commands(bot)
    me = await bot.get_me()
    logger.info(
        "Bot @%s started successfully! | Mock Mode: %s | Allowed Users: %s",
        me.username,
        settings.GEMINI_MOCK_MODE,
        settings.allowed_users_set or "ALL (Public)",
    )

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped cleanly.")

