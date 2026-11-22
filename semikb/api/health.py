"""元信息与健康检查。"""
from fastapi import APIRouter

from semikb.common.config import Config
from semikb.service.health_service import HealthService

router = APIRouter(tags=["meta"])


@router.get("/api/meta")
def meta():
    cfg = Config.instance()
    return {
        "code": 200,
        "message": "ok",
        "data": {
            "brand": cfg.section("brand"),
            "suggestions": cfg.get("rag.suggestions", []),
            "max_question_chars": 2000,
            "version": "1.1.0",
        },
    }


@router.get("/api/health")
def health():
    return {"code": 200, "message": "ok", "data": HealthService.public()}
