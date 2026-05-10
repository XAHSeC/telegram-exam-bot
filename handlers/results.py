from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import get_user, check_access, get_user_results, get_session_errors
from keyboards.user_kb import back_to_menu_kb, results_kb, errors_nav_kb
from utils.helpers import format_time, get_grade, get_grade_emoji

router = Router()


@router.callback_query(F.data == "my_results")
async def cb_my_results(callback: CallbackQuery):
    uid = callback.from_user.id
    db_user = await get_user(uid)
    has_access, _ = check_access(db_user)
    if not has_access:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    results = await get_user_results(uid, limit=10)
    if not results:
        await callback.message.edit_text(
            "📊 <b>Ваши результаты</b>\n\n"
            "У вас пока нет завершённых экзаменов.\n"
            "Пройдите первый экзамен!",
            parse_mode="HTML",
            reply_markup=results_kb(),
        )
        await callback.answer()
        return

    lines = ["📊 <b>Ваши последние результаты:</b>\n"]
    for i, r in enumerate(results, 1):
        icon = get_grade_emoji(bool(r["passed"]))
        score = r["score_percent"]
        time_str = format_time(r["time_spent_seconds"])
        date_str = r["finished_at"][:10] if r["finished_at"] else "—"
        lines.append(
            f"{i}. {icon} <b>{score:.1f}%</b> — {r['correct_answers']}/{r['total_questions']} "
            f"| {time_str} | {date_str}"
        )

    best = max(results, key=lambda r: r["score_percent"])
    lines.append(f"\n🏆 Лучший результат: <b>{best['score_percent']:.1f}%</b>")
    passed_count = sum(1 for r in results if r["passed"])
    lines.append(f"✅ Сдано: {passed_count}/{len(results)}")

    # Show error review button for the latest session
    latest_session_id = results[0]["id"] if results else 0

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=results_kb(latest_session_id),
    )
    await callback.answer()


# ─── Error review ─────────────────────────────────────────────────────────────

async def _show_error(callback: CallbackQuery, errors: list, index: int, session_id: int):
    total = len(errors)
    e = errors[index]

    letters = ["A", "B", "C", "D", "E"]
    answers_text = ""
    for i, ans in enumerate(e["answers"]):
        label = letters[i] if i < len(letters) else str(i + 1)
        if ans["is_correct"]:
            answers_text += f"  ✅ {label}) {ans['text']}\n"
        elif ans["id"] == e["selected_answer_id"]:
            answers_text += f"  ❌ {label}) {ans['text']}\n"
        else:
            answers_text += f"  ▫️ {label}) {ans['text']}\n"

    text = (
        f"📋 <b>Разбор ошибок</b>  {index + 1}/{total}\n"
        f"{'━' * 25}\n\n"
        f"❓ <b>{e['question_text']}</b>\n\n"
        f"{answers_text}\n"
        f"❌ Ваш ответ: <i>{e['selected_text']}</i>\n"
        f"✅ Правильно: <b>{e['correct_text']}</b>\n"
    )

    if e.get("explanation"):
        text += f"\n💡 <i>{e['explanation']}</i>"

    kb = errors_nav_kb(session_id, index, total)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("review_errors:"))
async def cb_review_errors(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split(":")[1])
    errors = await get_session_errors(session_id)

    if not errors:
        await callback.answer("🎉 Ошибок нет — все ответы верные!", show_alert=True)
        return

    # Cache errors in FSM state for navigation
    await state.update_data(review_errors=errors, review_session_id=session_id)
    await _show_error(callback, errors, 0, session_id)
    await callback.answer()


@router.callback_query(F.data.startswith("err_nav:"))
async def cb_err_nav(callback: CallbackQuery, state: FSMContext):
    _, session_id_str, index_str = callback.data.split(":")
    session_id = int(session_id_str)
    index = int(index_str)

    data = await state.get_data()
    errors = data.get("review_errors")

    # Reload from DB if state was lost
    if not errors or data.get("review_session_id") != session_id:
        errors = await get_session_errors(session_id)
        await state.update_data(review_errors=errors, review_session_id=session_id)

    if not errors or index >= len(errors):
        await callback.answer("Ошибка навигации.", show_alert=True)
        return

    await _show_error(callback, errors, index, session_id)
    await callback.answer()
