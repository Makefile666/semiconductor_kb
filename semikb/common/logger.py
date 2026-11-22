"""统一日志。"""
import logging
from logging.handlers import RotatingFileHandler

from semikb.common.config import PROJECT_ROOT

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(threadName)-12s | %(name)s:%(lineno)d | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_initialized = False


def setup_logging(config) -> None:
    global _initialized
    if _initialized:
        return
    level_name = str(config.get("log.level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_dir = PROJECT_ROOT / str(config.get("log.dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    file_handler = RotatingFileHandler(
        log_dir / str(config.get("log.file", "server.log")),
        maxBytes=int(config.get("log.max_bytes", 10 * 1024 * 1024)),
        backupCount=int(config.get("log.backup_count", 5)),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
