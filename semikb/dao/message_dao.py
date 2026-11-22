"""消息数据访问。"""
import json

from semikb.dao.db_pool import DbPool


class MessageDao:
    def __init__(self):
        self._pool = DbPool.instance()

    def add(
        self,
        session_id: int,
        role: str,
        content: str,
        source: str | None = None,
        route: str | None = None,
        rewrite_count: int = 0,
        regenerate_count: int = 0,
        llm_calls: int = 0,
        latency_ms: int | None = None,
        verified: bool = True,
        trace: dict | None = None,
    ) -> int:
        trace_json = json.dumps(trace, ensure_ascii=False) if trace is not None else None
        with self._pool.cursor() as cur:
            cur.execute(
                "INSERT INTO t_message "
                "(session_id, role, content, source, route, rewrite_count, regenerate_count, "
                "llm_calls, latency_ms, verified, trace_json) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    session_id,
                    role,
                    content,
                    source,
                    route,
                    int(rewrite_count or 0),
                    int(regenerate_count or 0),
                    int(llm_calls or 0),
                    latency_ms,
                    1 if verified else 0,
                    trace_json,
                ),
            )
            return int(cur.lastrowid)

    def get(self, message_id: int) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute("SELECT * FROM t_message WHERE id=%s", (message_id,))
            return cur.fetchone()

    def list_by_session(self, session_id: int, limit: int = 30) -> list[dict]:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT * FROM (SELECT * FROM t_message WHERE session_id=%s "
                "ORDER BY id DESC LIMIT %s) x ORDER BY id ASC",
                (session_id, limit),
            )
            return cur.fetchall()

    def rate(self, message_id: int, rating: int) -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_message SET rating=%s WHERE id=%s AND role='bot'",
                (rating, message_id),
            )
            return cur.rowcount

    def admin_list(
        self,
        page: int,
        size: int,
        session_id: int | None = None,
        role: str = "bot",
        source: str | None = None,
        days: int | None = None,
        keyword: str | None = None,
    ) -> tuple[list[dict], int]:
        where = ["role=%s"]
        params: list = [role]
        if session_id is not None:
            where.append("session_id=%s")
            params.append(session_id)
        if source:
            where.append("source=%s")
            params.append(source)
        if days:
            where.append("created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)")
            params.append(days)
        if keyword:
            where.append("content LIKE %s")
            params.append(f"%{keyword}%")
        clause = " AND ".join(where)
        with self._pool.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM t_message WHERE {clause}", tuple(params))
            total = int(cur.fetchone()["n"])
            offset = (page - 1) * size
            cur.execute(
                f"SELECT id, session_id, role, content, source, route, latency_ms, verified, "
                f"rating, created_at FROM t_message WHERE {clause} "
                f"ORDER BY id DESC LIMIT %s OFFSET %s",
                tuple(params + [size, offset]),
            )
            rows = cur.fetchall()
        return rows, total
