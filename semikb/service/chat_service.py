"""用户端问答会话服务。"""
import asyncio
import json
import time

from semikb.common.config import Config
from semikb.common.constants import SessionStatus
from semikb.common.exceptions import AppError, ConflictError, NotFoundError, ParamError, RateLimitError
from semikb.common.logger import get_logger
from semikb.common.utils import iso, snippet
from semikb.dao.citation_dao import CitationDao
from semikb.dao.message_dao import MessageDao
from semikb.dao.session_dao import SessionDao
from semikb.rag.runner import RAGRunner
from semikb.service.rate_limiter import RateLimiter

logger = get_logger(__name__)


class ChatService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.sessions = SessionDao()
        self.messages = MessageDao()
        self.citations = CitationDao()
        self.runner = RAGRunner()
        self.limiter = RateLimiter()
        self.semaphore = asyncio.Semaphore(
            int(self.config.get("rag.max_concurrent_questions", 8))
        )
        self._busy: set[int] = set()
        self._busy_lock = asyncio.Lock()
        self._ready = True

    # ---------------- 会话 ----------------

    def _session_payload(self, session: dict) -> dict:
        return {
            "id": int(session["id"]),
            "visitor_name": session.get("visitor_name") or "访客",
            "status": session.get("status"),
            "turn_count": int(session.get("turn_count") or 0),
            "created_at": iso(session.get("created_at")),
            "updated_at": iso(session.get("updated_at")),
            "last_active_at": iso(session.get("last_active_at")),
        }

    def _message_payload(self, row: dict, include_sources: bool = True) -> dict:
        sources = self.citations.list_by_message(int(row["id"])) if include_sources else []
        trace = None
        if row.get("trace_json"):
            try:
                trace = row["trace_json"]
                if isinstance(trace, str):
                    trace = json.loads(trace)
            except Exception:
                trace = None
        return {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "role": row["role"],
            "content": row["content"],
            "source": row.get("source"),
            "route": row.get("route"),
            "sources": sources,
            "trace": trace,
            "verified": bool(row.get("verified", 1)),
            "rating": row.get("rating"),
            "latency_ms": row.get("latency_ms"),
            "created_at": iso(row.get("created_at")),
        }

    def _conversation_payload(self, row: dict) -> dict:
        return {
            "conversation_id": int(row["conversation_id"]),
            "session_id": int(row["session_id"]),
            "visitor_name": row.get("visitor_name") or "访客",
            "status": row.get("status"),
            "turn_count": int(row.get("turn_count") or 0),
            "title": snippet(row.get("title") or "", 48) or "未命名对话",
            "preview": snippet(row.get("preview") or "", 120),
            "message_count": int(row.get("message_count") or 0),
            "created_at": iso(row.get("created_at")),
            "updated_at": iso(row.get("updated_at")),
            "last_active_at": iso(row.get("last_active_at")),
        }

    def list_sessions(self, limit: int = 50) -> dict:
        rows = self.sessions.list_with_first_bot(limit)
        return {
            "items": [self._conversation_payload(row) for row in rows],
            "total": self.sessions.count_with_first_bot(),
            "limit": limit,
        }

    def create_session(self, visitor_name: str | None, ip: str) -> dict:
        allowed, retry = self.limiter.allow(
            f"session-create:{ip}",
            int(self.config.get("rate_limit.chat_per_minute", 20)),
            60,
        )
        if not allowed:
            raise RateLimitError("创建会话过于频繁，请稍后再试", retry)
        name = (visitor_name or "访客").strip()[:32] or "访客"
        session_id = self.sessions.create(name)
        session = self.sessions.get(session_id)
        return {
            "session": self._session_payload(session),
            "suggestions": self.config.get("rag.suggestions", []),
            "welcome": "你好，我是芯知。可以问我半导体工艺、设备、材料与封装测试相关的问题，我会在回答里标注引用的文档。",
        }

    def get_session(self, session_id: int) -> dict:
        session = self.sessions.get(int(session_id))
        if not session:
            raise NotFoundError("会话不存在")
        return session

    def history(self, session_id: int, limit: int = 30) -> dict:
        session = self.get_session(session_id)
        rows = self.messages.list_by_session(int(session_id), limit)
        return {
            "session": self._session_payload(session),
            "messages": [self._message_payload(row) for row in rows],
        }

    def close_session(self, session_id: int) -> dict:
        session = self.get_session(session_id)
        if session.get("status") == SessionStatus.CLOSED:
            return self._session_payload(session)
        session = self.sessions.close(int(session_id))
        return self._session_payload(session)

    def rate_message(self, message_id: int, rating: int) -> dict:
        row = self.messages.get(message_id)
        if not row:
            raise NotFoundError("消息不存在")
        if row["role"] != "bot":
            raise ParamError("只能评价助手消息")
        changed = self.messages.rate(message_id, rating)
        if not changed:
            raise ParamError("评价失败")
        return {"message_id": message_id, "rating": rating}

    def _recent_history(self, session_id: int, before_id: int | None = None) -> list[dict]:
        rows = self.messages.list_by_session(session_id, 8)
        if before_id:
            rows = [row for row in rows if int(row["id"]) < before_id]
        return [
            {"role": "user" if row["role"] == "user" else "assistant", "content": row["content"]}
            for row in rows[-int(self.config.get("rag.history_turns", 3)) * 2:]
        ]

    # ---------------- 问答 ----------------

    async def handle_chat(self, session_id: int, websocket, content: str, debug: bool = True) -> None:
        question = (content or "").strip()
        if not question:
            raise ParamError("问题不能为空")
        if len(question) > 2000:
            raise ParamError("问题长度不能超过 2000 字")
        session = self.get_session(session_id)
        if session.get("status") != SessionStatus.ACTIVE:
            raise ConflictError("会话已关闭，请新建会话")
        allowed, retry = self.limiter.allow(
            f"chat:{session_id}",
            int(self.config.get("rate_limit.session_per_minute", 10)),
            60,
        )
        if not allowed:
            raise RateLimitError("提问过于频繁，请稍后再试", retry)
        async with self._busy_lock:
            if session_id in self._busy:
                raise ConflictError("上一条回答还在生成，请稍候")
            self._busy.add(session_id)
        acquired = False
        try:
            try:
                await asyncio.wait_for(self.semaphore.acquire(), timeout=3)
                acquired = True
            except asyncio.TimeoutError:
                raise RateLimitError("当前提问人数较多，请稍后再试", 3)

            history = self._recent_history(session_id)
            user_id = self.messages.add(
                session_id=session_id,
                role="user",
                content=question,
            )
            self.sessions.touch(session_id)
            user_row = self.messages.get(user_id)
            await websocket.send_json(
                {"type": "user_message", "message": self._message_payload(user_row)}
            )

            loop = asyncio.get_running_loop()
            disconnected = [False]

            def send_threadsafe(payload: dict) -> None:
                if disconnected[0]:
                    return
                try:
                    future = asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
                    future.result(timeout=8)
                except Exception:
                    disconnected[0] = True

            def emit_node(payload: dict) -> None:
                if debug:
                    send_threadsafe(payload)

            def emit_token(delta: str) -> None:
                send_threadsafe({"type": "chunk", "delta": delta})

            def run_graph():
                return self.runner.run(
                    question,
                    history=history,
                    debug=debug,
                    emit_node=emit_node,
                    emit_token=emit_token,
                )

            started = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, run_graph),
                    timeout=float(self.config.get("rag.wall_timeout_seconds", 90)) + 5,
                )
            except asyncio.TimeoutError:
                result = {
                    "answer": str(self.config.get("rag.fallback_message")),
                    "source": "fallback",
                    "route": "vectorstore",
                    "verified": False,
                    "terminated_by": "timeout",
                    "sources": [],
                    "trace": {
                        "nodes": [],
                        "route": "vectorstore",
                        "route_method": "",
                        "rewrite_count": 0,
                        "regenerate_count": 0,
                        "llm_calls": 0,
                        "latency_ms": int((time.perf_counter() - started) * 1000),
                        "terminated_by": "timeout",
                        "verified": False,
                    },
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }

            trace = result.get("trace") or {}
            bot_id = self.messages.add(
                session_id=session_id,
                role="bot",
                content=result.get("answer") or "",
                source=result.get("source") if result.get("source") in {
                    "vectorstore", "web_search", "fallback", "extractive", "direct"
                } else "fallback",
                route=result.get("route"),
                rewrite_count=int(trace.get("rewrite_count", 0) or 0),
                regenerate_count=int(trace.get("regenerate_count", 0) or 0),
                llm_calls=int(trace.get("llm_calls", 0) or 0),
                latency_ms=int(result.get("latency_ms", 0) or 0),
                verified=bool(result.get("verified")),
                trace=trace,
            )
            self.citations.add_many(bot_id, result.get("sources") or [])
            self.sessions.increment_turn(session_id)
            bot_row = self.messages.get(bot_id)
            await websocket.send_json(
                {
                    "type": "message_end",
                    "message": self._message_payload(bot_row),
                }
            )
            await websocket.send_json(
                {
                    "type": "session_status",
                    "session": self._session_payload(self.sessions.get(session_id)),
                }
            )
        finally:
            if acquired:
                self.semaphore.release()
            async with self._busy_lock:
                self._busy.discard(session_id)
