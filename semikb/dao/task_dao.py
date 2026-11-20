"""入库任务数据访问。"""
from semikb.dao.db_pool import DbPool


class TaskDao:
    UPDATABLE = {
        "status", "progress", "total_chunks", "done_chunks", "message", "finished_at", "doc_uid",
    }

    def __init__(self):
        self._pool = DbPool.instance()

    def create(self, task_type: str, doc_uid: str | None = None, status: str = "queued") -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "INSERT INTO t_ingest_task (task_type, doc_uid, status, message) "
                "VALUES (%s,%s,%s,%s)",
                (task_type, doc_uid, status, "已进入队列"),
            )
            return int(cur.lastrowid)

    def get(self, task_id: int) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute("SELECT * FROM t_ingest_task WHERE id=%s", (task_id,))
            return cur.fetchone()

    def update(self, task_id: int, fields: dict | None = None, **kwargs) -> None:
        merged = dict(fields or {})
        merged.update(kwargs)
        clean = {k: v for k, v in merged.items() if k in self.UPDATABLE}
        if not clean:
            return
        assignments = ", ".join(f"{key}=%s" for key in clean)
        values = list(clean.values()) + [task_id]
        with self._pool.cursor() as cur:
            cur.execute(
                f"UPDATE t_ingest_task SET {assignments} WHERE id=%s",
                tuple(values),
            )

    def list(self, page: int, size: int, status: str | None = None) -> tuple[list[dict], int]:
        where = []
        params: list = []
        if status:
            where.append("status=%s")
            params.append(status)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with self._pool.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM t_ingest_task {clause}", tuple(params))
            total = int(cur.fetchone()["n"])
            offset = (page - 1) * size
            cur.execute(
                f"SELECT * FROM t_ingest_task {clause} ORDER BY id DESC LIMIT %s OFFSET %s",
                tuple(params + [size, offset]),
            )
            return cur.fetchall(), total

    def active_for_doc(self, doc_uid: str, task_types: tuple[str, ...] | None = None) -> dict | None:
        types = task_types or ("upload", "reindex", "delete", "rebuild")
        placeholders = ",".join(["%s"] * len(types))
        with self._pool.cursor() as cur:
            cur.execute(
                f"SELECT * FROM t_ingest_task WHERE doc_uid=%s AND task_type IN ({placeholders}) "
                f"AND status IN ('queued','running') ORDER BY id DESC LIMIT 1",
                (doc_uid, *types),
            )
            return cur.fetchone()

    def active_rebuild(self) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT * FROM t_ingest_task WHERE task_type='rebuild' "
                "AND status IN ('queued','running') ORDER BY id DESC LIMIT 1"
            )
            return cur.fetchone()

    def pending_count(self) -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM t_ingest_task WHERE status IN ('queued','running')"
            )
            return int(cur.fetchone()["n"])

    def recover_stale(self) -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_ingest_task SET status='failed', finished_at=NOW(), "
                "message='服务重启，任务中断' WHERE status IN ('queued','running')"
            )
            return cur.rowcount
