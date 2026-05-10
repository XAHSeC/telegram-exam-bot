from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.rate_limiter import rate_limiter
from utils.logger import logger


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and not rate_limiter.is_allowed(user.id):
            logger.warning("Rate limit hit for user %s", user.id)
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Слишком много запросов. Пожалуйста, подождите немного.",
                    show_alert=False,
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком много запросов. Подождите.", show_alert=True
                )
            return

        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        action = ""
        if isinstance(event, Message):
            user = event.from_user
            action = f"MSG: {event.text or '[media]'}"
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            action = f"CB: {event.data}"

        if user:
            logger.debug("User %s (@%s) | %s", user.id, user.username, action)

        return await handler(event, data)
