import time
from collections import defaultdict
from config import config


class RateLimiter:
    def __init__(self):
        self._windows: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        window = config.RATE_LIMIT_WINDOW_SECONDS
        self._windows[user_id] = [
            t for t in self._windows[user_id] if now - t < window
        ]
        if len(self._windows[user_id]) >= config.RATE_LIMIT_MESSAGES:
            return False
        self._windows[user_id].append(now)
        return True

    def reset(self, user_id: int) -> None:
        self._windows.pop(user_id, None)


rate_limiter = RateLimiter()
