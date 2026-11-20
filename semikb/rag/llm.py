"""大模型与嵌入客户端。"""
import os
import threading

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from semikb.common.config import Config
from semikb.common.exceptions import UnavailableError


class LLMFactory:
    _lock = threading.RLock()
    _chat = None
    _grader = None
    _embedding = None

    @classmethod
    def _cfg(cls, section: str) -> dict:
        return Config.instance().section(section)

    @classmethod
    def chat(cls) -> ChatOpenAI:
        with cls._lock:
            if cls._chat is None:
                cfg = cls._cfg("llm.chat")
                key = os.getenv(str(cfg.get("api_key_env", "DASHSCOPE_API_KEY")))
                if not key:
                    raise UnavailableError("未配置 DASHSCOPE_API_KEY，无法调用对话模型")
                cls._chat = ChatOpenAI(
                    model=str(cfg.get("model", "qwen-plus")),
                    api_key=key,
                    base_url=str(cfg.get("base_url")),
                    temperature=float(cfg.get("temperature", 0)),
                    max_tokens=int(cfg.get("max_tokens", 900)),
                    timeout=float(cfg.get("timeout_seconds", 45)),
                    streaming=bool(cfg.get("streaming", True)),
                    max_retries=int(cfg.get("max_retries", 2)),
                )
            return cls._chat

    @classmethod
    def grader(cls) -> ChatOpenAI:
        with cls._lock:
            if cls._grader is None:
                cfg = cls._cfg("llm.grader")
                key = os.getenv(str(cfg.get("api_key_env", "DASHSCOPE_API_KEY")))
                if not key:
                    raise UnavailableError("未配置 DASHSCOPE_API_KEY，无法调用评分模型")
                cls._grader = ChatOpenAI(
                    model=str(cfg.get("model", "qwen-turbo")),
                    api_key=key,
                    base_url=str(cfg.get("base_url")),
                    temperature=float(cfg.get("temperature", 0)),
                    max_tokens=int(cfg.get("max_tokens", 220)),
                    timeout=float(cfg.get("timeout_seconds", 30)),
                    streaming=False,
                    max_retries=int(cfg.get("max_retries", 2)),
                )
            return cls._grader

    @classmethod
    def embedding(cls) -> OpenAIEmbeddings:
        with cls._lock:
            if cls._embedding is None:
                cfg = cls._cfg("embedding")
                key = os.getenv(str(cfg.get("api_key_env", "DASHSCOPE_API_KEY")))
                if not key:
                    raise UnavailableError("未配置 DASHSCOPE_API_KEY，无法生成向量")
                cls._embedding = OpenAIEmbeddings(
                    model=str(cfg.get("model", "text-embedding-v4")),
                    api_key=key,
                    base_url=str(cfg.get("base_url")),
                    check_embedding_ctx_length=False,
                    chunk_size=int(cfg.get("batch", 10)),
                    dimensions=int(cfg.get("dim", 1024)),
                )
            return cls._embedding
