"""Tavily 联网检索。"""
import os

import requests
from langchain_core.documents import Document

from semikb.common.config import Config
from semikb.common.logger import get_logger

logger = get_logger(__name__)


class WebSearch:
    def __init__(self):
        self.config = Config.instance()
        self.key = os.getenv(str(self.config.get("web_search.api_key_env", "TAVILY_API_KEY")))
        self.url = "https://api.tavily.com/search"

    def search(self, query: str) -> list[Document]:
        if not self.key:
            return []
        try:
            response = requests.post(
                self.url,
                json={
                    "api_key": self.key,
                    "query": query,
                    "max_results": int(self.config.get("web_search.max_results", 3)),
                    "search_depth": str(self.config.get("web_search.search_depth", "basic")),
                    "include_answer": False,
                },
                timeout=float(self.config.get("web_search.timeout_seconds", 20)),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning("Tavily 搜索失败: %s", e)
            return []
        docs = []
        for item in payload.get("results", []):
            content = (item.get("content") or item.get("raw_content") or "").strip()
            if not content:
                continue
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "title": item.get("title", "联网结果"),
                        "url": item.get("url", ""),
                        "source": item.get("url", ""),
                        "filename": "",
                        "doc_uid": "",
                        "chunk_index": None,
                        "category": "web_search",
                        "score": None,
                    },
                )
            )
        return docs
