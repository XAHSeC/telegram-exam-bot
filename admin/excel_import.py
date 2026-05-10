import io
import os
import tempfile
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import add_question, get_questions_count, log_action
from config import config
from utils.logger import logger

router = Router()


class ImportState(StatesGroup):
    waiting_for_file = State()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.callback_query(F.data == "admin_import")
async def cb_admin_import(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет прав.", show_alert=True)
        return

    await callback.message.edit_text(
        "📥 <b>Импорт вопросов из Excel</b>\n\n"
        "Загрузите файл <b>.xlsx</b> или <b>.xls</b> со следующей структурой:\n\n"
        "<b>Колонки (обязательные):</b>\n"
        "• <code>question</code> — текст вопроса\n"
        "• <code>answer_1</code> — вариант ответа 1\n"
        "• <code>answer_2</code> — вариант ответа 2\n"
        "• <code>answer_3</code> — вариант ответа 3\n"
        "• <code>answer_4</code> — вариант ответа 4\n"
        "• <code>answer_5</code> — вариант ответа 5 (необязательный)\n"
        "• <code>correct</code> — номер правильного ответа (1-5)\n\n"
        "<b>Необязательные:</b>\n"
        "• <code>category</code> — категория\n"
        "• <code>explanation</code> — объяснение\n"
        "• <code>image_url</code> — URL картинки (https://...)\n\n"
        "Отправьте файл сейчас:",
        parse_mode="HTML",
    )
    await state.set_state(ImportState.waiting_for_file)
    await callback.answer()


@router.message(ImportState.waiting_for_file, F.document)
async def handle_excel_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    doc: Document = message.document
    fname = doc.file_name or ""
    if not fname.lower().endswith((".xlsx", ".xls")):
        await message.answer("❌ Пожалуйста, загрузите файл формата .xlsx или .xls")
        return

    await message.answer("⏳ Обрабатываю файл...")

    try:
        import openpyxl
    except ImportError:
        await message.answer(
            "❌ Модуль openpyxl не установлен.\n"
            "Выполните: pip install openpyxl"
        )
        await state.clear()
        return

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await message.bot.download(doc, destination=tmp_path)
        results = await _process_excel(tmp_path)
    except Exception as e:
        logger.error("Excel import error: %s", e)
        await message.answer(f"❌ Ошибка при обработке файла:\n<code>{e}</code>", parse_mode="HTML")
        await state.clear()
        return
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    await state.clear()
    await log_action(message.from_user.id, "admin_import", f"imported={results['imported']} errors={results['errors']}")

    total = await get_questions_count()
    await message.answer(
        f"✅ <b>Импорт завершён</b>\n\n"
        f"➕ Добавлено вопросов: <b>{results['imported']}</b>\n"
        f"❌ Ошибок: <b>{results['errors']}</b>\n"
        f"⚠️ Пропущено: <b>{results['skipped']}</b>\n\n"
        f"📚 Итого вопросов в базе: <b>{total}</b>",
        parse_mode="HTML",
    )


async def _process_excel(path: str) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"imported": 0, "errors": 0, "skipped": 0}

    # Map header columns
    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    col = {name: idx for idx, name in enumerate(header)}

    required = {"question", "answer_1", "answer_2", "correct"}
    if not required.issubset(col.keys()):
        missing = required - col.keys()
        raise ValueError(f"Отсутствуют обязательные колонки: {missing}")

    # Detect how many answer columns exist (answer_1 .. answer_5)
    max_answers = max(
        (i for i in range(1, 6) if f"answer_{i}" in col),
        default=4,
    )

    imported = errors = skipped = 0

    for row_num, row in enumerate(rows[1:], start=2):
        try:
            q_text = str(row[col["question"]]).strip() if row[col["question"]] else ""
            if not q_text or q_text.lower() == "none":
                skipped += 1
                continue

            correct_num = int(row[col["correct"]]) if row[col["correct"]] else 0
            if correct_num < 1 or correct_num > max_answers:
                errors += 1
                continue

            answers = []
            for i in range(1, max_answers + 1):
                key = f"answer_{i}"
                if key in col and row[col[key]]:
                    text = str(row[col[key]]).strip()
                    if text and text.lower() != "none":
                        answers.append({"text": text, "is_correct": (i == correct_num)})

            if len(answers) < 2:
                skipped += 1
                continue

            category = ""
            if "category" in col and row[col["category"]]:
                category = str(row[col["category"]]).strip()

            explanation = ""
            if "explanation" in col and row[col["explanation"]]:
                explanation = str(row[col["explanation"]]).strip()

            image_url = None
            for img_key in ("image_url", "image", "photo", "photo_url"):
                if img_key in col and row[col[img_key]]:
                    val = str(row[col[img_key]]).strip()
                    if val and val.lower() not in ("none", "—", "-", ""):
                        image_url = val
                        break

            await add_question(
                text=q_text,
                category=category or "general",
                explanation=explanation,
                image_path=image_url,
                answers=answers,
            )
            imported += 1

        except Exception as e:
            logger.warning("Row %d error: %s", row_num, e)
            errors += 1

    wb.close()
    return {"imported": imported, "errors": errors, "skipped": skipped}


@router.callback_query(F.data == "admin_questions")
async def cb_admin_questions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет прав.", show_alert=True)
        return

    from database.db import get_questions_count
    from keyboards.admin_kb import admin_panel_kb
    count = await get_questions_count()
    await callback.message.edit_text(
        f"❓ <b>Вопросы</b>\n\n"
        f"Всего активных вопросов: <b>{count}</b>\n\n"
        f"Для добавления вопросов используйте импорт Excel.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()
