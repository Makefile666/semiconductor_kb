"""Milvus 3.0.2 集合、写入与混合检索。

这里不经过 langchain-milvus，直接用 pymilvus 的 MilvusClient。
原因：Milvus 3.0 对应 PyMilvus 3.0.x，LangChain 的 Milvus 封装存在连接管理兼容风险；
同时直接调用可以精确控制 TEXT 字段、BM25 函数、别名与 RRF 参数。
"""
import threading
from pathlib import Path

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from semikb.common.config import PROJECT_ROOT, Config
from semikb.common.logger import get_logger

ACTIVE_FILE = PROJECT_ROOT / "data" / "active_collection.txt"


class MilvusStore:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self.config = Config.instance()
        self.logger = get_logger(__name__)
        self.uri = str(self.config.get("milvus.uri", "http://127.0.0.1:19530"))
        self.alias = str(self.config.get("milvus.collection", "semi_kb_chunks"))
        self.default_physical = str(
            self.config.get("milvus.default_physical", "semi_kb_chunks_v1")
        )
        self.prefix = str(self.config.get("milvus.physical_prefix", "semi_kb_chunks_v"))
        self.client = MilvusClient(uri=self.uri)
        self._ready = True

    # ---------------- 集合 ----------------

    def _create_collection(self, name: str) -> None:
        schema = self.client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(
            field_name="text",
            datatype=DataType.VARCHAR,
            max_length=12000,
            enable_analyzer=True,
            analyzer_params={"tokenizer": "jieba", "filter": ["cnalphanumonly"]},
        )
        schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=1000)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=1000)
        schema.add_field(field_name="filename", datatype=DataType.VARCHAR, max_length=1000)
        schema.add_field(field_name="filetype", datatype=DataType.VARCHAR, max_length=1000)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=1000)
        schema.add_field(field_name="category_depth", datatype=DataType.INT64)
        schema.add_field(field_name="doc_uid", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field(field_name="dense", datatype=DataType.FLOAT_VECTOR, dim=1024)

        schema.add_function(
            Function(
                name="text_bm25_emb",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
        )

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="sparse",
            index_name="sparse_inverted_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            params={
                "inverted_index_algo": "DAAT_MAXSCORE",
                "bm25_k1": 1.2,
                "bm25_b": 0.75,
            },
        )
        index_params.add_index(
            field_name="dense",
            index_name="dense_hnsw",
            index_type="HNSW",
            metric_type="IP",
            params={"M": 16, "efConstruction": 64},
        )
        self.client.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params,
            consistency_level="Strong",
        )
        self.logger.info("创建 Milvus 集合: %s", name)

    def set_alias(self, name: str, alias: str | None = None) -> None:
        alias = alias or self.alias
        try:
            aliases = self.client.list_aliases(collection_name=name)
            if isinstance(aliases, dict):
                aliases = aliases.get("aliases", [])
        except Exception:
            aliases = []
        if alias in aliases:
            self.client.alter_alias(collection_name=name, alias=alias)
        else:
            try:
                self.client.create_alias(collection_name=name, alias=alias)
            except Exception:
                # 别名可能挂在别的物理集合上，直接改指向。
                self.client.alter_alias(collection_name=name, alias=alias)
        self.logger.info("Milvus 别名 %s -> %s", alias, name)

    def ensure_collection(self, name: str | None = None, switch_alias: bool = True) -> str:
        name = name or self.active_collection
        with self._lock:
            if not self.client.has_collection(name):
                self._create_collection(name)
            if switch_alias:
                self.set_alias(name)
            if name == self.default_physical or switch_alias:
                self._write_active(name)
        return name

    @property
    def active_collection(self) -> str:
        try:
            if ACTIVE_FILE.exists():
                value = ACTIVE_FILE.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            pass
        return self.default_physical

    def _write_active(self, name: str) -> None:
        ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_FILE.write_text(name, encoding="utf-8")

    def next_physical_collection(self) -> str:
        names = self.client.list_collections()
        nums = []
        for item in names:
            if item.startswith(self.prefix):
                tail = item[len(self.prefix):]
                if tail.isdigit():
                    nums.append(int(tail))
        return f"{self.prefix}{max(nums, default=1) + 1}"

    # ---------------- 写入 ----------------

    def insert_chunks(self, rows: list[dict], collection_name: str | None = None) -> int:
        if not rows:
            return 0
        name = collection_name or self.active_collection
        result = self.client.insert(collection_name=name, data=rows)
        inserted = int(result.get("insert_count", len(rows))) if isinstance(result, dict) else len(rows)
        return inserted

    def flush(self, collection_name: str | None = None) -> None:
        self.client.flush(collection_name=collection_name or self.active_collection)

    def delete_by_doc(self, doc_uid: str, collection_name: str | None = None) -> int:
        name = collection_name or self.active_collection
        result = self.client.delete(
            collection_name=name,
            filter=f'doc_uid == "{doc_uid}"',
        )
        if isinstance(result, dict):
            return int(result.get("delete_count", 0) or 0)
        return 0

    # ---------------- 查询 ----------------

    def query_chunks(self, doc_uid: str, collection_name: str | None = None) -> list[dict]:
        name = collection_name or self.active_collection
        rows = self.client.query(
            collection_name=name,
            filter=f'doc_uid == "{doc_uid}"',
            output_fields=[
                "text", "title", "filename", "doc_uid", "chunk_index",
                "category_depth", "category",
            ],
            limit=16384,
        )
        return sorted(rows, key=lambda x: int(x.get("chunk_index") or 0))

    def count_doc(self, doc_uid: str, collection_name: str | None = None) -> int:
        try:
            rows = self.client.query(
                collection_name=collection_name or self.active_collection,
                filter=f'doc_uid == "{doc_uid}"',
                output_fields=["count(*)"],
            )
            if rows:
                return int(list(rows[0].values())[0])
        except Exception:
            pass
        return len(self.query_chunks(doc_uid, collection_name))

    def count_total(self, collection_name: str | None = None) -> int:
        name = collection_name or self.alias
        try:
            rows = self.client.query(
                collection_name=name,
                filter='doc_uid != ""',
                output_fields=["count(*)"],
            )
            if rows:
                return int(list(rows[0].values())[0])
        except Exception:
            pass
        try:
            stats = self.client.get_collection_stats(collection_name=name)
            return int(stats.get("row_count", 0) or 0)
        except Exception:
            return 0

    # ---------------- 混合检索 ----------------

    def search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 4,
        candidate_limit: int = 20,
        score_threshold: float = 0.0,
        expr: str | None = None,
        collection_name: str | None = None,
    ) -> list[dict]:
        name = collection_name or self.alias
        dense_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="dense",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=candidate_limit,
        )
        sparse_req = AnnSearchRequest(
            data=[query_text],
            anns_field="sparse",
            param={"metric_type": "BM25"},
            limit=candidate_limit,
        )
        results = self.client.hybrid_search(
            collection_name=name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=int(self.config.get("milvus.ranker_k", 100))),
            limit=top_k,
            output_fields=[
                "text", "title", "filename", "doc_uid", "chunk_index",
                "category_depth", "category", "source",
            ],
            filter=expr or str(self.config.get("milvus.expr", 'category == "content"')),
        )
        hits = results[0] if results else []
        output = []
        for item in hits:
            if isinstance(item, dict):
                entity = item.get("entity", {}) or {}
                score = item.get("distance", item.get("score", 0.0))
            else:
                entity = getattr(item, "entity", {}) or {}
                score = getattr(item, "distance", getattr(item, "score", 0.0))
            if float(score or 0) < score_threshold:
                continue
            output.append(
                {
                    "score": float(score or 0),
                    "text": entity.get("text", ""),
                    "title": entity.get("title", ""),
                    "filename": entity.get("filename", ""),
                    "doc_uid": entity.get("doc_uid", ""),
                    "chunk_index": int(entity.get("chunk_index", 0) or 0),
                    "category_depth": int(entity.get("category_depth", 0) or 0),
                    "category": entity.get("category", ""),
                    "source_url": entity.get("source", ""),
                }
            )
        return output

    def health(self) -> dict:
        info = {"status": "down", "collection": self.alias, "entities": 0}
        try:
            info["version"] = str(self.client.get_server_version())
            info["entities"] = self.count_total(self.alias)
            info["status"] = "up"
        except Exception as e:
            info["error"] = str(e)[:200]
        return info
