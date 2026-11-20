"""文档元数据数据访问。"""
from __future__ import annotations

from semikb.dao.db_pool import DbPool


class DocumentDao:
    _UPDATABLE = {
        "filename", "title", "source_path", "size_bytes", "chunk_count",
        "status", "milvus_collection", "error_msg", "indexed_at",
    }

    def __init__(self):
        self._pool = DbPool.instance()

    def create(
        self,
        doc_uid: str,
        filename: str,
        title: str | None,
        source_path: str,
        file_hash: str,
        size_bytes: int,
        milvus_collection: str,
        status: str = "pending",
    ) -> None:
        with self._pool.cursor() as cur:
            cur.execute(
                "INSERT INTO t_document "
                "(doc_uid, filename, title, source_path, file_hash, size_bytes, "
                "status, milvus_collection) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    doc_uid, filename, title, source_path, file_hash, size_bytes,
                    status, milvus_collection,
                ),
            )

    def get(self, doc_uid: str) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute("SELECT * FROM t_document WHERE doc_uid=%s", (doc_uid,))
            return cur.fetchone()

    def get_by_hash(self, file_hash: str) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute("SELECT * FROM t_document WHERE file_hash=%s", (file_hash,))
            return cur.fetchone()

    def update_fields(self, doc_uid: str, fields: dict | None = None, **kwargs) -> None:
        merged = dict(fields or {})
        merged.update(kwargs)
        clean = {k: v for k, v in merged.items() if k in self._UPDATABLE}
        if not clean:
            return
        assignments = ", ".join(f"{key}=%s" for key in clean)
        values = list(clean.values()) + [doc_uid]
        with self._pool.cursor() as cur:
            cur.execute(
                f"UPDATE t_document SET {assignments}, updated_at=NOW() WHERE doc_uid=%s",
                tuple(values),
            )

    def list(
        self,
        page: int,
        size: int,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[dict], int]:
        where = ["status <> 'deleted'"]
        params: list = []
        if status:
            where.append("status=%s")
            params.append(status)
        if keyword:
            where.append("(filename LIKE %s OR title LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        clause = " AND ".join(where)
        with self._pool.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM t_document WHERE {clause}", tuple(params))
            total = int(cur.fetchone()["n"])
            offset = (page - 1) * size
            cur.execute(
                f"SELECT * FROM t_document WHERE {clause} "
                f"ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                tuple(params + [size, offset]),
            )
            return cur.fetchall(), total

    def list_ready(self) -> list[dict]:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT * FROM t_document WHERE status='ready' ORDER BY id ASC"
            )
            return cur.fetchall()

    def stats(self) -> dict:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(status='ready') AS ready, "
                "SUM(status='failed') AS failed, "
                "SUM(chunk_count) AS chunks "
                "FROM t_document WHERE status <> 'deleted'"
            )
            row = cur.fetchone()
        return {
            "total": int(row.get("total") or 0),
            "ready": int(row.get("ready") or 0),
            "failed": int(row.get("failed") or 0),
            "chunks": int(row.get("chunks") or 0),
        }

    def set_all_collection(self, collection: str) -> None:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_document SET milvus_collection=%s "
                "WHERE status IN ('ready','parsing','indexing')",
                (collection,),
            )

    def mark_deleted(self, doc_uid: str) -> None:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_document SET status='deleted', updated_at=NOW() WHERE doc_uid=%s",
                (doc_uid,),
            )
