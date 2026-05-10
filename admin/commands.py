from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (
    add_user, remove_user, block_user, unblock_user,
    get_all_users, get_stats, get_user, log_action,
)
from keyboards.admin_kb import admin_panel_kb, admin_user_actions_kb, confirm_delete_kb
from config import config
from utils.logger import logger

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def admin_only(func):
    import functools
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, "from_user") else 0
        if not is_admin(uid):
            if isinstance(event, Message):
                await event.answer("🚫 Нет прав администратора.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Нет прав администратора.", show_alert=True)
            return
        return await func(event, *args, **kwargs)
    return wrapper


# ─── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    await message.answer(
        "👨‍💼 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


# ─── /add_user ────────────────────────────────────────────────────────────────

@router.message(Command("add_user"))
@admin_only
async def cmd_add_user(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /add_user <telegram_id> [username]")
        return

    try:
        tid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID (должно быть число).")
        return

    username = parts[2] if len(parts) > 2 else ""
    ok = await add_user(tid, username, username, message.from_user.id)
    if ok:
        await message.answer(f"✅ Пользователь <code>{tid}</code> добавлен.", parse_mode="HTML")
        await log_action(message.from_user.id, "admin_add_user", f"target={tid}")
        # Notify the user
        try:
            await message.bot.send_message(
                tid,
                f"✅ <b>Доступ предоставлен!</b>\n\n"
                f"Теперь вы можете начать экзамен.\n"
                f"Напишите /start для продолжения.",
                parse_mode="HTML",
            )
        except Exception:
            await message.answer("⚠️ Не удалось отправить уведомление пользователю.")
    else:
        await message.answer(f"⚠️ Пользователь <code>{tid}</code> уже существует.", parse_mode="HTML")


# ─── /remove_user ─────────────────────────────────────────────────────────────

@router.message(Command("remove_user"))
@admin_only
async def cmd_remove_user(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /remove_user <telegram_id>")
        return
    try:
        tid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID.")
        return

    ok = await remove_user(tid)
    if ok:
        await message.answer(f"✅ Пользователь <code>{tid}</code> удалён.", parse_mode="HTML")
        await log_action(message.from_user.id, "admin_remove_user", f"target={tid}")
    else:
        await message.answer(f"❌ Пользователь <code>{tid}</code> не найден.", parse_mode="HTML")


# ─── /block_user ──────────────────────────────────────────────────────────────

@router.message(Command("block_user"))
@admin_only
async def cmd_block_user(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /block_user <telegram_id>")
        return
    try:
        tid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID.")
        return

    ok = await block_user(tid)
    if ok:
        await message.answer(f"🚫 Пользователь <code>{tid}</code> заблокирован.", parse_mode="HTML")
        await log_action(message.from_user.id, "admin_block_user", f"target={tid}")
    else:
        await message.answer(f"❌ Пользователь <code>{tid}</code> не найден.", parse_mode="HTML")


# ─── /unblock_user ────────────────────────────────────────────────────────────

@router.message(Command("unblock_user"))
@admin_only
async def cmd_unblock_user(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unblock_user <telegram_id>")
        return
    try:
        tid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный Telegram ID.")
        return

    ok = await unblock_user(tid)
    if ok:
        await message.answer(f"✅ Пользователь <code>{tid}</code> разблокирован.", parse_mode="HTML")
        await log_action(message.from_user.id, "admin_unblock_user", f"target={tid}")
    else:
        await message.answer(f"❌ Пользователь <code>{tid}</code> не найден.", parse_mode="HTML")


# ─── /users ───────────────────────────────────────────────────────────────────

@router.message(Command("users"))
@admin_only
async def cmd_users(message: Message):
    users = await get_all_users()
    if not users:
        await message.answer("👥 Пользователей нет.")
        return

    lines = [f"👥 <b>Пользователи ({len(users)}):</b>\n"]
    for u in users[:50]:  # max 50 to avoid message length limit
        status = "🚫" if u["is_blocked"] else "✅"
        username = f"@{u['username']}" if u["username"] else "—"
        lines.append(f"{status} <code>{u['telegram_id']}</code> {username} — {u['full_name'] or '—'}")

    if len(users) > 50:
        lines.append(f"\n... и ещё {len(users) - 50} пользователей")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /stats ───────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message):
    s = await get_stats()
    pass_rate = (
        f"{s['passed_exams'] / s['total_exams'] * 100:.1f}%"
        if s["total_exams"] > 0 else "—"
    )
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b>\n"
        f"✅ Активных: <b>{s['active_users']}</b>\n"
        f"🚫 Заблокированных: <b>{s['total_users'] - s['active_users']}</b>\n\n"
        f"❓ Вопросов в базе: <b>{s['total_questions']}</b>\n\n"
        f"📝 Всего экзаменов: <b>{s['total_exams']}</b>\n"
        f"✅ Сдано: <b>{s['passed_exams']}</b>\n"
        f"📈 Процент сдачи: <b>{pass_rate}</b>\n"
        f"⭐ Средний балл: <b>{s['avg_score']}%</b>",
        parse_mode="HTML",
    )


# ─── Inline admin actions ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
@admin_only
async def cb_admin_users(callback: CallbackQuery):
    users = await get_all_users()
    if not users:
        await callback.message.edit_text("👥 Пользователей нет.", reply_markup=admin_panel_kb())
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for u in users[:20]:
        status = "🚫" if u["is_blocked"] else "✅"
        label = f"{status} {u['telegram_id']} {('@' + u['username']) if u['username'] else ''}"
        builder.button(text=label[:50], callback_data=f"admin_view_user:{u['telegram_id']}")
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(1)

    await callback.message.edit_text(
        f"👥 <b>Пользователи ({len(users)})</b>\nВыберите для управления:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_user:"))
@admin_only
async def cb_admin_view_user(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    user = await get_user(tid)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    status = "🚫 Заблокирован" if user["is_blocked"] else "✅ Активен"
    expires = user["access_expires_at"] or "Бессрочно"
    await callback.message.edit_text(
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user['telegram_id']}</code>\n"
        f"Username: @{user['username'] or '—'}\n"
        f"Имя: {user['full_name'] or '—'}\n"
        f"Статус: {status}\n"
        f"Доступ до: {expires}\n"
        f"Добавлен: {user['created_at'][:10]}",
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(tid, bool(user["is_blocked"])),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_block:"))
@admin_only
async def cb_admin_block(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    await block_user(tid)
    await log_action(callback.from_user.id, "admin_block_user", f"target={tid}")
    await callback.answer("🚫 Заблокирован", show_alert=True)
    await cb_admin_view_user(callback)


@router.callback_query(F.data.startswith("admin_unblock:"))
@admin_only
async def cb_admin_unblock(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    # fix callback data for view
    callback.data = f"admin_view_user:{tid}"
    await unblock_user(tid)
    await log_action(callback.from_user.id, "admin_unblock_user", f"target={tid}")
    await callback.answer("✅ Разблокирован", show_alert=True)
    await cb_admin_view_user(callback)


@router.callback_query(F.data.startswith("admin_delete:"))
@admin_only
async def cb_admin_delete_prompt(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"🗑 Удалить пользователя <code>{tid}</code>?\nЭто действие нельзя отменить.",
        parse_mode="HTML",
        reply_markup=confirm_delete_kb(tid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete:"))
@admin_only
async def cb_admin_confirm_delete(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    await remove_user(tid)
    await log_action(callback.from_user.id, "admin_delete_user", f"target={tid}")
    await callback.answer("🗑 Удалён", show_alert=True)
    await callback.message.edit_text("🗑 Пользователь удалён.", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_stats")
@admin_only
async def cb_admin_stats(callback: CallbackQuery):
    s = await get_stats()
    pass_rate = (
        f"{s['passed_exams'] / s['total_exams'] * 100:.1f}%"
        if s["total_exams"] > 0 else "—"
    )
    from keyboards.admin_kb import admin_panel_kb
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{s['total_users']}</b> (актив: {s['active_users']})\n"
        f"❓ Вопросов: <b>{s['total_questions']}</b>\n"
        f"📝 Экзаменов: <b>{s['total_exams']}</b>\n"
        f"✅ Сдано: <b>{s['passed_exams']}</b> ({pass_rate})\n"
        f"⭐ Средний балл: <b>{s['avg_score']}%</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_back")
@admin_only
async def cb_admin_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "👨‍💼 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()
