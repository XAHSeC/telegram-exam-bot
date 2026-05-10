from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def no_access_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆔 Получить ID", callback_data="get_id")
    return builder.as_markup()


def get_id_kb(admin_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👨‍💻 Отправить админу",
        url=f"https://t.me/{admin_username.lstrip('@')}",
    )
    return builder.as_markup()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Начать экзамен", callback_data="start_exam")
    builder.button(text="📊 Мои результаты", callback_data="my_results")
    builder.button(text="ℹ️ Информация", callback_data="info")
    builder.button(text="☎️ Поддержка", callback_data="support")
    builder.adjust(1)
    return builder.as_markup()


def exam_answer_kb(answers: list, session_id: int, question_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    letters = ["A", "B", "C", "D", "E", "F"]
    for i, ans in enumerate(answers):
        label = letters[i] if i < len(letters) else str(i + 1)
        builder.button(
            text=f"{label}) {ans['text']}",
            callback_data=f"answer:{session_id}:{question_id}:{ans['id']}",
        )
    builder.button(text="🚫 Завершить экзамен", callback_data=f"finish_exam:{session_id}")
    builder.adjust(1)
    return builder.as_markup()


def exam_answer_kb_photo(answers: list, session_id: int, question_id: int) -> InlineKeyboardMarkup:
    """Same as exam_answer_kb but without the finish button (used in photo captions with char limit)."""
    return exam_answer_kb(answers, session_id, question_id)


def confirm_start_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Начать", callback_data="confirm_start_exam")
    builder.button(text="❌ Отмена", callback_data="cancel_exam")
    builder.adjust(2)
    return builder.as_markup()


def confirm_finish_kb(session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, завершить", callback_data=f"confirm_finish:{session_id}")
    builder.button(text="↩️ Продолжить", callback_data=f"continue_exam:{session_id}")
    builder.adjust(2)
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    return builder.as_markup()


def results_kb(session_id: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if session_id:
        builder.button(text="📋 Разбор ошибок", callback_data=f"review_errors:{session_id}")
    builder.button(text="✅ Начать новый экзамен", callback_data="start_exam")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def errors_nav_kb(session_id: int, current: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current > 0:
        builder.button(text="◀️ Пред.", callback_data=f"err_nav:{session_id}:{current - 1}")
    if current < total - 1:
        builder.button(text="След. ▶️", callback_data=f"err_nav:{session_id}:{current + 1}")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()
