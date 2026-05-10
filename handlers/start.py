from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from database.db import get_user, check_access, upsert_user_info, log_action
from keyboards.user_kb import no_access_kb, get_id_kb, main_menu_kb
from config import config
from utils.logger import logger

router = Router()


def _full_name(user) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    return " ".join(p for p in parts if p).strip() or user.username or str(user.id)


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await log_action(user.id, "start", f"@{user.username}")

    db_user = await get_user(user.id)
    if db_user:
        await upsert_user_info(user.id, user.username or "", _full_name(user))

    has_access, reason = check_access(db_user)

    if not has_access:
        if reason == "blocked":
            await message.answer(
                "🚫 <b>Ваш аккаунт заблокирован.</b>\n\n"
                "Обратитесь к администратору для решения вопроса.",
                parse_mode="HTML",
            )
        elif reason == "expired":
            await message.answer(
                "⏰ <b>Срок вашего доступа истёк.</b>\n\n"
                "Обратитесь к администратору для продления доступа.",
                parse_mode="HTML",
                reply_markup=get_id_kb(config.SUPPORT_USERNAME),
            )
        else:
            await message.answer(
                "❌ <b>У вас нет доступа к экзамену.</b>\n\n"
                "Нажмите кнопку ниже, чтобы получить ваш ID и отправить его администратору.",
                parse_mode="HTML",
                reply_markup=no_access_kb(),
            )
        return

    name = _full_name(user)
    await message.answer(
        f"👋 <b>Добро пожаловать, {name}!</b>\n\n"
        f"🎓 Вы находитесь в системе тестирования <b>{config.BOT_NAME}</b>.\n\n"
        f"📋 <b>Параметры экзамена:</b>\n"
        f"  • Вопросов: <b>{config.EXAM_QUESTIONS_COUNT}</b>\n"
        f"  • Время: <b>{config.EXAM_TIME_LIMIT_MINUTES} мин</b>\n"
        f"  • Проходной балл: <b>{int(config.PASS_THRESHOLD * 100)}%</b>\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user = callback.from_user
    db_user = await get_user(user.id)
    has_access, _ = check_access(db_user)

    if not has_access:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        f"🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "get_id")
async def cb_get_id(callback: CallbackQuery):
    user = callback.from_user
    await callback.message.answer(
        f"🆔 <b>Ваш Telegram ID:</b>\n\n"
        f"<code>{user.id}</code>\n\n"
        f"Отправьте этот ID администратору для получения доступа.",
        parse_mode="HTML",
        reply_markup=get_id_kb(config.SUPPORT_USERNAME),
    )
    await callback.answer()


@router.callback_query(F.data == "info")
async def cb_info(callback: CallbackQuery):
    from keyboards.user_kb import back_to_menu_kb
    await callback.message.edit_text(
        f"ℹ️ <b>Информация о боте</b>\n\n"
        f"🤖 <b>{config.BOT_NAME}</b> — система онлайн-тестирования.\n\n"
        f"📋 <b>Правила экзамена:</b>\n"
        f"  • {config.EXAM_QUESTIONS_COUNT} вопросов с вариантами ответа\n"
        f"  • Время: {config.EXAM_TIME_LIMIT_MINUTES} минут\n"
        f"  • Проходной балл: {int(config.PASS_THRESHOLD * 100)}%\n"
        f"  • Максимум попыток в день: {config.MAX_DAILY_ATTEMPTS}\n\n"
        f"📌 <b>Как проходить:</b>\n"
        f"  1. Нажмите «Начать экзамен»\n"
        f"  2. Выбирайте ответы на вопросы\n"
        f"  3. По окончании увидите результат\n\n"
        f"💡 Внимательно читайте каждый вопрос!",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    from keyboards.user_kb import back_to_menu_kb
    await callback.message.edit_text(
        f"☎️ <b>Поддержка</b>\n\n"
        f"По всем вопросам обращайтесь:\n"
        f"👨‍💻 {config.SUPPORT_USERNAME}\n\n"
        f"🆔 Ваш ID: <code>{callback.from_user.id}</code>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
