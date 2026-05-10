from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram import Bot
from aiogram.methods import TelegramMethod, Response
from aiogram.methods import (
    SendMessage, SendPhoto, SendDocument, SendVideo,
    SendAudio, SendAnimation, SendVoice, SendSticker,
)

PROTECTED_METHODS = (
    SendMessage, SendPhoto, SendDocument, SendVideo,
    SendAudio, SendAnimation, SendVoice, SendSticker,
)


class ProtectContentMiddleware(BaseRequestMiddleware):
    async def __call__(
        self,
        make_request: NextRequestMiddlewareType,
        bot: Bot,
        method: TelegramMethod,
    ) -> Response:
        if isinstance(method, PROTECTED_METHODS):
            if getattr(method, "protect_content", None) is None:
                method.protect_content = True
        return await make_request(bot, method)
