from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram import Bot
from aiogram.methods import TelegramMethod, Response


class ProtectContentMiddleware(BaseRequestMiddleware):
    async def __call__(
        self,
        make_request: NextRequestMiddlewareType,
        bot: Bot,
        method: TelegramMethod,
    ) -> Response:
        if hasattr(method, "protect_content") and method.protect_content is None:
            method.protect_content = True
        return await make_request(bot, method)
