"""LangGraph 工作流。"""
from langgraph.graph import END, START, StateGraph

from semikb.rag.nodes import (
    decide_to_generate,
    direct_answer,
    generate,
    generation_decision,
    grade_documents,
    grade_generation,
    retrieve,
    route_decision,
    route_question,
    transform_query,
    web_search,
)
from semikb.rag.state import GraphState


def build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("route_question", route_question)
    workflow.add_node("direct_answer", direct_answer)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("generate", generate)
    workflow.add_node("grade_generation", grade_generation)
    workflow.add_node("transform_query", transform_query)
    workflow.add_node("web_search", web_search)

    workflow.add_edge(START, "route_question")
    workflow.add_conditional_edges(
        "route_question",
        route_decision,
        {"retrieve": "retrieve", "web_search": "web_search", "direct_answer": "direct_answer"},
    )
    workflow.add_edge("direct_answer", END)
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {
            "generate": "generate",
            "transform_query": "transform_query",
            "web_search": "web_search",
        },
    )
    workflow.add_edge("transform_query", "retrieve")
    workflow.add_edge("web_search", "generate")
    workflow.add_edge("generate", "grade_generation")
    workflow.add_conditional_edges(
        "grade_generation",
        generation_decision,
        {
            "useful": END,
            "not supported": "generate",
            "not useful": "transform_query",
            "give_up": END,
        },
    )
    return workflow.compile()
