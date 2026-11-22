"""管理员认证：PBKDF 风格的口令哈希 + HMAC 签名令牌。"""
import base64
import hashlib
import hmac
import json
import os
import threading
import time

from semikb.common.config import Config
from semikb.common.constants import MessageRole
from semikb.common.exceptions import AuthError
from semikb.dao.admin_dao import AdminDao


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class AuthService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.admin_dao = AdminDao()
        self.secret = os.getenv(
            str(self.config.get("admin.token_secret_env", "SEMIKB_ADMIN_SECRET")),
            str(self.config.get("admin.token_secret", "semi-kb-dev-secret")),
        ).encode("utf-8")
        self.ttl_seconds = int(self.config.get("admin.token_ttl_hours", 8)) * 3600
        self._blacklist: dict[str, float] = {}
        self._lock = threading.RLock()
        self._ready = True

    def _hash(self, password: str, salt: str) -> str:
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def login(self, username: str, password: str) -> dict:
        admin = self.admin_dao.get_by_username(username)
        if not admin:
            raise AuthError("用户名或密码错误")
        expected = self._hash(password, admin["salt"])
        if not hmac.compare_digest(expected, admin["password_hash"]):
            raise AuthError("用户名或密码错误")
        now_ts = int(time.time())
        payload = {
            "sub": int(admin["id"]),
            "username": admin["username"],
            "iat": now_ts,
            "exp": now_ts + self.ttl_seconds,
        }
        body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64encode(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
        token = f"{body}.{signature}"
        return {
            "token": token,
            "admin": {
                "id": int(admin["id"]),
                "username": admin["username"],
                "display_name": admin["display_name"],
            },
            "expires_in": self.ttl_seconds,
        }

    def verify(self, token: str) -> dict:
        if not token:
            raise AuthError()
        with self._lock:
            if token in self._blacklist:
                raise AuthError("令牌已失效")
        try:
            body, signature = token.split(".", 1)
            expected = _b64encode(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, signature):
                raise AuthError()
            payload = json.loads(_b64decode(body))
        except AuthError:
            raise
        except Exception:
            raise AuthError()
        if int(payload.get("exp", 0)) < int(time.time()):
            raise AuthError("登录已过期，请重新登录")
        admin = self.admin_dao.get_by_id(int(payload.get("sub", 0)))
        if not admin:
            raise AuthError()
        return {
            "id": int(admin["id"]),
            "username": admin["username"],
            "display_name": admin["display_name"],
        }

    def logout(self, token: str) -> None:
        with self._lock:
            self._blacklist[token] = time.time() + self.ttl_seconds
        self._cleanup()

    def _cleanup(self) -> None:
        now_ts = time.time()
        with self._lock:
            expired = [token for token, until in self._blacklist.items() if until < now_ts]
            for token in expired:
                self._blacklist.pop(token, None)
