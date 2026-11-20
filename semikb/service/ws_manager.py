"""用户端连接计数。"""
import threading


class ChatWsManager:
    def __init__(self):
        self._count = 0
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            self._count += 1

    def disconnect(self) -> None:
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        with self._lock:
            return self._count
