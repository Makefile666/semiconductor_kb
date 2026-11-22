"""启动前环境自检。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semikb.common.config import Config
from semikb.dao.db_pool import DbPool
from semikb.ingest.milvus_store import MilvusStore
from semikb.rag.llm import LLMFactory


def line(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {name:<18} {detail}")


def main() -> int:
    config = Config.instance()
    failures = 0
    print("芯知 SemiKB preflight\n")
    line("config", True, str(config.get("database.db")))
    db = config.db_config()
    line("db password", bool(db.get("password")), "已从环境变量注入")
    try:
        with DbPool.instance().cursor() as cur:
            cur.execute("SELECT VERSION()")
            version = cur.fetchone()["VERSION()"]
        line("mysql", True, f"{db.get('host')}:{db.get('port')} version={version}")
    except Exception as e:
        failures += 1
        line("mysql", False, str(e)[:160])
    try:
        store = MilvusStore()
        health = store.health()
        line("milvus", health.get("status") == "up", f"version={health.get('version')} alias={store.alias}")
        aliases = store.client.list_aliases(collection_name=store.active_collection)
        if isinstance(aliases, dict):
            aliases = aliases.get("aliases", [])
        alias_ok = store.alias in aliases
        line("milvus alias", alias_ok, f"{store.active_collection} aliases={aliases}")
        if not alias_ok:
            failures += 1
    except Exception as e:
        failures += 1
        line("milvus", False, str(e)[:160])
    key = os.getenv("DASHSCOPE_API_KEY")
    line("dashscope key", bool(key), "已配置" if key else "未配置")
    if key:
        try:
            vector = LLMFactory.embedding().embed_query("半导体工艺")
            line("embedding", len(vector) == 1024, f"dim={len(vector)}")
        except Exception as e:
            failures += 1
            line("embedding", False, str(e)[:160])
    line("tavily key", bool(os.getenv("TAVILY_API_KEY")), "联网兜底可用")
    print(f"\n结果: {'PASS' if failures == 0 else 'FAIL'}，失败项 {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
