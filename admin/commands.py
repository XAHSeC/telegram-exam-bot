from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (
    add_user, remove_user, block_user, unblock_user,
    get_all_users, get_stats, get_user, log_action,
    activate_question, deactivate_question, delete_question,
    search_questions, get_questions_page, get_total_questions_count,
    get_question_with_answers,
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


# ─── Question management ──────────────────────────────────────────────────────

def _questions_kb(questions, offset, total):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for q in questions:
        status = "✅" if q["is_active"] else "🚫"
        label = f"{status} #{q['id']} {q['text'][:35]}..."
        builder.button(text=label, callback_data=f"qmgr_view:{q['id']}")
    builder.adjust(1)
    nav = []
    if offset > 0:
        nav.append(("◀️ Назад", f"qmgr_page:{max(0, offset-10)}"))
    if offset + 10 < total:
        nav.append(("▶️ Далее", f"qmgr_page:{offset+10}"))
    for label, cb in nav:
        builder.button(text=label, callback_data=cb)
    builder.button(text="🔍 Поиск", callback_data="qmgr_search_prompt")
    builder.button(text="◀️ Меню", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("questions"))
@admin_only
async def cmd_questions(message: Message):
    total = await get_total_questions_count()
    qs = await get_questions_page(offset=0, limit=10)
    await message.answer(
        f"❓ <b>Вопросы в базе ({total} всего)</b>\nВыберите вопрос:",
        parse_mode="HTML",
        reply_markup=_questions_kb(qs, 0, total),
    )


@router.callback_query(F.data.startswith("qmgr_page:"))
@admin_only
async def cb_qmgr_page(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    total = await get_total_questions_count()
    qs = await get_questions_page(offset=offset, limit=10)
    await callback.message.edit_text(
        f"❓ <b>Вопросы в базе ({total} всего)</b>\nВыберите вопрос:",
        parse_mode="HTML",
        reply_markup=_questions_kb(qs, offset, total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qmgr_view:"))
@admin_only
async def cb_qmgr_view(callback: CallbackQuery):
    qid = int(callback.data.split(":")[1])
    q = await get_question_with_answers(qid)
    if not q:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    status = "✅ Активен" if q["is_active"] else "🚫 Скрыт"
    answers_text = "\n".join(
        f"  {'✔' if a['is_correct'] else '—'} {a['text'][:60]}"
        for a in q["answers"]
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if q["is_active"]:
        builder.button(text="🚫 Скрыть вопрос", callback_data=f"qmgr_hide:{qid}")
    else:
        builder.button(text="✅ Активировать", callback_data=f"qmgr_activate:{qid}")
    builder.button(text="🗑 Удалить навсегда", callback_data=f"qmgr_del_prompt:{qid}")
    builder.button(text="◀️ К списку", callback_data="qmgr_page:0")
    builder.adjust(1)

    await callback.message.edit_text(
        f"❓ <b>Вопрос #{qid}</b> [{status}]\n\n"
        f"<b>{q['text'][:300]}</b>\n\n"
        f"Варианты:\n{answers_text}\n\n"
        f"Категория: {q.get('category','—')}",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qmgr_hide:"))
@admin_only
async def cb_qmgr_hide(callback: CallbackQuery):
    qid = int(callback.data.split(":")[1])
    ok = await deactivate_question(qid)
    await log_action(callback.from_user.id, "hide_question", f"qid={qid}")
    await callback.answer("🚫 Вопрос скрыт из экзаменов" if ok else "Уже скрыт", show_alert=True)
    callback.data = f"qmgr_view:{qid}"
    await cb_qmgr_view(callback)


@router.callback_query(F.data.startswith("qmgr_activate:"))
@admin_only
async def cb_qmgr_activate(callback: CallbackQuery):
    qid = int(callback.data.split(":")[1])
    await activate_question(qid)
    await log_action(callback.from_user.id, "activate_question", f"qid={qid}")
    await callback.answer("✅ Вопрос активирован", show_alert=True)
    callback.data = f"qmgr_view:{qid}"
    await cb_qmgr_view(callback)


@router.callback_query(F.data.startswith("qmgr_del_prompt:"))
@admin_only
async def cb_qmgr_del_prompt(callback: CallbackQuery):
    qid = int(callback.data.split(":")[1])
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"qmgr_del_confirm:{qid}")
    builder.button(text="❌ Отмена", callback_data=f"qmgr_view:{qid}")
    builder.adjust(2)
    await callback.message.edit_text(
        f"🗑 Удалить вопрос #{qid} навсегда?\n\nЭто действие нельзя отменить.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qmgr_del_confirm:"))
@admin_only
async def cb_qmgr_del_confirm(callback: CallbackQuery):
    qid = int(callback.data.split(":")[1])
    ok = await delete_question(qid)
    await log_action(callback.from_user.id, "delete_question", f"qid={qid}")
    await callback.answer("🗑 Вопрос удалён" if ok else "Не найден", show_alert=True)
    total = await get_total_questions_count()
    qs = await get_questions_page(offset=0, limit=10)
    await callback.message.edit_text(
        f"❓ <b>Вопросы в базе ({total} всего)</b>\nВыберите вопрос:",
        parse_mode="HTML",
        reply_markup=_questions_kb(qs, 0, total),
    )


# ─── /hide_question and /del_question text commands ──────────────────────────

@router.message(Command("hide_question"))
@admin_only
async def cmd_hide_question(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /hide_question <id>")
        return
    try:
        qid = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    ok = await deactivate_question(qid)
    await log_action(message.from_user.id, "hide_question", f"qid={qid}")
    if ok:
        await message.answer(f"🚫 Вопрос #{qid} скрыт из экзаменов.")
    else:
        await message.answer(f"❌ Вопрос #{qid} не найден или уже скрыт.")


@router.message(Command("del_question"))
@admin_only
async def cmd_del_question(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /del_question <id>")
        return
    try:
        qid = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    ok = await delete_question(qid)
    await log_action(message.from_user.id, "delete_question", f"qid={qid}")
    if ok:
        await message.answer(f"🗑 Вопрос #{qid} удалён навсегда.")
    else:
        await message.answer(f"❌ Вопрос #{qid} не найден.")


@router.message(Command("find_question"))
@admin_only
async def cmd_find_question(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /find_question <текст>")
        return
    query = parts[1]
    results = await search_questions(query)
    if not results:
        await message.answer("❌ Вопросы не найдены.")
        return
    lines = [f"🔍 Найдено {len(results)} вопрос(ов):\n"]
    for q in results:
        status = "✅" if q["is_active"] else "🚫"
        lines.append(f"{status} <code>#{q['id']}</code> {q['text'][:80]}...")
    lines.append("\nЧтобы скрыть: /hide_question &lt;id&gt;\nЧтобы удалить: /del_question &lt;id&gt;")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "qmgr_search_prompt")
@admin_only
async def cb_qmgr_search_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 Введите текст для поиска вопроса командой:\n/find_question &lt;текст&gt;",
        parse_mode="HTML",
    )
    await callback.answer()
