"""Pydantic 请求模型与统一响应。"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "ok"
    data: Any = None


class CreateSessionRequest(BaseModel):
    visitor_name: str | None = Field(default=None, max_length=32)


class RateRequest(BaseModel):
    rating: Literal[1, -1]


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)


class RetrievalTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    expr: str | None = Field(default=None, max_length=500)


class QaTestRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    debug: bool = False


class RebuildRequest(BaseModel):
    scope: Literal["all"] = "all"
