"""会话数据访问。"""
from semikb.dao.db_pool import DbPool


class SessionDao:
    def __init__(self):
        self._pool = DbPool.instance()

    def create(self, visitor_name: str) -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "INSERT INTO t_session (visitor_name, status) VALUES (%s, 'active')",
                (visitor_name,),
            )
            return int(cur.lastrowid)

    def get(self, session_id: int) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT id, visitor_name, status, turn_count, created_at, updated_at, last_active_at "
                "FROM t_session WHERE id=%s",
                (session_id,),
            )
            return cur.fetchone()

    def touch(self, session_id: int) -> None:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_session SET last_active_at=NOW(), updated_at=NOW() WHERE id=%s",
                (session_id,),
            )

    def close(self, session_id: int) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_session SET status='closed', updated_at=NOW(), last_active_at=NOW() WHERE id=%s",
                (session_id,),
            )
        return self.get(session_id)

    def increment_turn(self, session_id: int) -> None:
        with self._pool.cursor() as cur:
            cur.execute(
                "UPDATE t_session SET turn_count=turn_count+1, last_active_at=NOW(), updated_at=NOW() WHERE id=%s",
                (session_id,),
            )

    def list_with_first_bot(self, limit: int = 50) -> list[dict]:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT s.id AS session_id, s.visitor_name, s.status, s.turn_count, "
                "s.created_at, s.updated_at, s.last_active_at, "
                "(SELECT MIN(m.id) FROM t_message m "
                " WHERE m.session_id=s.id AND m.role='bot') AS conversation_id, "
                "(SELECT LEFT(m.content, 120) FROM t_message m "
                " WHERE m.session_id=s.id AND m.role='user' ORDER BY m.id ASC LIMIT 1) AS title, "
                "(SELECT LEFT(m.content, 180) FROM t_message m "
                " WHERE m.session_id=s.id AND m.role='bot' ORDER BY m.id ASC LIMIT 1) AS preview, "
                "(SELECT COUNT(*) FROM t_message m WHERE m.session_id=s.id) AS message_count "
                "FROM t_session s "
                "WHERE EXISTS (SELECT 1 FROM t_message m "
                "              WHERE m.session_id=s.id AND m.role='bot') "
                "ORDER BY s.last_active_at DESC, s.id DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()

    def count_with_first_bot(self) -> int:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM t_session s "
                "WHERE EXISTS (SELECT 1 FROM t_message m "
                "              WHERE m.session_id=s.id AND m.role='bot')"
            )
            row = cur.fetchone()
            return int(row["n"] if row else 0)
