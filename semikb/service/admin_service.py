"""管理台业务服务。"""
import hashlib
import os
import time
from pathlib import Path

from semikb.common.config import PROJECT_ROOT, Config
from semikb.common.constants import DocStatus, TaskStatus, TaskType
from semikb.common.exceptions import (
    ConflictError, NotFoundError, PayloadTooLargeError, UnsupportedMediaError, UnavailableError,
)
from semikb.common.logger import get_logger
from semikb.common.utils import iso, new_uid, now, safe_filename, snippet
from semikb.dao.citation_dao import CitationDao
from semikb.dao.document_dao import DocumentDao
from semikb.dao.message_dao import MessageDao
from semikb.dao.session_dao import SessionDao
from semikb.dao.task_dao import TaskDao
from semikb.ingest.milvus_store import MilvusStore
from semikb.ingest.pipeline import IngestPipeline
from semikb.ingest.task_queue import TaskQueue
from semikb.rag.retriever import KnowledgeRetriever
from semikb.rag.runner import RAGRunner
from semikb.service.auth_service import AuthService
from semikb.service.health_service import HealthService
from semikb.service.rate_limiter import RateLimiter
from semikb.service.stats_service import StatsService

logger = get_logger(__name__)
DOC_DIR = PROJECT_ROOT / "data" / "docs"


class AdminService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.auth = AuthService()
        self.documents = DocumentDao()
        self.tasks = TaskDao()
        self.messages = MessageDao()
        self.sessions = SessionDao()
        self.citations = CitationDao()
        self.store = MilvusStore()
        self.pipeline = IngestPipeline()
        self.queue = TaskQueue()
        self.runner = RAGRunner()
        self.limiter = RateLimiter()
        DOC_DIR.mkdir(parents=True, exist_ok=True)
        self._ready = True

    # ---------------- 认证 ----------------

    def login(self, username: str, password: str) -> dict:
        return self.auth.login(username, password)

    def logout(self, token: str) -> None:
        self.auth.logout(token)

    def me(self, token: str) -> dict:
        return self.auth.verify(token)

    # ---------------- 序列化 ----------------

    @staticmethod
    def _doc_payload(row: dict) -> dict:
        return {
            "doc_uid": row.get("doc_uid"),
            "filename": row.get("filename"),
            "title": row.get("title") or "",
            "size_bytes": int(row.get("size_bytes") or 0),
            "chunk_count": int(row.get("chunk_count") or 0),
            "status": row.get("status"),
            "milvus_collection": row.get("milvus_collection"),
            "error_msg": row.get("error_msg"),
            "created_at": iso(row.get("created_at")),
            "updated_at": iso(row.get("updated_at")),
            "indexed_at": iso(row.get("indexed_at")),
        }

    @staticmethod
    def _task_payload(row: dict) -> dict:
        return {
            "id": int(row.get("id")),
            "task_type": row.get("task_type"),
            "doc_uid": row.get("doc_uid"),
            "status": row.get("status"),
            "progress": int(row.get("progress") or 0),
            "total_chunks": int(row.get("total_chunks") or 0),
            "done_chunks": int(row.get("done_chunks") or 0),
            "message": row.get("message"),
            "created_at": iso(row.get("created_at")),
            "finished_at": iso(row.get("finished_at")),
        }

    # ---------------- 文档 ----------------

    def list_documents(self, page: int, size: int, status: str | None, keyword: str | None) -> dict:
        rows, total = self.documents.list(page, size, status, keyword)
        return {
            "items": [self._doc_payload(row) for row in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    def document_detail(self, doc_uid: str) -> dict:
        row = self.documents.get(doc_uid)
        if not row or row.get("status") == DocStatus.DELETED:
            raise NotFoundError("文档不存在")
        payload = self._doc_payload(row)
        try:
            chunks = self.store.query_chunks(doc_uid, row.get("milvus_collection"))
        except Exception:
            chunks = []
        payload["chunks_preview"] = [
            {
                "chunk_index": int(item.get("chunk_index") or 0),
                "title": item.get("title") or "",
                "text": snippet(item.get("text") or "", 240),
            }
            for item in chunks[:5]
        ]
        return payload

    def upload_documents(self, uploads: list[tuple[str, bytes]]) -> dict:
        max_files = int(self.config.get("ingest.max_files_per_upload", 20))
        if len(uploads) > max_files:
            raise ConflictError(f"一次最多上传 {max_files} 个文件")
        max_bytes = int(self.config.get("ingest.max_file_mb", 5)) * 1024 * 1024
        extensions = {str(x).lower() for x in self.config.get("ingest.extensions", [".md", ".markdown"])}
        seen_hashes: set[str] = set()
        accepted, rejected = [], []
        task_ids = []
        active_collection = self.store.active_collection
        for filename, data in uploads:
            safe = safe_filename(filename)
            lower = safe.lower()
            if not any(lower.endswith(ext) for ext in extensions):
                rejected.append({"filename": filename, "reason": "只支持 Markdown 文件"})
                continue
            if len(data) > max_bytes:
                rejected.append({"filename": filename, "reason": f"文件超过 {max_bytes // 1024 // 1024} MB"})
                continue
            file_hash = hashlib.sha256(data).hexdigest()
            if file_hash in seen_hashes:
                rejected.append({"filename": filename, "reason": "本次上传中有重复文件"})
                continue
            seen_hashes.add(file_hash)
            existed = self.documents.get_by_hash(file_hash)
            if existed and existed.get("status") != DocStatus.DELETED:
                rejected.append(
                    {
                        "filename": filename,
                        "reason": "文件已存在",
                        "existing_doc_uid": existed.get("doc_uid"),
                    }
                )
                continue
            if existed:
                # 已删除的文档重新上传时复用原 doc_uid，避免 file_hash 唯一约束挡住恢复流程。
                doc_uid = existed["doc_uid"]
                path = DOC_DIR / f"{doc_uid}_{safe}"
                path.write_bytes(data)
                self.documents.update_fields(
                    doc_uid,
                    filename=safe,
                    title=Path(safe).stem,
                    source_path=str(path),
                    size_bytes=len(data),
                    milvus_collection=active_collection,
                    status=DocStatus.PENDING,
                    error_msg=None,
                    chunk_count=0,
                    indexed_at=None,
                )
                task_id = self.tasks.create(TaskType.UPLOAD, doc_uid=doc_uid)
                task_ids.append(task_id)
                self.queue.submit(self.pipeline.run_document, doc_uid, task_id)
                accepted.append(
                    {"doc_uid": doc_uid, "filename": safe, "size_bytes": len(data), "status": "pending"}
                )
                continue
            doc_uid = new_uid()
            path = DOC_DIR / f"{doc_uid}_{safe}"
            path.write_bytes(data)
            title = Path(safe).stem
            self.documents.create(
                doc_uid=doc_uid,
                filename=safe,
                title=title,
                source_path=str(path),
                file_hash=file_hash,
                size_bytes=len(data),
                milvus_collection=active_collection,
                status=DocStatus.PENDING,
            )
            task_id = self.tasks.create(TaskType.UPLOAD, doc_uid=doc_uid)
            task_ids.append(task_id)
            self.queue.submit(self.pipeline.run_document, doc_uid, task_id)
            accepted.append({"doc_uid": doc_uid, "filename": safe, "size_bytes": len(data), "status": "pending"})
        if not accepted:
            if not rejected:
                raise ConflictError("没有可上传的文件")
            reasons = {item["reason"] for item in rejected}
            if reasons == {"只支持 Markdown 文件"}:
                raise UnsupportedMediaError("只支持 .md 或 .markdown 文件")
            if all("MB" in item["reason"] for item in rejected):
                raise PayloadTooLargeError(rejected[0]["reason"])
            raise ConflictError("所有文件都未通过校验", {"rejected": rejected})
        return {
            "accepted": accepted,
            "rejected": rejected,
            "task_id": task_ids[0] if task_ids else None,
            "task_ids": task_ids,
        }

    def reindex_document(self, doc_uid: str) -> dict:
        row = self.documents.get(doc_uid)
        if not row or row.get("status") == DocStatus.DELETED:
            raise NotFoundError("文档不存在")
        active = self.tasks.active_for_doc(doc_uid, ("upload", "reindex", "rebuild"))
        if active:
            raise ConflictError("该文档已有进行中的任务", {"task_id": active["id"]})
        collection = self.store.active_collection
        self.store.ensure_collection(collection)
        self.documents.update_fields(doc_uid, {"status": DocStatus.PARSING, "error_msg": None})
        task_id = self.tasks.create(TaskType.REINDEX, doc_uid=doc_uid)
        self.queue.submit(self.pipeline.run_document, doc_uid, task_id)
        return {"doc_uid": doc_uid, "task_id": task_id, "status": "queued"}

    def delete_document(self, doc_uid: str) -> dict:
        row = self.documents.get(doc_uid)
        if not row or row.get("status") == DocStatus.DELETED:
            raise NotFoundError("文档不存在")
        active = self.tasks.active_for_doc(doc_uid, ("upload", "reindex", "delete", "rebuild"))
        if active:
            raise ConflictError("该文档已有进行中的任务", {"task_id": active["id"]})
        self.documents.mark_deleted(doc_uid)
        task_id = self.tasks.create(TaskType.DELETE, doc_uid=doc_uid)
        self.queue.submit(self.pipeline.delete_document, doc_uid, task_id)
        return {"doc_uid": doc_uid, "task_id": task_id, "status": "queued"}

    def chunks(self, doc_uid: str, limit: int = 50, offset: int = 0) -> dict:
        row = self.documents.get(doc_uid)
        if not row:
            raise NotFoundError("文档不存在")
        try:
            items = self.store.query_chunks(doc_uid, row.get("milvus_collection"))
        except Exception as e:
            raise UnavailableError(f"读取 Milvus 失败: {e}")
        total = len(items)
        page = items[offset:offset + limit]
        return {
            "doc_uid": doc_uid,
            "total": total,
            "items": [
                {
                    "chunk_index": int(item.get("chunk_index") or 0),
                    "title": item.get("title") or "",
                    "text": item.get("text") or "",
                }
                for item in page
            ],
            "page": max(1, offset // max(1, limit) + 1),
            "size": limit,
        }

    # ---------------- 任务 -------------

    def list_tasks(self, page: int, size: int, status: str | None) -> dict:
        rows, total = self.tasks.list(page, size, status)
        return {
            "items": [self._task_payload(row) for row in rows],
            "total": total, "page": page, "size": size,
        }

    def task_detail(self, task_id: int) -> dict:
        row = self.tasks.get(task_id)
        if not row:
            raise NotFoundError("任务不存在")
        return self._task_payload(row)

    def rebuild(self) -> dict:
        active = self.tasks.active_rebuild()
        if active:
            raise ConflictError("已有全量重建任务在进行", {"task_id": active["id"]})
        ready = self.documents.list_ready()
        if not ready:
            raise ConflictError("没有 ready 状态的文档，无法重建")
        task_id = self.tasks.create(TaskType.REBUILD)
        self.queue.submit(self.pipeline.rebuild_all, task_id)
        return {"task_id": task_id, "status": "queued", "documents": len(ready)}

    # ---------------- 检索与问答 -------------

    def retrieval_test(self, query: str, top_k: int, score_threshold: float, expr: str | None) -> dict:
        started = time.perf_counter()
        try:
            docs = KnowledgeRetriever().retrieve(
                query, top_k=top_k, score_threshold=score_threshold, expr=expr
            )
        except Exception as e:
            raise UnavailableError(f"检索失败: {e}")
        return {
            "query": query,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "expr": expr,
            "took_ms": int((time.perf_counter() - started) * 1000),
            "hits": [
                {
                    "rank": index,
                    "score": doc.metadata.get("score"),
                    "doc_uid": doc.metadata.get("doc_uid"),
                    "chunk_index": doc.metadata.get("chunk_index"),
                    "title": doc.metadata.get("title"),
                    "filename": doc.metadata.get("filename"),
                    "url": doc.metadata.get("url"),
                    "snippet": snippet(doc.page_content, 240),
                    "text": doc.page_content,
                }
                for index, doc in enumerate(docs, 1)
            ],
        }

    def qa_test(self, question: str, debug: bool) -> dict:
        result = self.runner.run(question, history=[], debug=debug)
        return result

    # ---------------- 消息与统计 -------------

    def list_messages(
        self, page: int, size: int, session_id: int | None, source: str | None,
        days: int | None, keyword: str | None,
    ) -> dict:
        rows, total = self.messages.admin_list(page, size, session_id, "bot", source, days, keyword)
        items = []
        for row in rows:
            citations = self.citations.list_by_message(int(row["id"]))
            items.append(
                {
                    "id": int(row["id"]),
                    "session_id": int(row["session_id"]),
                    "content": snippet(row.get("content") or "", 260),
                    "source": row.get("source"),
                    "route": row.get("route"),
                    "latency_ms": row.get("latency_ms"),
                    "verified": bool(row.get("verified", 1)),
                    "rating": row.get("rating"),
                    "created_at": iso(row.get("created_at")),
                    "citation_count": len(citations),
                }
            )
        return {"items": items, "total": total, "page": page, "size": size}

    def message_detail(self, message_id: int) -> dict:
        row = self.messages.get(message_id)
        if not row:
            raise NotFoundError("消息不存在")
        citations = self.citations.list_by_message(message_id)
        session = self.sessions.get(int(row["session_id"]))
        trace = row.get("trace_json")
        if isinstance(trace, str):
            try:
                import json
                trace = json.loads(trace)
            except Exception:
                trace = None
        return {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "role": row["role"],
            "content": row["content"],
            "source": row.get("source"),
            "route": row.get("route"),
            "sources": citations,
            "trace": trace,
            "verified": bool(row.get("verified", 1)),
            "rating": row.get("rating"),
            "latency_ms": row.get("latency_ms"),
            "created_at": iso(row.get("created_at")),
            "session": {
                "id": int(session["id"]) if session else None,
                "visitor_name": session.get("visitor_name") if session else "",
                "turn_count": int(session.get("turn_count") or 0) if session else 0,
                "created_at": iso(session.get("created_at")) if session else None,
            },
        }

    def overview(self, days: int) -> dict:
        return StatsService.overview(days)

    def health(self) -> dict:
        return HealthService.detailed()

    def public_config(self) -> dict:
        cfg = Config.instance()
        return {
            "brand": cfg.section("brand"),
            "milvus": {
                "uri": cfg.get("milvus.uri"),
                "collection": cfg.get("milvus.collection"),
                "version": self.store.health().get("version"),
                "top_k": cfg.get("milvus.top_k"),
                "candidate_limit": cfg.get("milvus.candidate_limit"),
                "score_threshold": cfg.get("milvus.score_threshold"),
            },
            "embedding": cfg.section("embedding"),
            "llm": {
                "chat": {k: v for k, v in cfg.section("llm.chat").items() if k != "api_key_env"},
                "grader": {k: v for k, v in cfg.section("llm.grader").items() if k != "api_key_env"},
            },
            "rag": {
                k: v for k, v in cfg.section("rag").items()
                if k not in {"domain_keywords", "suggestions"}
            },
            "ingest": cfg.section("ingest"),
            "rate_limit": cfg.section("rate_limit"),
        }
