from aiogram import Router
from .commands import router as commands_router
from .excel_import import router as import_router

admin_router = Router()
admin_router.include_router(commands_router)
admin_router.include_router(import_router)

__all__ = ["admin_router"]
