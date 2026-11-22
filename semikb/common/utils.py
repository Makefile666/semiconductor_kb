"""通用工具。"""
import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path


def new_uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now()


def iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + "+08:00"
    return str(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_filename(name: str) -> str:
    base = Path(name or "document.md").name
    base = re.sub(r"[^\w\u4e00-\u9fff.\-]+", "_", base)
    base = base.strip("._") or "document.md"
    return base[:180]


def snippet(text: str, limit: int = 512) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:limit]


def keyword_overlap(question: str, text: str) -> int:
    q = question.lower()
    t = (text or "").lower()
    tokens = [x for x in re.split(r"[^\w\u4e00-\u9fff]+", q) if len(x) >= 2]
    if not tokens:
        tokens = [q]
    return sum(1 for token in tokens if token in t)


def parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
