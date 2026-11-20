"""知识库检索器。"""
from langchain_core.documents import Document

from semikb.common.config import Config
from semikb.common.logger import get_logger
from semikb.ingest.milvus_store import MilvusStore
from semikb.rag.llm import LLMFactory

logger = get_logger(__name__)


class KnowledgeRetriever:
    def __init__(self):
        self.config = Config.instance()
        self.store = MilvusStore()
        self.embedding = LLMFactory.embedding()

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        expr: str | None = None,
    ) -> list[Document]:
        top_k = int(top_k or self.config.get("milvus.top_k", 4))
        candidate = int(self.config.get("milvus.candidate_limit", 20))
        threshold = float(
            self.config.get("milvus.score_threshold", 0.0)
            if score_threshold is None
            else score_threshold
        )
        vector = self.embedding.embed_query(question)
        hits = self.store.search(
            query_text=question,
            query_vector=vector,
            top_k=top_k,
            candidate_limit=candidate,
            score_threshold=threshold,
            expr=expr,
        )
        output: list[Document] = []
        for item in hits:
            output.append(
                Document(
                    page_content=item.get("text", ""),
                    metadata={
                        "score": item.get("score", 0.0),
                        "doc_uid": item.get("doc_uid", ""),
                        "filename": item.get("filename", ""),
                        "title": item.get("title", ""),
                        "chunk_index": item.get("chunk_index", 0),
                        "category": item.get("category", ""),
                        "url": item.get("source_url", ""),
                        "source": item.get("filename", ""),
                    },
                )
            )
        logger.info("检索完成: question=%s hits=%s", question[:40], len(output))
        return output
