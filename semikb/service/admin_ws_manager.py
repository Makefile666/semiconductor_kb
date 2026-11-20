"""管理端 WebSocket 广播。"""
import asyncio
import threading

from semikb.common.logger import get_logger

logger = get_logger(__name__)


class AdminWsManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.sockets: set = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self._ready = True

    @classmethod
    def instance(cls) -> "AdminWsManager":
        return cls()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, websocket) -> None:
        self.sockets.add(websocket)

    async def disconnect(self, websocket) -> None:
        self.sockets.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        if not self.sockets:
            return
        dead = []
        for ws in list(self.sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.sockets.discard(ws)

    def publish(self, payload: dict) -> None:
        if not self.loop or not self.sockets:
            return
        try:
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.broadcast(payload))
            )
        except Exception as e:
            logger.debug("管理端广播失败: %s", e)
