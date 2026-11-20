"""健康检查与运行时信息。"""
import os
import time

from semikb.common.config import Config, PROJECT_ROOT
from semikb.common.utils import iso, now
from semikb.dao.db_pool import DbPool
from semikb.ingest.milvus_store import MilvusStore
from semikb.rag.llm import LLMFactory

_STARTED_AT = time.time()


class HealthService:
    _cache = None
    _cache_at = 0.0

    @classmethod
    def _db_health(cls) -> dict:
        started = time.perf_counter()
        try:
            with DbPool.instance().cursor() as cur:
                cur.execute("SELECT VERSION() AS version")
                row = cur.fetchone()
            return {
                "status": "up",
                "version": row.get("version"),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as e:
            return {"status": "down", "error": str(e)[:200]}

    @classmethod
    def _embedding_health(cls) -> dict:
        cfg = Config.instance().section("embedding")
        key = os.getenv(str(cfg.get("api_key_env", "DASHSCOPE_API_KEY")))
        if not key:
            return {"status": "down", "model": cfg.get("model"), "error": "API Key 未配置"}
        try:
            started = time.perf_counter()
            vector = LLMFactory.embedding().embed_query("半导体健康检查")
            return {
                "status": "up",
                "model": cfg.get("model"),
                "dim": len(vector),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as e:
            return {"status": "down", "model": cfg.get("model"), "error": str(e)[:200]}

    @classmethod
    def _llm_health(cls) -> dict:
        cfg = Config.instance().section("llm.chat")
        key = os.getenv(str(cfg.get("api_key_env", "DASHSCOPE_API_KEY")))
        return {
            "status": "up" if key else "down",
            "model": cfg.get("model"),
            "error": None if key else "API Key 未配置",
        }

    @classmethod
    def detailed(cls, use_cache: bool = True) -> dict:
        if use_cache and cls._cache and time.time() - cls._cache_at < 60:
            return cls._cache
        config = Config.instance()
        mysql = cls._db_health()
        milvus = MilvusStore().health()
        embedding = cls._embedding_health()
        llm = cls._llm_health()
        statuses = [mysql.get("status"), milvus.get("status")]
        overall = "ok" if all(x == "up" for x in statuses) else "degraded"
        if embedding.get("status") != "up" or llm.get("status") != "up":
            overall = "degraded"
        payload = {
            "status": overall,
            "time": iso(now()),
            "uptime_seconds": int(time.time() - _STARTED_AT),
            "components": {
                "mysql": mysql,
                "milvus": milvus,
                "embedding": embedding,
                "llm": llm,
            },
            "app": {
                "name": str(config.get("brand.name")),
                "version": "1.1.0",
                "project_root": str(PROJECT_ROOT),
            },
        }
        cls._cache = payload
        cls._cache_at = time.time()
        return payload

    @classmethod
    def public(cls) -> dict:
        detail = cls.detailed()
        return {
            "status": detail["status"],
            "time": detail["time"],
            "components": {key: value.get("status") for key, value in detail["components"].items()},
        }
