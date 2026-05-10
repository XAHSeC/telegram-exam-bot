"""
Run once to populate the database with sample questions.
Usage: python seed_questions.py
"""
import asyncio
from database.db import init_db, add_question

SAMPLE_QUESTIONS = [
    {
        "text": "Что такое IP-адрес?",
        "category": "Сети",
        "explanation": "IP-адрес — уникальный числовой идентификатор устройства в сети.",
        "answers": [
            {"text": "Уникальный идентификатор устройства в сети", "is_correct": True},
            {"text": "Тип процессора", "is_correct": False},
            {"text": "Операционная система", "is_correct": False},
            {"text": "Протокол шифрования", "is_correct": False},
        ],
    },
    {
        "text": "Какой протокол используется для безопасной передачи данных в вебе?",
        "category": "Безопасность",
        "explanation": "HTTPS — расширение HTTP с поддержкой шифрования SSL/TLS.",
        "answers": [
            {"text": "HTTP", "is_correct": False},
            {"text": "FTP", "is_correct": False},
            {"text": "HTTPS", "is_correct": True},
            {"text": "SMTP", "is_correct": False},
        ],
    },
    {
        "text": "Что означает аббревиатура DNS?",
        "category": "Сети",
        "explanation": "DNS — Domain Name System, система доменных имён.",
        "answers": [
            {"text": "Dynamic Network Service", "is_correct": False},
            {"text": "Domain Name System", "is_correct": True},
            {"text": "Data Navigation System", "is_correct": False},
            {"text": "Digital Network Standard", "is_correct": False},
        ],
    },
    {
        "text": "Какой порт использует протокол HTTP по умолчанию?",
        "category": "Сети",
        "explanation": "HTTP использует порт 80, HTTPS — порт 443.",
        "answers": [
            {"text": "443", "is_correct": False},
            {"text": "8080", "is_correct": False},
            {"text": "80", "is_correct": True},
            {"text": "21", "is_correct": False},
        ],
    },
    {
        "text": "Что такое брандмауэр (firewall)?",
        "category": "Безопасность",
        "explanation": "Брандмауэр — система для контроля входящего и исходящего сетевого трафика.",
        "answers": [
            {"text": "Антивирусная программа", "is_correct": False},
            {"text": "Система контроля сетевого трафика", "is_correct": True},
            {"text": "Тип базы данных", "is_correct": False},
            {"text": "Протокол шифрования", "is_correct": False},
        ],
    },
]


async def seed():
    await init_db()
    for q in SAMPLE_QUESTIONS:
        qid = await add_question(
            text=q["text"],
            category=q["category"],
            explanation=q["explanation"],
            image_path=None,
            answers=q["answers"],
        )
        print(f"Added question #{qid}: {q['text'][:50]}...")
    print(f"\n✅ Seeded {len(SAMPLE_QUESTIONS)} questions.")
    print("Add more via Excel import in the admin panel or expand this file.")


if __name__ == "__main__":
    asyncio.run(seed())
