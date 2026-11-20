"""用户端 REST 接口。"""
from fastapi import APIRouter, Depends, Query, Request

from semikb.api.deps import client_ip, ok
from semikb.schema.models import CreateSessionRequest, RateRequest
from semikb.service.chat_service import ChatService
from semikb.service.rate_limiter import RateLimiter

router = APIRouter(prefix="/api/chat", tags=["chat"])
service = ChatService()
limiter = RateLimiter()


@router.post("/sessions")
def create_session(payload: CreateSessionRequest, request: Request):
    return ok(service.create_session(payload.visitor_name, client_ip(request)))


@router.get("/sessions")
def list_sessions(limit: int = Query(default=50, ge=1, le=100)):
    return ok(service.list_sessions(limit))


@router.get("/sessions/{session_id}")
def get_session(session_id: int):
    return ok(service._session_payload(service.get_session(session_id)))


@router.post("/sessions/{session_id}/close")
def close_session(session_id: int):
    return ok(service.close_session(session_id))


@router.get("/sessions/{session_id}/messages")
def history(session_id: int, limit: int = Query(default=30, ge=1, le=100)):
    return ok(service.history(session_id, limit))


@router.post("/messages/{message_id}/rate")
def rate_message(message_id: int, payload: RateRequest):
    return ok(service.rate_message(message_id, payload.rating))
