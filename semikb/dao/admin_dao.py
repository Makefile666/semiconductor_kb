"""管理员数据访问。"""
from semikb.dao.db_pool import DbPool


class AdminDao:
    def __init__(self):
        self._pool = DbPool.instance()

    def get_by_username(self, username: str) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, salt, display_name, created_at "
                "FROM t_admin WHERE username=%s",
                (username,),
            )
            return cur.fetchone()

    def get_by_id(self, admin_id: int) -> dict | None:
        with self._pool.cursor() as cur:
            cur.execute(
                "SELECT id, username, display_name, created_at FROM t_admin WHERE id=%s",
                (admin_id,),
            )
            return cur.fetchone()
