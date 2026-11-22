"""后台入库任务队列。"""
import threading
from concurrent.futures import ThreadPoolExecutor

from semikb.common.config import Config
from semikb.common.logger import get_logger

logger = get_logger(__name__)


class TaskQueue:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.pool = ThreadPoolExecutor(
            max_workers=int(self.config.get("ingest.max_workers", 2)),
            thread_name_prefix="semi-ingest",
        )
        self._ready = True

    def submit(self, fn, *args, **kwargs):
        future = self.pool.submit(fn, *args, **kwargs)
        future.add_done_callback(self._log_error)
        return future

    @staticmethod
    def _log_error(future):
        try:
            exc = future.exception()
        except Exception:
            return
        if exc:
            logger.error("后台任务异常: %s", exc)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=False)
