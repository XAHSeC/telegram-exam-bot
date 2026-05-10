def format_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}ч {m}мин {s}сек"
    if m:
        return f"{m}мин {s}сек"
    return f"{s}сек"


def get_grade(percent: float) -> str:
    if percent >= 90:
        return "🏆 Отлично"
    if percent >= 75:
        return "⭐ Хорошо"
    if percent >= 60:
        return "✅ Удовлетворительно"
    return "❌ Не сдан"


def get_grade_emoji(passed: bool) -> str:
    return "✅" if passed else "❌"


def progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(length * current / total) if total else 0
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {current}/{total}"


def truncate(text: str, max_len: int = 200) -> str:
    return text[:max_len] + "…" if len(text) > max_len else text
