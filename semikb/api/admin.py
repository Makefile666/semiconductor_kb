"""管理端 REST 接口。"""
import asyncio

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from semikb.api.deps import client_ip, get_admin_token, get_current_admin, ok
from semikb.common.exceptions import RateLimitError
from semikb.schema.models import AdminLoginRequest, QaTestRequest, RebuildRequest, RetrievalTestRequest
from semikb.service.admin_service import AdminService
from semikb.service.rate_limiter import RateLimiter

router = APIRouter(prefix="/api/admin", tags=["admin"])
service = AdminService()
limiter = RateLimiter()


def _check(key: str, limit: int, window: float, message: str) -> None:
    allowed, retry = limiter.allow(key, limit, window)
    if not allowed:
        raise RateLimitError(message, retry)


@router.post("/login")
def login(payload: AdminLoginRequest, request: Request):
    _check(
        f"admin-login:{client_ip(request)}",
        int(service.config.get("rate_limit.admin_login_per_minute", 5)),
        60,
        "登录尝试过于频繁，请一分钟后再试",
    )
    return ok(service.login(payload.username, payload.password))


@router.post("/logout")
def logout(token: str = Depends(get_admin_token)):
    service.logout(token)
    return ok({"logged_out": True})


@router.get("/me")
def me(admin: dict = Depends(get_current_admin)):
    return ok(admin)


@router.get("/documents")
def documents(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    keyword: str | None = None,
    admin: dict = Depends(get_current_admin),
):
    return ok(service.list_documents(page, size, status, keyword))


@router.get("/documents/{doc_uid}")
def document_detail(doc_uid: str, admin: dict = Depends(get_current_admin)):
    return ok(service.document_detail(doc_uid))


@router.get("/documents/{doc_uid}/chunks")
def document_chunks(
    doc_uid: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(get_current_admin),
):
    return ok(service.chunks(doc_uid, limit, offset))


@router.post("/documents/upload", status_code=202)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    admin: dict = Depends(get_current_admin),
):
    _check(
        f"admin-upload:{admin['id']}",
        int(service.config.get("rate_limit.upload_per_hour", 30)),
        3600,
        "上传次数过多，请稍后再试",
    )
    uploads = []
    for file in files:
        data = await file.read()
        uploads.append((file.filename or "document.md", data))
    result = service.upload_documents(uploads)
    return ok(result, message="已进入入库队列", code=202)


@router.post("/documents/{doc_uid}/reindex", status_code=202)
def reindex_document(doc_uid: str, admin: dict = Depends(get_current_admin)):
    return ok(service.reindex_document(doc_uid), message="已进入重建索引队列", code=202)


@router.delete("/documents/{doc_uid}", status_code=202)
def delete_document(doc_uid: str, admin: dict = Depends(get_current_admin)):
    return ok(service.delete_document(doc_uid), message="已进入删除队列", code=202)


@router.get("/tasks")
def tasks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    admin: dict = Depends(get_current_admin),
):
    return ok(service.list_tasks(page, size, status))


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, admin: dict = Depends(get_current_admin)):
    return ok(service.task_detail(task_id))


@router.post("/rebuild", status_code=202)
def rebuild(payload: RebuildRequest, admin: dict = Depends(get_current_admin)):
    return ok(service.rebuild(), message="已进入全量重建队列", code=202)


@router.post("/retrieval-test")
async def retrieval_test(payload: RetrievalTestRequest, admin: dict = Depends(get_current_admin)):
    _check(
        f"admin-retrieval:{admin['id']}",
        int(service.config.get("rate_limit.retrieval_test_per_minute", 30)),
        60,
        "检索调试过于频繁",
    )
    result = await asyncio.to_thread(
        service.retrieval_test, payload.query, payload.top_k, payload.score_threshold, payload.expr
    )
    return ok(result)


@router.post("/qa-test")
async def qa_test(payload: QaTestRequest, admin: dict = Depends(get_current_admin)):
    _check(
        f"admin-qa:{admin['id']}",
        int(service.config.get("rate_limit.qa_test_per_minute", 10)),
        60,
        "问答测试过于频繁",
    )
    result = await asyncio.to_thread(service.qa_test, payload.question, payload.debug)
    return ok(result)


@router.get("/stats/overview")
def overview(
    days: int = Query(default=7, ge=1, le=30),
    admin: dict = Depends(get_current_admin),
):
    return ok(service.overview(days))


@router.get("/messages")
def messages(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session_id: int | None = None,
    source: str | None = None,
    days: int | None = Query(default=None, ge=1, le=30),
    keyword: str | None = None,
    admin: dict = Depends(get_current_admin),
):
    return ok(service.list_messages(page, size, session_id, source, days, keyword))


@router.get("/messages/{message_id}")
def message_detail(message_id: int, admin: dict = Depends(get_current_admin)):
    return ok(service.message_detail(message_id))


@router.get("/health")
def health(admin: dict = Depends(get_current_admin)):
    return ok(service.health())


@router.get("/config")
def config(admin: dict = Depends(get_current_admin)):
    return ok(service.public_config())
