import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ])
    DATABASE_URL: str = os.getenv("DATABASE_URL", "exam_bot.db")

    EXAM_QUESTIONS_COUNT: int = int(os.getenv("EXAM_QUESTIONS_COUNT", "150"))
    EXAM_TIME_LIMIT_MINUTES: int = int(os.getenv("EXAM_TIME_LIMIT_MINUTES", "180"))
    MAX_DAILY_ATTEMPTS: int = int(os.getenv("MAX_DAILY_ATTEMPTS", "3"))

    RATE_LIMIT_MESSAGES: int = int(os.getenv("RATE_LIMIT_MESSAGES", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    PASS_THRESHOLD: float = float(os.getenv("PASS_THRESHOLD", "0.7"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")

    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "@admin")
    BOT_NAME: str = os.getenv("BOT_NAME", "Exam Bot")


config = Config()
