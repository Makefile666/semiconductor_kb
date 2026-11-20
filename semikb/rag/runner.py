"""RAG 运行器：封装 LangGraph 调用、事件回调与最终结果。"""
import time

from semikb.common.config import Config
from semikb.common.logger import get_logger
from semikb.rag import runtime
from semikb.rag.graph import build_graph

logger = get_logger(__name__)


class RAGRunner:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.graph = build_graph()
        self._ready = True

    def run(
        self,
        question: str,
        history: list[dict] | None = None,
        debug: bool = True,
        emit_node=None,
        emit_token=None,
    ) -> dict:
        started = time.perf_counter()
        runtime.configure(emit_node=emit_node, emit_token=emit_token)
        inputs = {
            "question": question,
            "original_question": question,
            "generation": "",
            "transform_count": 0,
            "generation_count": 0,
            "documents": [],
            "history": history or [],
            "trace_nodes": [],
            "verified": False,
            "route": "vectorstore",
            "route_method": "keyword",
            "source": "vectorstore",
        }
        try:
            final = self.graph.invoke(
                inputs,
                config={"recursion_limit": int(self.config.get("rag.recursion_limit", 20))},
            )
        except Exception as e:
            logger.exception("RAG 图执行失败: %s", e)
            final = dict(inputs)
            final["generation"] = str(self.config.get("rag.fallback_message"))
            final["source"] = "fallback"
            final["verified"] = False
            final["terminated_by"] = "graph_error"
            final["trace_nodes"] = list(inputs.get("trace_nodes", []))
            final["error"] = str(e)[:300]
        finally:
            calls = runtime.llm_calls()
            runtime.reset()

        docs = final.get("documents") or []
        sources = []
        for index, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            doc_uid = meta.get("doc_uid") or None
            url = f"/document/{doc_uid}" if doc_uid else (meta.get("url") or None)
            sources.append(
                {
                    "index": index,
                    "doc_uid": doc_uid,
                    "chunk_index": meta.get("chunk_index"),
                    "title": meta.get("title") or meta.get("filename") or "未命名文档",
                    "filename": meta.get("filename") or "",
                    "url": url,
                    "score": meta.get("score"),
                    "snippet": (doc.page_content or "")[:512],
                }
            )

        generation = final.get("generation") or ""
        source = final.get("source") or final.get("route") or "vectorstore"
        if source == "web_search" and not final.get("verified"):
            source = "web_search"
        if final.get("terminated_by") == "no_result":
            source = "fallback"
        if not generation.strip():
            generation = str(self.config.get("rag.fallback_message"))
            source = "fallback"
            final["verified"] = False
            final["terminated_by"] = final.get("terminated_by") or "empty_generation"

        elapsed = int((time.perf_counter() - started) * 1000)
        trace_nodes = final.get("trace_nodes", [])
        if not debug:
            trace_nodes = [
                {"node": n.get("node"), "elapsed_ms": n.get("elapsed_ms"), "detail": {}}
                for n in trace_nodes
            ]
        return {
            "answer": generation,
            "source": source,
            "route": final.get("route") or "vectorstore",
            "verified": bool(final.get("verified")),
            "terminated_by": final.get("terminated_by") or "unknown",
            "sources": sources,
            "trace": {
                "nodes": trace_nodes,
                "route": final.get("route") or "vectorstore",
                "route_method": final.get("route_method") or "",
                "rewrite_count": int(final.get("transform_count", 0) or 0),
                "regenerate_count": max(0, int(final.get("generation_count", 0) or 0) - 1),
                "llm_calls": calls,
                "latency_ms": elapsed,
                "terminated_by": final.get("terminated_by") or "unknown",
                "verified": bool(final.get("verified")),
                "error": final.get("error"),
            },
            "latency_ms": elapsed,
        }
