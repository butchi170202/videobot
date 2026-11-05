"""Access control and anti-duplicate middleware for personal Telegram Bot."""

import logging
import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.config import settings

logger = logging.getLogger(__name__)


class PersonalAccessMiddleware(BaseMiddleware):
    """
    Restricts bot access to ALLOWED_USER_IDS (if configured in .env)
    and prevents duplicate rapid callback clicks.
    """

    def __init__(self) -> None:
        self._last_callback_ts: dict[tuple[int, str], float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        allowed_ids = settings.allowed_users_set
        if allowed_ids and user.id not in allowed_ids:
            logger.warning(
                "Unauthorized access attempt blocked | user_id=%d | username=%s",
                user.id,
                user.username,
            )
            if isinstance(event, Message):
                await event.answer(
                    "⛔ <b>Bot cá nhân:</b> Tài khoản của bạn chưa được cấp quyền sử dụng.\n"
                    f"ID Telegram của bạn là: <code>{user.id}</code>",
                    parse_mode="HTML",
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Bạn không có quyền sử dụng Bot này.", show_alert=True)
            return None

        # Prevent duplicate rapid button clicks (Idempotency guard within 1.5s)
        if isinstance(event, CallbackQuery) and event.data:
            now = time.monotonic()
            key = (user.id, event.data)
            prev = self._last_callback_ts.get(key, 0.0)
            if now - prev < 1.5:
                await event.answer("⏳ Đang xử lý thao tác...", show_alert=False)
                return None
            self._last_callback_ts[key] = now

        return await handler(event, data)

