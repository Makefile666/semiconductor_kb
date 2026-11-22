"""管理端 WebSocket。"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from semikb.common.logger import get_logger
from semikb.service.admin_service import AdminService
from semikb.service.admin_ws_manager import AdminWsManager
from semikb.service.auth_service import AuthService

router = APIRouter(tags=["admin-ws"])
logger = get_logger(__name__)
service = AdminService()
manager = AdminWsManager()


@router.websocket("/api/admin/ws")
async def admin_websocket(websocket: WebSocket, token: str = ""):
    try:
        admin = AuthService().verify(token)
    except Exception:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await manager.connect(websocket)
    try:
        pending = service.tasks.pending_count()
        await websocket.send_json(
            {
                "type": "hello",
                "admin": admin,
                "pending_tasks": pending,
                "server_time": service.health()["time"],
            }
        )
        while True:
            text = await websocket.receive_text()
            if text.strip() in {"ping", "{\"type\":\"ping\"}"}:
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("管理端 WebSocket 异常")
    finally:
        await manager.disconnect(websocket)
