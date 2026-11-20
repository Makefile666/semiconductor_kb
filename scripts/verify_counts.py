"""校验 MySQL 文档切片数与 Milvus 实际切片数。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semikb.dao.db_pool import DbPool
from semikb.ingest.milvus_store import MilvusStore


def main() -> None:
    store = MilvusStore()
    total = store.count_total(store.alias)
    print("milvus_stats_total", total)
    client = store.client
    rows = client.query(
        collection_name=store.alias,
        filter='doc_uid != ""',
        output_fields=["count(*)"],
    )
    count = int(list(rows[0].values())[0]) if rows else 0
    print("milvus_query_total", count)
    pool = DbPool.instance()
    with pool.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS docs, SUM(chunk_count) AS chunks FROM t_document WHERE status='ready'")
        print("mysql", cur.fetchone())
        cur.execute(
            "SELECT doc_uid, filename, chunk_count FROM t_document WHERE status='ready' ORDER BY id DESC LIMIT 5"
        )
        print("last", cur.fetchall())
    print("alias", store.alias, "active", store.active_collection)


if __name__ == "__main__":
    main()
