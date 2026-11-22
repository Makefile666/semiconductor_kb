"""滑动窗口限流。"""
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self):
        self._windows: dict[str, deque] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

    def allow(self, key: str, limit: int, window_seconds: float) -> tuple[bool, float]:
        now_ts = time.time()
        with self._lock:
            window = self._windows.setdefault(key, deque())
            cutoff = now_ts - window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                retry = max(0.2, window_seconds - (now_ts - window[0]))
                return False, retry
            window.append(now_ts)
            self._cleanup(now_ts)
            return True, 0.0

    def _cleanup(self, now_ts: float) -> None:
        if now_ts - self._last_cleanup < 300:
            return
        self._last_cleanup = now_ts
        stale = [key for key, window in self._windows.items() if not window or window[-1] < now_ts - 3600]
        for key in stale:
            self._windows.pop(key, None)
