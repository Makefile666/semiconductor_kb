"""接口公共依赖。"""
from fastapi import Depends, Header, Request

from semikb.common.exceptions import AuthError
from semikb.service.auth_service import AuthService


def ok(data=None, message: str = "ok", code: int = 200) -> dict:
    return {"code": code, "message": message, "data": data}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None),
) -> str:
    if x_admin_token:
        return x_admin_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise AuthError()


def get_current_admin(token: str = Depends(get_admin_token)) -> dict:
    return AuthService().verify(token)
