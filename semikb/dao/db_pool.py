"""MySQL 连接池，沿用 ai_service 的 DBUtils + DictCursor 方案。"""
import threading
from contextlib import contextmanager

import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor

from semikb.common.config import Config
from semikb.common.logger import get_logger


class DbPool:
    _instance = None
    _config: dict | None = None
    _init_lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_config: dict | None = None):
        if getattr(self, "_ready", False):
            return
        if db_config is not None:
            DbPool._config = db_config
        if DbPool._config is None:
            DbPool._config = Config.instance().db_config()
        with DbPool._init_lock:
            if getattr(self, "_ready", False):
                return
            self._logger = get_logger(__name__)
            self._pool = PooledDB(
                creator=pymysql,
                maxconnections=int(DbPool._config.get("pool_max", 10)),
                mincached=int(DbPool._config.get("pool_min", 2)),
                maxcached=int(DbPool._config.get("pool_max", 10)),
                blocking=True,
                host=DbPool._config.get("host"),
                port=int(DbPool._config.get("port", 3306)),
                user=DbPool._config.get("user"),
                password=DbPool._config.get("password"),
                database=DbPool._config.get("db"),
                charset=DbPool._config.get("charset", "utf8mb4"),
                cursorclass=DictCursor,
                autocommit=False,
            )
            self._ready = True
            self._logger.info(
                "数据库连接池初始化成功: %s:%s/%s",
                DbPool._config.get("host"),
                DbPool._config.get("port"),
                DbPool._config.get("db"),
            )

    @classmethod
    def instance(cls, db_config: dict | None = None) -> "DbPool":
        return cls(db_config)

    @contextmanager
    def cursor(self):
        conn = self._pool.connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def close(self) -> None:
        if getattr(self, "_ready", False):
            self._pool.close()
            self._ready = False
