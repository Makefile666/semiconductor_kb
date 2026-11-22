"""RAG 节点运行期回调与计数。"""
from contextvars import ContextVar

_emitter: ContextVar = ContextVar("semikb_node_emitter", default=None)
_tokener: ContextVar = ContextVar("semikb_token_emitter", default=None)
_counter: ContextVar = ContextVar("semikb_llm_counter", default=None)


def configure(emit_node=None, emit_token=None) -> None:
    _emitter.set(emit_node)
    _tokener.set(emit_token)
    _counter.set([0])


def reset() -> None:
    _emitter.set(None)
    _tokener.set(None)
    _counter.set(None)


def emit_node(node: str, phase: str, elapsed_ms: int = 0, detail: dict | None = None) -> None:
    emitter = _emitter.get()
    if not emitter:
        return
    try:
        emitter(
            {
                "type": "node",
                "node": node,
                "phase": phase,
                "elapsed_ms": elapsed_ms,
                "detail": detail or {},
            }
        )
    except Exception:
        pass


def emit_token(delta: str) -> None:
    tokener = _tokener.get()
    if not tokener or not delta:
        return
    try:
        tokener(delta)
    except Exception:
        pass


def bump_llm() -> int:
    counter = _counter.get()
    if counter is None:
        return 0
    counter[0] += 1
    return counter[0]


def llm_calls() -> int:
    counter = _counter.get()
    return int(counter[0]) if counter else 0
