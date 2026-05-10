from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.db import get_user, check_access, get_user_results
from keyboards.user_kb import back_to_menu_kb, results_kb
from utils.helpers import format_time, get_grade_emoji

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

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
