from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📥 Импорт вопросов", callback_data="admin_import")
    builder.button(text="❓ Вопросы", callback_data="admin_questions")
    builder.adjust(2)
    return builder.as_markup()


def admin_user_actions_kb(telegram_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_blocked:
        builder.button(text="✅ Разблокировать", callback_data=f"admin_unblock:{telegram_id}")
    else:
        builder.button(text="🚫 Заблокировать", callback_data=f"admin_block:{telegram_id}")
    builder.button(text="🗑 Удалить", callback_data=f"admin_delete:{telegram_id}")
    builder.button(text="◀️ Назад", callback_data="admin_users")
    builder.adjust(2)
    return builder.as_markup()


def confirm_delete_kb(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"admin_confirm_delete:{telegram_id}")
    builder.button(text="❌ Отмена", callback_data="admin_users")
    builder.adjust(2)
    return builder.as_markup()
