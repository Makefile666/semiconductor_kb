"""提示词与结构化输出模型，逻辑移植自 graph2。"""
from functools import lru_cache
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from semikb.rag.llm import LLMFactory


class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search", "direct"] = Field(
        description="direct 表示寒暄、身份或能力询问，无需查资料；vectorstore 表示半导体知识库主题；web_search 表示其他需要联网查证的问题"
    )


class BatchGradeDocuments(BaseModel):
    scores: list[Literal["yes", "no"]] = Field(
        description="按文档编号顺序排列的评分，长度必须等于文档数量"
    )


class SingleGradeDocument(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="文档是否与问题相关")


class GradeGeneration(BaseModel):
    grounded: Literal["yes", "no"] = Field(description="回答是否完全基于给定文档事实")
    answers_question: Literal["yes", "no"] = Field(description="回答是否真正解决用户问题")


@lru_cache(maxsize=1)
def route_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
 "你是一个擅长分流用户问题的路由专家，可选目标是 direct、vectorstore 或 web_search。"
                "direct：问候、感谢、告别、询问你是谁、询问你会做什么、闲聊等无需查资料即可回应的内容。"
                "vectorstore：半导体材料、芯片制造、光刻、刻蚀、薄膜、封装、测试等领域主题。"
                "web_search：不属于半导体知识库，但需要外部事实或实时信息的问题。"
                "寒暄和身份问题不要走向量知识库或网络搜索。",
            ),
            ("human", "{question}"),
        ]
    )
    return prompt | LLMFactory.grader().with_structured_output(RouteQuery)


@lru_cache(maxsize=1)
def batch_grade_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
 "你是检索文档相关性评分器。判断每一篇文档是否与用户问题相关。"
                "只输出 scores 列表，按文档编号顺序排列，每项 yes 或 no，长度等于文档数量。"
                "文档包含与问题相关的关键词或语义含义即视为相关，目的是过滤明显错误的结果，不必过严。",
            ),
            ("human", "用户问题：{question}\n\n待评分的文档列表：\n{documents}"),
        ]
    )
    return prompt | LLMFactory.grader().with_structured_output(BatchGradeDocuments)


@lru_cache(maxsize=1)
def single_grade_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
 "你是检索文档相关性评分器。文档包含与问题相关的关键词或语义含义即相关，"
                "只给出 yes 或 no。",
            ),
            ("human", "检索到的文档：\n\n{document}\n\n用户问题：{question}"),
        ]
    )
    return prompt | LLMFactory.grader().with_structured_output(SingleGradeDocument)


@lru_cache(maxsize=1)
def generation_grade_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
 "你是生成结果质量校验器，同时判断两件事：\n"
                "1. grounded：回答是否完全基于给定文档中的事实，没有编造文档之外的信息。\n"
                "2. answers_question：回答是否真正解决了用户提出的问题。\n"
                "两个字段都只能填 yes 或 no，必须分别判断，不要因为一个为 no 就把另一个也判为 no。",
            ),
            (
                "human",
                "事实集：\n\n{documents}\n\n用户问题：{question}\n\n生成回答：{generation}",
            ),
        ]
    )
    return prompt | LLMFactory.grader().with_structured_output(GradeGeneration)


def rewrite_question(question: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
 "作为问题重写器，把输入问题转换为更适合向量数据库检索的版本。"
                "保留原意，补全术语，不要回答问题。",
            ),
            ("human", "初始问题：\n\n{question}\n\n请给出一个优化后的检索问题。"),
        ]
    )
    chain = prompt | LLMFactory.grader()
    return str(chain.invoke({"question": question}).content).strip()


def generation_messages(question: str, context: str, history: list[dict] | None = None):
    history = history or []
    history_text = ""
    for item in history[-6:]:
        role = "用户" if item.get("role") == "user" else "助手"
        history_text += f"{role}：{item.get('content', '')[:300]}\n"
    system = (
        "你是半导体工艺与芯片制造领域的文档问答助手。"
        "只根据提供的检索上下文回答，不要使用上下文之外的事实，不要编造数值、公式或结论。"
        "上下文按文档编号组织；回答时用 [1]、[2] 这样的角标标注依据。"
        "如果上下文不足以回答，直接说明缺少哪方面资料。回答保持简洁、结构清晰。"
    )
    human = (
        f"最近对话：\n{history_text or '无'}\n\n"
        f"检索上下文：\n{context}\n\n"
        f"用户问题：{question}\n\n回答："
    )
    return [("system", system), ("human", human)]
