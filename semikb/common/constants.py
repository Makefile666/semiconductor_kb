"""常量与枚举。"""
from enum import StrEnum


class SessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class MessageRole(StrEnum):
    USER = "user"
    BOT = "bot"


class MessageSource(StrEnum):
    VECTORSTORE = "vectorstore"
    WEB_SEARCH = "web_search"
    FALLBACK = "fallback"
    EXTRACTIVE = "extractive"


class Route(StrEnum):
    VECTORSTORE = "vectorstore"
    WEB_SEARCH = "web_search"


class DocStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class TaskType(StrEnum):
    UPLOAD = "upload"
    REINDEX = "reindex"
    DELETE = "delete"
    REBUILD = "rebuild"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WsType(StrEnum):
    READY = "ready"
    CHAT = "chat"
    PING = "ping"
    PONG = "pong"
    USER_MESSAGE = "user_message"
    NODE = "node"
    CHUNK = "chunk"
    MESSAGE_END = "message_end"
    SESSION_STATUS = "session_status"
    ERROR = "error"
    HELLO = "hello"
    TASK_UPDATE = "task_update"
    DOCUMENT_UPDATE = "document_update"
    STATS_TICK = "stats_tick"
