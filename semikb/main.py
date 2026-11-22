"""FastAPI 应用装配。"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from semikb.api import admin, chat, chat_ws, health, pages
from semikb.api import admin_ws
from semikb.common.config import Config, PROJECT_ROOT
from semikb.common.exceptions import AppError, RateLimitError
from semikb.common.logger import get_logger, setup_logging
from semikb.dao.db_pool import DbPool
from semikb.dao.task_dao import TaskDao
from semikb.ingest.milvus_store import MilvusStore
from semikb.service.admin_ws_manager import AdminWsManager

config = Config.instance()
setup_logging(config)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("芯知 SemiKB 启动")
    try:
        DbPool.instance()
        recover = TaskDao().recover_stale()
        if recover:
            logger.warning("恢复中断任务: %s 个", recover)
    except Exception:
        logger.exception("数据库初始化失败")
    try:
        MilvusStore().ensure_collection()
        logger.info("Milvus 集合就绪: %s", MilvusStore().active_collection)
    except Exception:
        logger.exception("Milvus 初始化失败，健康检查会显示 degraded")
    AdminWsManager.instance().set_loop(asyncio.get_running_loop())
    yield
    logger.info("芯知 SemiKB 停止")


app = FastAPI(
    title="芯知 SemiKB API",
    description="基于 RAG 的半导体文档知识库系统",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:8010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(chat_ws.router)
app.include_router(admin.router)
app.include_router(admin_ws.router)
app.include_router(pages.router)

static_dir = PROJECT_ROOT / "semikb" / "static"
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(max(1, int(exc.retry_after)))
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message, "data": exc.data},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "参数校验失败"
    if errors:
        first = errors[0]
        message = f"{'.'.join(str(x) for x in first.get('loc', []))}: {first.get('msg', message)}"
    return JSONResponse(
        status_code=400,
        content={"code": 400, "message": message, "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务内部错误", "data": None},
    )
