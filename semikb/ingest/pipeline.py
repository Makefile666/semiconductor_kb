"""入库流水线：解析、切片、嵌入、写 Milvus、回写 MySQL。"""
import time
from pathlib import Path

from semikb.common.config import Config
from semikb.common.constants import DocStatus, TaskStatus
from semikb.common.logger import get_logger
from semikb.common.utils import iso, now
from semikb.dao.document_dao import DocumentDao
from semikb.dao.task_dao import TaskDao
from semikb.ingest.milvus_store import MilvusStore
from semikb.ingest.parser import MarkdownChunker, parse_markdown
from semikb.rag.llm import LLMFactory

logger = get_logger(__name__)


class IngestPipeline:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.docs = DocumentDao()
        self.tasks = TaskDao()
        self.store = MilvusStore()
        self.chunker = MarkdownChunker()
        self._ready = True

    @staticmethod
    def _publish_task(task: dict | None) -> None:
        if not task:
            return
        try:
            from semikb.service.admin_ws_manager import AdminWsManager

            AdminWsManager.instance().publish(
                {
                    "type": "task_update",
                    "task": {
                        "id": task.get("id"),
                        "task_type": task.get("task_type"),
                        "doc_uid": task.get("doc_uid"),
                        "status": task.get("status"),
                        "progress": task.get("progress"),
                        "total_chunks": task.get("total_chunks"),
                        "done_chunks": task.get("done_chunks"),
                        "message": task.get("message"),
                    },
                }
            )
        except Exception:
            pass

    @staticmethod
    def _publish_doc(doc_uid: str) -> None:
        try:
            from semikb.service.admin_ws_manager import AdminWsManager

            AdminWsManager.instance().publish({"type": "document_update", "doc_uid": doc_uid})
        except Exception:
            pass

    def _task_update(self, task_id: int | None, **fields) -> None:
        if task_id is None:
            return
        self.tasks.update(task_id, fields)
        self._publish_task(self.tasks.get(task_id))

    def _mark_doc(self, doc_uid: str, **fields) -> None:
        self.docs.update_fields(doc_uid, fields)
        self._publish_doc(doc_uid)

    def run_document(
        self,
        doc_uid: str,
        task_id: int | None = None,
        collection: str | None = None,
        persist_collection: bool = True,
        update_task: bool = True,
        flush_collection: bool = True,
        verify_count: bool = True,
    ) -> dict:
        doc = self.docs.get(doc_uid)
        if not doc:
            raise ValueError(f"文档不存在: {doc_uid}")
        target = collection or doc.get("milvus_collection") or self.store.active_collection
        self.store.ensure_collection(target, switch_alias=target == self.store.active_collection)
        started = time.perf_counter()
        if update_task:
            self._task_update(
                task_id, status=TaskStatus.RUNNING, progress=2,
                message="正在解析 Markdown",
            )
        self._mark_doc(doc_uid, status=DocStatus.PARSING, error_msg=None)
        try:
            path = Path(doc["source_path"])
            if not path.exists():
                raise FileNotFoundError(f"源文件不存在: {path}")
            title, blocks = parse_markdown(path)
            chunks = self.chunker.split(blocks)
            if not chunks:
                raise ValueError("没有解析出有效切片")
            total = len(chunks)
            self._mark_doc(
                doc_uid,
                title=title,
                chunk_count=total,
                status=DocStatus.INDEXING,
            )
            if update_task:
                self._task_update(
                    task_id, total_chunks=total, done_chunks=0, progress=5,
                    message=f"解析完成，共 {total} 个切片，开始向量化",
                )
            self.store.delete_by_doc(doc_uid, target)

            embedding = LLMFactory.embedding()
            embed_batch = int(self.config.get("ingest.batch_embed", 10))
            insert_batch = int(self.config.get("ingest.batch_insert", 50))
            done = 0
            for start in range(0, total, embed_batch):
                group = chunks[start:start + embed_batch]
                texts = [item["text"] for item in group]
                vectors = embedding.embed_documents(texts)
                rows = []
                for item, vector in zip(group, vectors):
                    rows.append(
                        {
                            "text": item["text"],
                            "category": "content",
                            "source": doc["filename"],
                            "filename": doc["filename"],
                            "filetype": "md",
                            "title": item["title"],
                            "category_depth": int(item["category_depth"]),
                            "doc_uid": doc_uid,
                            "chunk_index": int(item["chunk_index"]),
                            "dense": vector,
                        }
                    )
                for offset in range(0, len(rows), insert_batch):
                    self.store.insert_chunks(rows[offset:offset + insert_batch], target)
                done += len(group)
                if update_task:
                    progress = min(95, 5 + int(90 * done / total))
                    self._task_update(
                        task_id, done_chunks=done, progress=progress,
                        message=f"已写入 {done}/{total} 个切片",
                    )
            if flush_collection:
                self.store.flush(target)
            if verify_count:
                actual = self.store.count_doc(doc_uid, target)
                if actual != total:
                    raise RuntimeError(f"切片数量校验失败: MySQL {total} / Milvus {actual}")
            else:
                actual = total
            fields = {
                "status": DocStatus.READY,
                "chunk_count": actual,
                "error_msg": None,
                "indexed_at": now(),
            }
            if persist_collection:
                fields["milvus_collection"] = target
            self._mark_doc(doc_uid, **fields)
            if update_task:
                self._task_update(
                    task_id, status=TaskStatus.SUCCEEDED, progress=100,
                    done_chunks=total, total_chunks=total,
                    message=f"入库完成，共 {total} 个切片",
                    finished_at=now(),
                )
            logger.info("文档入库完成: %s chunks=%s %.2fs", doc_uid, total, time.perf_counter() - started)
            return {"doc_uid": doc_uid, "chunks": total, "collection": target}
        except Exception as e:
            message = str(e)[:500]
            logger.exception("文档入库失败: %s", doc_uid)
            self._mark_doc(doc_uid, status=DocStatus.FAILED, error_msg=message)
            if update_task:
                self._task_update(
                    task_id, status=TaskStatus.FAILED, message=message,
                    finished_at=now(),
                )
            raise

    def delete_document(self, doc_uid: str, task_id: int | None = None) -> dict:
        doc = self.docs.get(doc_uid)
        if not doc:
            raise ValueError(f"文档不存在: {doc_uid}")
        self._task_update(task_id, status=TaskStatus.RUNNING, progress=10, message="正在删除向量")
        try:
            collection = doc.get("milvus_collection") or self.store.active_collection
            deleted = self.store.delete_by_doc(doc_uid, collection)
            self.store.flush(collection)
            self.docs.mark_deleted(doc_uid)
            self._task_update(
                task_id, status=TaskStatus.SUCCEEDED, progress=100,
                message=f"已删除 {deleted} 个切片", finished_at=now(),
            )
            self._publish_doc(doc_uid)
            return {"doc_uid": doc_uid, "deleted": deleted}
        except Exception as e:
            self._task_update(
                task_id, status=TaskStatus.FAILED, message=str(e)[:500],
                finished_at=now(),
            )
            raise

    def rebuild_all(self, task_id: int) -> dict:
        docs = self.docs.list_ready()
        if not docs:
            raise ValueError("没有可重建的 ready 文档")
        new_collection = self.store.next_physical_collection()
        self._task_update(
            task_id, status=TaskStatus.RUNNING, progress=1,
            message=f"正在创建影子集合 {new_collection}",
        )
        self.store.ensure_collection(new_collection, switch_alias=False)
        total_docs = len(docs)
        total_chunks = 0
        for index, doc in enumerate(docs, 1):
            result = self.run_document(
                doc["doc_uid"],
                task_id=None,
                collection=new_collection,
                persist_collection=False,
                update_task=False,
                flush_collection=False,
                verify_count=False,
            )
            total_chunks += int(result.get("chunks", 0))
            progress = min(95, 1 + int(94 * index / total_docs))
            self._task_update(
                task_id, progress=progress,
                message=f"已重建 {index}/{total_docs} 篇，累计 {total_chunks} 个切片",
            )
        self.store.flush(new_collection)
        actual = self.store.count_total(new_collection)
        if actual < total_chunks:
            raise RuntimeError(f"影子集合数量校验失败: 期望 {total_chunks} / 实际 {actual}")
        self.store.set_alias(new_collection, self.store.alias)
        self.store._write_active(new_collection)
        self.docs.set_all_collection(new_collection)
        self._task_update(
            task_id, status=TaskStatus.SUCCEEDED, progress=100,
            total_chunks=actual, done_chunks=actual,
            message=f"重建完成，别名已切到 {new_collection}",
            finished_at=now(),
        )
        logger.info("全量重建完成: %s total=%s", new_collection, actual)
        return {"collection": new_collection, "chunks": actual}
