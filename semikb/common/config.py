"""全局配置：JSON 文件 + .env 环境变量。"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Config:
    _instance = None
    _loaded = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_file: str | Path | None = None):
        if Config._loaded:
            return
        self._path = Path(config_file) if config_file else PROJECT_ROOT / "config" / "config.json"
        with open(self._path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        Config._loaded = True

    @classmethod
    def instance(cls, config_file: str | Path | None = None) -> "Config":
        return cls(config_file)

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._loaded = False

    def get(self, key: str, default=None):
        node = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, key: str) -> dict:
        return self.get(key, {}) or {}

    def env(self, key: str, default=None):
        return os.getenv(key, default)

    def db_config(self) -> dict:
        db = dict(self.section("database"))
        env_name = db.get("password_env")
        if env_name and os.getenv(env_name) is not None:
            db["password"] = os.getenv(env_name)
        return db
