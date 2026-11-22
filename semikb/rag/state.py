"""图状态。"""
from typing import TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict, total=False):
    question: str
    original_question: str
    generation: str
    transform_count: int
    generation_count: int
    documents: list[Document]
    history: list[dict]
    route: str
    route_method: str
    direct_intent: str
    source: str
    verified: bool
    terminated_by: str
    verdict: str
    trace_nodes: list[dict]
    llm_calls: int
