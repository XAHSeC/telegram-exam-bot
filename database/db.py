import aiosqlite
import asyncio
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from config import config


DB_PATH = config.DATABASE_URL


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                is_blocked INTEGER DEFAULT 0,
                access_expires_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                added_by INTEGER
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                image_path TEXT,
                category TEXT DEFAULT 'general',
                explanation TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                is_correct INTEGER DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                started_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT,
                is_completed INTEGER DEFAULT 0,
                total_questions INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                time_spent_seconds INTEGER DEFAULT 0,
                current_question_index INTEGER DEFAULT 0,
                score_percent REAL DEFAULT 0.0,
                passed INTEGER DEFAULT 0,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS exam_session_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                order_num INTEGER NOT NULL,
                selected_answer_id INTEGER,
                is_correct INTEGER,
                FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            );

            CREATE TABLE IF NOT EXISTS attempt_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_hash TEXT,
                attempted_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                telegram_id INTEGER NOT NULL,
                window_start TEXT NOT NULL,
                message_count INTEGER DEFAULT 1,
                PRIMARY KEY (telegram_id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
            CREATE INDEX IF NOT EXISTS idx_sessions_telegram_id ON exam_sessions(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_attempt_logs_telegram_id ON attempt_logs(telegram_id);
        """)
        await db.commit()


# ─── User operations ─────────────────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def add_user(telegram_id: int, username: str, full_name: str, added_by: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR IGNORE INTO users (telegram_id, username, full_name, added_by)
                   VALUES (?, ?, ?, ?)""",
                (telegram_id, username, full_name, added_by),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def upsert_user_info(telegram_id: int, username: str, full_name: str):
    """Update username/full_name for known users (called on every /start)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users SET username = ?, full_name = ?
               WHERE telegram_id = ?""",
            (username, full_name, telegram_id),
        )
        await db.commit()


async def remove_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def block_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET is_blocked = 1 WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def unblock_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET is_blocked = 0 WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def set_user_expiry(telegram_id: int, expires_at: Optional[str]) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET access_expires_at = ? WHERE telegram_id = ?",
            (expires_at, telegram_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


def check_access(user: Optional[Dict]) -> tuple[bool, str]:
    """Returns (has_access, reason)."""
    if not user:
        return False, "not_found"
    if user["is_blocked"]:
        return False, "blocked"
    if user["access_expires_at"]:
        expires = datetime.fromisoformat(user["access_expires_at"])
        if datetime.utcnow() > expires:
            return False, "expired"
    return True, "ok"


# ─── Question operations ──────────────────────────────────────────────────────

async def get_random_questions(count: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT q.*,
                      GROUP_CONCAT(a.id || '|' || a.text || '|' || a.is_correct, ';;') as answers_raw
               FROM questions q
               JOIN answers a ON a.question_id = q.id
               WHERE q.is_active = 1
               GROUP BY q.id
               ORDER BY RANDOM()
               LIMIT ?""",
            (count,),
        ) as cursor:
            rows = await cursor.fetchall()
            questions = []
            for row in rows:
                q = dict(row)
                answers = []
                if q["answers_raw"]:
                    for part in q["answers_raw"].split(";;"):
                        aid, atext, ais_correct = part.split("|", 2)
                        answers.append({
                            "id": int(aid),
                            "text": atext,
                            "is_correct": int(ais_correct),
                        })
                q["answers"] = answers
                del q["answers_raw"]
                questions.append(q)
            return questions


async def get_question_with_answers(question_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ) as cursor:
            q_row = await cursor.fetchone()
        if not q_row:
            return None
        q = dict(q_row)
        async with db.execute(
            "SELECT * FROM answers WHERE question_id = ?", (question_id,)
        ) as cursor:
            answers = [dict(r) for r in await cursor.fetchall()]
        q["answers"] = answers
        return q


async def add_question(text: str, category: str, explanation: str,
                       image_path: Optional[str], answers: List[Dict]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO questions (text, category, explanation, image_path)
               VALUES (?, ?, ?, ?)""",
            (text, category, explanation, image_path),
        )
        qid = cursor.lastrowid
        for ans in answers:
            await db.execute(
                "INSERT INTO answers (question_id, text, is_correct) VALUES (?, ?, ?)",
                (qid, ans["text"], 1 if ans["is_correct"] else 0),
            )
        await db.commit()
        return qid


async def get_questions_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM questions WHERE is_active = 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ─── Exam session operations ──────────────────────────────────────────────────

async def create_exam_session(telegram_id: int, question_ids: List[int]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO exam_sessions (telegram_id, total_questions)
               VALUES (?, ?)""",
            (telegram_id, len(question_ids)),
        )
        session_id = cursor.lastrowid
        for order, qid in enumerate(question_ids):
            await db.execute(
                """INSERT INTO exam_session_questions (session_id, question_id, order_num)
                   VALUES (?, ?, ?)""",
                (session_id, qid, order),
            )
        await db.commit()
        return session_id


async def get_active_session(telegram_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM exam_sessions
               WHERE telegram_id = ? AND is_completed = 0
               ORDER BY started_at DESC LIMIT 1""",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_session_question(session_id: int, order_num: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT esq.*, q.text, q.image_path, q.category, q.explanation
               FROM exam_session_questions esq
               JOIN questions q ON q.id = esq.question_id
               WHERE esq.session_id = ? AND esq.order_num = ?""",
            (session_id, order_num),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            sq = dict(row)
            async with db.execute(
                "SELECT * FROM answers WHERE question_id = ?", (sq["question_id"],)
            ) as ac:
                sq["answers"] = [dict(r) for r in await ac.fetchall()]
            return sq


async def save_answer(session_id: int, question_id: int, answer_id: int,
                      is_correct: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE exam_session_questions
               SET selected_answer_id = ?, is_correct = ?
               WHERE session_id = ? AND question_id = ?""",
            (answer_id, 1 if is_correct else 0, session_id, question_id),
        )
        await db.commit()


async def update_session_progress(session_id: int, current_index: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE exam_sessions SET current_question_index = ? WHERE id = ?",
            (current_index, session_id),
        )
        await db.commit()


async def complete_session(session_id: int, correct: int, total: int,
                           time_seconds: int) -> Dict:
    score_percent = (correct / total * 100) if total > 0 else 0
    passed = 1 if score_percent >= (config.PASS_THRESHOLD * 100) else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE exam_sessions
               SET is_completed = 1,
                   finished_at = datetime('now'),
                   correct_answers = ?,
                   time_spent_seconds = ?,
                   score_percent = ?,
                   passed = ?
               WHERE id = ?""",
            (correct, time_seconds, score_percent, passed, session_id),
        )
        await db.commit()
    return {
        "session_id": session_id,
        "correct": correct,
        "total": total,
        "score_percent": score_percent,
        "passed": bool(passed),
        "time_seconds": time_seconds,
    }


async def get_user_results(telegram_id: int, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM exam_sessions
               WHERE telegram_id = ? AND is_completed = 1
               ORDER BY finished_at DESC LIMIT ?""",
            (telegram_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_today_attempts(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        async with db.execute(
            """SELECT COUNT(*) FROM exam_sessions
               WHERE telegram_id = ? AND DATE(started_at) = ? AND is_completed = 1""",
            (telegram_id, today),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ─── Logging ──────────────────────────────────────────────────────────────────

async def log_action(telegram_id: int, action: str, details: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO attempt_logs (telegram_id, action, details) VALUES (?, ?, ?)",
            (telegram_id, action, details),
        )
        await db.commit()


# ─── Stats ────────────────────────────────────────────────────────────────────

async def get_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0") as c:
            active_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM questions WHERE is_active = 1") as c:
            total_questions = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM exam_sessions WHERE is_completed = 1") as c:
            total_exams = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM exam_sessions WHERE is_completed = 1 AND passed = 1"
        ) as c:
            passed_exams = (await c.fetchone())[0]
        async with db.execute(
            "SELECT AVG(score_percent) FROM exam_sessions WHERE is_completed = 1"
        ) as c:
            avg_score = (await c.fetchone())[0] or 0
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_questions": total_questions,
            "total_exams": total_exams,
            "passed_exams": passed_exams,
            "avg_score": round(avg_score, 1),
        }
