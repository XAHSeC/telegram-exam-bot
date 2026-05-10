from aiogram import Router
from .start import router as start_router
from .exam import router as exam_router
from .results import router as results_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(exam_router)
main_router.include_router(results_router)

__all__ = ["main_router"]
