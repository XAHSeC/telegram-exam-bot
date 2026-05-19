import asyncio
import time
from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (
    get_user, check_access, get_random_questions, create_exam_session,
    get_active_session, get_session_question, save_answer,
    update_session_progress, complete_session, get_today_attempts,
    get_questions_count, log_action,
)
from keyboards.user_kb import (
    exam_answer_kb, confirm_start_kb, confirm_finish_kb,
    back_to_menu_kb, results_kb, main_menu_kb,
)
from utils.helpers import format_time, get_grade, get_grade_emoji, progress_bar
from utils.logger import logger
from config import config

router = Router()


class ExamState(StatesGroup):
    in_exam = State()
    confirming_start = State()
    confirming_finish = State()


# ─── Guard helper ─────────────────────────────────────────────────────────────

async def _check_user_access(callback: CallbackQuery) -> bool:
    db_user = await get_user(callback.from_user.id)
    has_access, reason = check_access(db_user)
    if not has_access:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
    return has_access


# ─── Start exam ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "start_exam")
async def cb_start_exam(callback: CallbackQuery, state: FSMContext):
    if not await _check_user_access(callback):
        return

    uid = callback.from_user.id

    # Check daily limit
    today_count = await get_today_attempts(uid)
    if today_count >= config.MAX_DAILY_ATTEMPTS:
        await callback.message.edit_text(
            f"⚠️ <b>Лимит исчерпан</b>\n\n"
            f"Вы использовали все <b>{config.MAX_DAILY_ATTEMPTS}</b> попытки на сегодня.\n"
            f"Возвращайтесь завтра! 🌙",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    # Check question bank
    q_count = await get_questions_count()
    if q_count < config.EXAM_QUESTIONS_COUNT:
        await callback.message.edit_text(
            f"⚠️ <b>База вопросов недостаточна</b>\n\n"
            f"Доступно вопросов: {q_count}\n"
            f"Необходимо: {config.EXAM_QUESTIONS_COUNT}\n\n"
            f"Обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    # Check active session
    active = await get_active_session(uid)
    if active:
        await callback.message.edit_text(
            f"⚠️ <b>У вас есть незавершённый экзамен</b>\n\n"
            f"Вопрос {active['current_question_index'] + 1} из {active['total_questions']}\n\n"
            f"Продолжить или начать новый?",
            parse_mode="HTML",
            reply_markup=_resume_or_new_kb(active["id"]),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📋 <b>Подтверждение начала экзамена</b>\n\n"
        f"• Количество вопросов: <b>{config.EXAM_QUESTIONS_COUNT}</b>\n"
        f"• Ограничение по времени: <b>{config.EXAM_TIME_LIMIT_MINUTES} мин</b>\n"
        f"• Использованных попыток сегодня: <b>{today_count}/{config.MAX_DAILY_ATTEMPTS}</b>\n\n"
        f"❗ После начала экзамен не может быть приостановлен.\n\n"
        f"Вы готовы?",
        parse_mode="HTML",
        reply_markup=confirm_start_kb(),
    )
    await state.set_state(ExamState.confirming_start)
    await callback.answer()


@router.callback_query(F.data == "confirm_start_exam", ExamState.confirming_start)
async def cb_confirm_start(callback: CallbackQuery, state: FSMContext):
    if not await _check_user_access(callback):
        return

    uid = callback.from_user.id
    await callback.message.edit_text("⏳ <b>Готовим вопросы...</b>", parse_mode="HTML")

    questions = await get_random_questions(config.EXAM_QUESTIONS_COUNT)
    if not questions:
        await callback.message.edit_text(
            "❌ Не удалось загрузить вопросы. Обратитесь к администратору.",
            reply_markup=back_to_menu_kb(),
        )
        await state.clear()
        return

    q_ids = [q["id"] for q in questions]
    session_id = await create_exam_session(uid, q_ids)

    await state.update_data(
        session_id=session_id,
        questions=questions,
        current_index=0,
        correct_count=0,
        start_time=time.time(),
    )
    await state.set_state(ExamState.in_exam)
    await log_action(uid, "exam_start", f"session={session_id}")

    await _send_question(callback, state, 0)


@router.callback_query(F.data == "cancel_exam")
async def cb_cancel_exam(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Экзамен отменён.\n\nГлавное меню:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# ─── Resume ───────────────────────────────────────────────────────────────────

def _resume_or_new_kb(session_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ Продолжить", callback_data=f"resume_exam:{session_id}")
    builder.button(text="🔄 Начать заново", callback_data="new_exam_anyway")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data.startswith("resume_exam:"))
async def cb_resume_exam(callback: CallbackQuery, state: FSMContext):
    if not await _check_user_access(callback):
        return

    session_id = int(callback.data.split(":")[1])
    active = await get_active_session(callback.from_user.id)
    if not active or active["id"] != session_id:
        await callback.answer("Сессия не найдена.", show_alert=True)
        return

    idx = active["current_question_index"]
    sq = await get_session_question(session_id, idx)
    if not sq:
        await callback.answer("Ошибка загрузки вопроса.", show_alert=True)
        return

    # Rebuild state from DB (best-effort; start_time lost but OK)
    from database.db import get_random_questions as _
    questions_raw = []
    total = active["total_questions"]
    for i in range(total):
        q = await get_session_question(session_id, i)
        if q:
            questions_raw.append(q)

    await state.update_data(
        session_id=session_id,
        questions=questions_raw,
        current_index=idx,
        correct_count=active.get("correct_answers", 0),
        start_time=time.time() - (idx * 60),  # rough estimate
    )
    await state.set_state(ExamState.in_exam)
    await _send_question(callback, state, idx)


@router.callback_query(F.data == "new_exam_anyway")
async def cb_new_exam_anyway(callback: CallbackQuery, state: FSMContext):
    """User wants to start fresh — mark the active session as completed with 0."""
    uid = callback.from_user.id
    active = await get_active_session(uid)
    if active:
        await complete_session(active["id"], 0, active["total_questions"], 0)
    await state.clear()
    await callback.message.edit_text(
        "🔄 Предыдущая сессия закрыта. Начинаем новый экзамен...",
        parse_mode="HTML",
    )
    # Re-trigger start_exam flow
    from aiogram.types import CallbackQuery as CQ
    await cb_start_exam(callback, state)


# ─── Question rendering ───────────────────────────────────────────────────────

async def _send_question(callback: CallbackQuery, state: FSMContext, index: int):
    data = await state.get_data()
    questions = data["questions"]
    session_id = data["session_id"]
    total = len(questions)

    if index >= total:
        await _finish_exam(callback, state)
        return

    q = questions[index]
    q_id = q.get("id") or q.get("question_id")
    q_text = q.get("text", "")
    q_image = q.get("image_path")
    answers = q.get("answers", [])
    q_category = q.get("category", "")

    letters = ["A", "B", "C", "D", "E", "F"]
    answers_text = "\n".join(
        f"<b>{letters[i]})</b> {ans['text']}"
        for i, ans in enumerate(answers)
        if i < len(letters)
    )

    bar = progress_bar(index + 1, total)
    header = (
        f"📝 <b>Вопрос {index + 1} из {total}</b>\n"
        f"{bar}\n"
        f"{'🏷 ' + q_category if q_category else ''}\n\n"
        f"{q_text}\n\n"
        f"{answers_text}"
    )

    kb = exam_answer_kb(answers, session_id, q_id)

    try:
        if q_image:
            # Send photo above the question text, then delete previous message
            try:
                await callback.message.delete()
            except Exception:
                pass
            # Telegram caption limit is 1024 chars — truncate if needed
            caption = header[:1020] + "…" if len(header) > 1024 else header
            await callback.message.answer_photo(
                photo=q_image,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await callback.message.edit_text(header, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(header, parse_mode="HTML", reply_markup=kb)

    await callback.answer()


# ─── Answer handling ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("answer:"), ExamState.in_exam)
async def cb_answer(callback: CallbackQuery, state: FSMContext):
    _, session_id_str, question_id_str, answer_id_str = callback.data.split(":")
    session_id = int(session_id_str)
    question_id = int(question_id_str)
    answer_id = int(answer_id_str)

    data = await state.get_data()
    if data.get("session_id") != session_id:
        await callback.answer("Неверная сессия.", show_alert=True)
        return

    questions = data["questions"]
    current_index = data["current_index"]

    # Find the correct answer for this question
    q = questions[current_index]
    q_answers = q.get("answers", [])
    selected = next((a for a in q_answers if a["id"] == answer_id), None)
    is_correct = bool(selected and selected.get("is_correct"))

    # Save to DB
    await save_answer(session_id, question_id, answer_id, is_correct)

    correct_count = data["correct_count"] + (1 if is_correct else 0)
    next_index = current_index + 1

    await state.update_data(current_index=next_index, correct_count=correct_count)
    await update_session_progress(session_id, next_index)

    # Quick feedback
    if is_correct:
        await callback.answer("✅ Правильно!", show_alert=False)
    else:
        correct_text = next(
            (a["text"] for a in q_answers if a.get("is_correct")), "—"
        )
        await callback.answer(f"❌ Неверно\nПравильный ответ: {correct_text}", show_alert=True)

    await _send_question(callback, state, next_index)


# ─── Manual finish ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("finish_exam:"), ExamState.in_exam)
async def cb_finish_exam_prompt(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    total = len(data.get("questions", []))

    await callback.message.edit_text(
        f"⚠️ <b>Завершить экзамен досрочно?</b>\n\n"
        f"Отвечено: {current_index} из {total}\n"
        f"Оставшиеся вопросы будут засчитаны как неверные.",
        parse_mode="HTML",
        reply_markup=confirm_finish_kb(session_id),
    )
    await state.set_state(ExamState.confirming_finish)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_finish:"), ExamState.confirming_finish)
async def cb_confirm_finish(callback: CallbackQuery, state: FSMContext):
    await _finish_exam(callback, state)


@router.callback_query(F.data.startswith("continue_exam:"), ExamState.confirming_finish)
async def cb_continue_exam(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ExamState.in_exam)
    data = await state.get_data()
    idx = data.get("current_index", 0)
    await _send_question(callback, state, idx)


# ─── Finish & results ─────────────────────────────────────────────────────────

async def _finish_exam(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session_id = data["session_id"]
    correct_count = data["correct_count"]
    total = len(data["questions"])
    start_time = data.get("start_time", time.time())
    elapsed = int(time.time() - start_time)

    result = await complete_session(session_id, correct_count, total, elapsed)
    await log_action(callback.from_user.id, "exam_finish", f"session={session_id} score={result['score_percent']:.1f}%")

    await state.clear()

    score = result["score_percent"]
    passed = result["passed"]
    grade = get_grade(score)
    icon = get_grade_emoji(passed)
    time_str = format_time(elapsed)

    text = (
        f"🏁 <b>Экзамен завершён!</b>\n\n"
        f"{'━' * 25}\n"
        f"{icon} <b>Результат: {'СДАН' if passed else 'НЕ СДАН'}</b>\n"
        f"{'━' * 25}\n\n"
        f"✅ Правильных ответов: <b>{correct_count}</b> из <b>{total}</b>\n"
        f"📊 Процент: <b>{score:.1f}%</b>\n"
        f"🎓 Оценка: <b>{grade}</b>\n"
        f"⏱ Время: <b>{time_str}</b>\n\n"
    )

    if passed:
        text += "🎉 <b>Поздравляем! Вы успешно сдали экзамен!</b>"
    else:
        text += f"💪 Не расстраивайтесь! Минимальный балл: {int(config.PASS_THRESHOLD * 100)}%\nПопробуйте ещё раз."

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=results_kb(session_id))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=results_kb(session_id))
    await callback.answer()
