# Telegram Exam Bot

Система онлайн-тестирования через Telegram, построенная на **Python + aiogram 3 + SQLite**.

## Возможности

- Доступ **только по Telegram ID** — без регистрации
- Полная **админ-панель** с командами и inline-кнопками
- **150 случайных вопросов** из общего банка
- Таймер экзамена + процент правильных ответов + оценка
- **Импорт вопросов из Excel** (.xlsx)
- Защита от спама (rate limiter)
- Ограничение попыток (3 в день по умолчанию)
- Логирование всех действий
- Поддержка изображений в вопросах

---

## Структура проекта

```
telegram_exam_bot/
├── bot.py                  # Точка входа
├── config.py               # Конфигурация
├── seed_questions.py       # Заполнение тестовыми вопросами
├── requirements.txt
├── .env.example
├── database/
│   └── db.py               # Все операции с SQLite
├── handlers/
│   ├── start.py            # /start, меню, доступ
│   ├── exam.py             # Логика экзамена (FSM)
│   └── results.py          # История результатов
├── admin/
│   ├── commands.py         # Команды администратора
│   └── excel_import.py     # Импорт вопросов из Excel
├── keyboards/
│   ├── user_kb.py          # Клавиатуры пользователя
│   └── admin_kb.py         # Клавиатуры администратора
├── middlewares/
│   └── access.py           # Rate limiting + логирование
└── utils/
    ├── logger.py
    ├── rate_limiter.py
    └── helpers.py
```

---

## Быстрый старт

### 1. Клонировать и настроить окружение

```bash
cd telegram_exam_bot
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Создать `.env`

```bash
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789            # Ваш Telegram ID
SUPPORT_USERNAME=@your_username
```

### 3. Заполнить базу тестовыми вопросами (опционально)

```bash
python seed_questions.py
```

### 4. Запустить бота

```bash
python bot.py
```

---

## Команды администратора

| Команда | Описание |
|---|---|
| `/admin` | Открыть панель администратора |
| `/add_user 123456789` | Добавить пользователя по ID |
| `/remove_user 123456789` | Удалить пользователя |
| `/block_user 123456789` | Заблокировать пользователя |
| `/unblock_user 123456789` | Разблокировать пользователя |
| `/users` | Список всех пользователей |
| `/stats` | Статистика бота |

---

## Импорт вопросов из Excel

Загрузите файл `.xlsx` через кнопку **«📥 Импорт вопросов»** в панели администратора.

### Структура файла:

| question | answer_1 | answer_2 | answer_3 | answer_4 | correct | category | explanation |
|---|---|---|---|---|---|---|---|
| Вопрос 1 | Ответ A | Ответ B | Ответ C | Ответ D | 1 | Тема | Объяснение |
| Вопрос 2 | Ответ A | Ответ B | Ответ C | Ответ D | 3 | Тема | Объяснение |

- `correct` — номер правильного ответа (1–4)
- `category` и `explanation` — необязательны

---

## Настройки экзамена (`.env`)

| Параметр | По умолчанию | Описание |
|---|---|---|
| `EXAM_QUESTIONS_COUNT` | 150 | Количество вопросов |
| `EXAM_TIME_LIMIT_MINUTES` | 180 | Лимит времени (минуты) |
| `MAX_DAILY_ATTEMPTS` | 3 | Попыток в день |
| `PASS_THRESHOLD` | 0.7 | Проходной балл (70%) |
| `RATE_LIMIT_MESSAGES` | 30 | Сообщений в окне |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Ширина окна лимита |

---

## Deploy на Render / Railway

### Render

1. Создайте **Web Service** → выберите репозиторий
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `python bot.py`
4. Добавьте переменные окружения из `.env`
5. Для сохранения базы данных — добавьте **Disk** (mount path: `/data`) и укажите `DATABASE_URL=/data/exam_bot.db`

### Railway

```bash
railway login
railway init
railway up
```

Добавьте переменные окружения в Railway Dashboard.

---

## Безопасность

- Доступ только по белому списку Telegram ID
- Проверка статуса блокировки и срока доступа при каждом запросе
- Rate limiter (in-memory) против флуда
- Ограничение количества попыток в сутки
- Логирование всех действий в SQLite
- Изоляция admin-команд по списку `ADMIN_IDS`
