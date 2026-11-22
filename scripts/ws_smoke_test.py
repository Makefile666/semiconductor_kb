"""端到端 WebSocket 冒烟测试。

用法:
    python scripts/ws_smoke_test.py
"""
import json
import urllib.request

from websockets.sync.client import connect

BASE = "http://127.0.0.1:8010"


def post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    created = post("/api/chat/sessions", {"visitor_name": "联调测试"})
    session = created["data"]["session"]
    session_id = session["id"]
    print(f"session={session_id} status={session['status']}")

    uri = f"ws://127.0.0.1:8010/api/chat/ws/{session_id}?debug=1"
    node_events = 0
    chunks = 0
    final = None
    with connect(uri, open_timeout=10, close_timeout=5) as ws:
        ready = json.loads(ws.recv(timeout=10))
        print(f"ready type={ready['type']} status={ready.get('session', {}).get('status')}")
        ws.send(json.dumps({"type": "chat", "content": "高介电常数金属栅技术如何降低漏电流？"}))
        while True:
            event = json.loads(ws.recv(timeout=120))
            event_type = event.get("type")
            if event_type == "node":
                node_events += 1
            elif event_type == "chunk":
                chunks += 1
            elif event_type == "message_end":
                final = event["message"]
                print(
                    "message_end "
                    f"verified={final['verified']} source={final['source']} "
                    f"latency={final['latency_ms']} citations={len(final['sources'])}"
                )
                print("answer=" + final["content"][:120].replace("\n", " "))
                break
            elif event_type == "error":
                raise RuntimeError(event)
        ws.send(json.dumps({"type": "ping"}))
        pong = json.loads(ws.recv(timeout=10))
        print(f"pong type={pong['type']}")

    history = get(f"/api/chat/sessions/{session_id}/messages?limit=10")
    messages = history["data"]["messages"]
    print(f"history messages={len(messages)} node_events={node_events} chunks={chunks}")
    assert len(messages) >= 2, "会话历史缺少用户或助手消息"
    assert final and final["content"], "回答为空"
    print("WS_SMOKE_OK")


if __name__ == "__main__":
    main()
