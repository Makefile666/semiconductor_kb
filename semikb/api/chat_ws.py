"""用户端 WebSocket。"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from semikb.common.exceptions import AppError
from semikb.common.logger import get_logger
from semikb.service.chat_service import ChatService
from semikb.service.ws_manager import ChatWsManager

router = APIRouter(tags=["chat-ws"])
logger = get_logger(__name__)
service = ChatService()
manager = ChatWsManager()


@router.websocket("/api/chat/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: int, debug: bool = True):
    await websocket.accept()
    manager.connect()
    try:
        session = service.get_session(session_id)
        await websocket.send_json(
            {"type": "ready", "session": service._session_payload(session)}
        )
        while True:
            try:
                payload = await websocket.receive_json()
            except Exception:
                break
            msg_type = payload.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if msg_type != "chat":
                await websocket.send_json(
                    {"type": "error", "code": 400, "message": "未知消息类型", "data": None}
                )
                continue
            content = str(payload.get("content") or "")
            try:
                await service.handle_chat(session_id, websocket, content, debug=debug)
            except AppError as e:
                await websocket.send_json(
                    {"type": "error", "code": e.code, "message": e.message, "data": e.data}
                )
            except Exception:
                logger.exception("WebSocket 问答失败")
                await websocket.send_json(
                    {"type": "error", "code": 500, "message": "服务内部错误，请稍后重试", "data": None}
                )
    except WebSocketDisconnect:
        pass
    except AppError as e:
        try:
            await websocket.send_json(
                {"type": "error", "code": e.code, "message": e.message, "data": e.data}
            )
            await websocket.close(code=1008)
        except Exception:
            pass
    except Exception:
        logger.exception("WebSocket 连接异常")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        manager.disconnect()
