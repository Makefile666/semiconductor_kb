"""LangGraph 节点，判定逻辑移植自 graph2。"""
import re
import time

from langchain_core.documents import Document

from semikb.common.config import Config
from semikb.common.exceptions import UnavailableError
from semikb.common.logger import get_logger
from semikb.rag import runtime
from semikb.rag.llm import LLMFactory
from semikb.rag.prompts import (
    batch_grade_chain,
    generation_grade_chain,
    generation_messages,
    rewrite_question,
    route_chain,
    single_grade_chain,
)
from semikb.rag.retriever import KnowledgeRetriever
from semikb.rag.web_search import WebSearch

logger = get_logger(__name__)
config = Config.instance()


def _finish(state: dict, node: str, started: float, detail: dict, extra: dict | None = None) -> dict:
    elapsed = int((time.perf_counter() - started) * 1000)
    runtime.emit_node(node, "end", elapsed, detail)
    trace = list(state.get("trace_nodes", []))
    trace.append({"node": node, "elapsed_ms": elapsed, "detail": detail})
    result = {"trace_nodes": trace}
    if extra:
        result.update(extra)
    return result


def _format_context(docs: list[Document], limit: int | None = None) -> str:
    limit = int(limit or config.get("rag.context_char_limit", 8000))
    parts = []
    used = 0
    for index, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        head = f"[文档 {index}] 标题：{meta.get('title', '')} 文件：{meta.get('filename', '')}\n"
        body = doc.page_content or ""
        piece = head + body
        if used + len(piece) > limit:
            piece = piece[: max(0, limit - used)]
        if piece:
            parts.append(piece)
            used += len(piece)
        if used >= limit:
            break
    return "\n\n".join(parts)


def _small_talk_intent(question: str) -> str | None:
    """识别无需查资料的寒暄与身份问题，避免进入检索链路。"""
    text = re.sub(r"[\s\u3000]+", "", (question or "").strip().lower())
    text = re.sub(r"[，。！？、,.!?~～:：;；]+", "", text)
    prefix = re.compile(
        r"^(你好|您好|嗨|哈喽|hello|早上好|上午好|中午好|下午好|晚上好|在吗|在不在)"
    )
    for _ in range(3):
        match = prefix.match(text)
        if not match:
            break
        text = text[match.end():]
    text = re.sub(r"^(请问|想问一下|问一下|我想问一下|我想知道|想问下|问下)", "", text)
    text = re.sub(r"(呢|呀|啊|吧|哦|啦)$", "", text)

    if text in {"", "吗", "在吗", "在不在", "有人吗", "hello", "hi", "hey"}:
        return "greeting"
    if re.fullmatch(
        r"(你是谁|你叫什么(?:名字)?|你是什么(?:东西|助手|机器人)?|"
        r"你是什么模型|你用的什么模型|你由谁开发|你是谁开发(?:的)?|"
        r"自我介绍(?:一下)?|介绍一下(?:你自己|你)|"
        r"你是真人吗|你是机器人吗|你几岁|你多大了|你是男是女|"
        r"whoareyou|whatareyou)",
        text,
    ):
        return "identity"
    if re.fullmatch(
        r"(你能做什么|你会做什么|你可以做什么|你能干什么|你会什么|"
        r"你有哪些功能|你能帮我做什么|你有什么功能|whatcanyoudo)",
        text,
    ):
        return "capability"
    if re.fullmatch(r"(谢谢|谢谢你|谢了|感谢|感谢你|thanks|thankyou)", text):
        return "thanks"
    if re.fullmatch(r"(再见|拜拜|下次见|回头见|bye|goodbye)", text):
        return "farewell"
    return None


def route_question(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("route_question", "start")
    question = state.get("original_question") or state.get("question", "")
    lowered = question.lower()
    keywords = [str(x).lower() for x in config.get("rag.domain_keywords", [])]
    if any(keyword in lowered for keyword in keywords):
        return _finish(
            state, "route_question", started,
            {"route": "vectorstore", "method": "keyword"},
            {"route": "vectorstore", "route_method": "keyword"},
        )
    intent = _small_talk_intent(question)
    if intent:
        return _finish(
            state, "route_question", started,
            {"route": "direct", "method": "small_talk", "intent": intent},
            {"route": "direct", "route_method": "small_talk", "direct_intent": intent},
        )
    try:
        runtime.bump_llm()
        result = route_chain().invoke({"question": question})
        route = getattr(result, "datasource", "vectorstore")
        method = "llm"
    except Exception as e:
        logger.warning("路由模型失败，默认走向量库: %s", e)
        route, method = "vectorstore", "fallback"
    extra = {"route": route, "route_method": method}
    if route == "direct":
        extra["direct_intent"] = "generic"
    return _finish(
        state, "route_question", started,
        {"route": route, "method": method},
        extra,
    )


def route_decision(state: dict) -> str:
    route = state.get("route")
    if route == "direct":
        return "direct_answer"
    return "retrieve" if route == "vectorstore" else "web_search"


def direct_answer(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("direct_answer", "start")
    intent = state.get("direct_intent") or "generic"
    brand = str(config.get("brand.name", "芯知 SemiKB"))
    org = str(config.get("brand.org_name", "半导体文档知识库"))
    identity = f"我是{brand}，{org}的问答助手。我的回答主要来自本地半导体工艺文档，可以问我光刻、刻蚀、薄膜、封装、测试等问题。"
    answers = {
        "greeting": f"你好，{identity}",
        "identity": identity,
        "capability": "我可以基于本地半导体知识库，回答材料、芯片制造、光刻、刻蚀、薄膜、封装、测试等问题。",
        "thanks": "不客气。需要查工艺资料时，直接说具体问题就行。",
        "farewell": "再见，需要查半导体工艺资料时随时回来。",
        "generic": "我主要回答半导体工艺与芯片制造相关的问题。可以说得更具体一些，比如光刻胶、刻蚀、3D NAND 或先进封装。",
    }
    answer = answers.get(intent, answers["generic"])
    runtime.emit_token(answer)
    return _finish(
        state, "direct_answer", started,
        {"intent": intent, "chars": len(answer)},
        {
            "generation": answer,
            "source": "direct",
            "route": "direct",
            "verified": True,
            "terminated_by": "direct",
            "verdict": "useful",
        },
    )


def retrieve(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("retrieve", "start")
    question = state.get("question", "")
    try:
        docs = KnowledgeRetriever().retrieve(question)
        error = ""
    except Exception as e:
        logger.warning("检索失败: %s", e)
        docs, error = [], str(e)[:200]
    detail = {"hits": len(docs)}
    if error:
        detail["error"] = error
    return _finish(
        state, "retrieve", started, detail,
        {"documents": docs, "source": "vectorstore", "route": "vectorstore"},
    )


def grade_documents(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("grade_documents", "start")
    question = state.get("question", "")
    docs = state.get("documents") or []
    if not docs:
        return _finish(
            state, "grade_documents", started, {"kept": 0, "total": 0},
            {"documents": []},
        )
    filtered: list[Document] = []
    try:
        blocks = "\n\n".join(
            f"[文档 {i}]\n{(doc.page_content or '')[:1800]}"
            for i, doc in enumerate(docs, 1)
        )
        runtime.bump_llm()
        result = batch_grade_chain().invoke({"question": question, "documents": blocks})
        scores = [str(s).strip().lower() for s in result.scores]
        if len(scores) != len(docs):
            raise ValueError(f"批量评分数量不一致: {len(docs)}/{len(scores)}")
        for doc, score in zip(docs, scores):
            if score.startswith("yes"):
                filtered.append(doc)
    except Exception as e:
        logger.warning("批量评分失败: %s", e)
        if "429" in str(e) or "rate limit" in str(e).lower() or "limit_requests" in str(e).lower():
            logger.warning("评分模型限流，保留全部检索结果，跳过逐篇评分")
            filtered = list(docs)
        else:
            for doc in docs:
                try:
                    runtime.bump_llm()
                    result = single_grade_chain().invoke(
                        {"question": question, "document": (doc.page_content or "")[:1800]}
                    )
                    if str(result.binary_score).lower().startswith("yes"):
                        filtered.append(doc)
                except Exception:
                    # 评分模型不可用时保留文档，避免整条链路被外部依赖拖死。
                    filtered.append(doc)
    return _finish(
        state, "grade_documents", started,
        {"kept": len(filtered), "total": len(docs)},
        {"documents": filtered},
    )


def decide_to_generate(state: dict) -> str:
    docs = state.get("documents") or []
    transform_count = int(state.get("transform_count", 0) or 0)
    if docs:
        return "generate"
    if transform_count >= int(config.get("rag.transform_max", 2)):
        return "web_search"
    return "transform_query"


def generate(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("generate", "start")
    question = state.get("original_question") or state.get("question", "")
    docs = state.get("documents") or []
    generation_count = int(state.get("generation_count", 0) or 0) + 1

    if not docs:
        message = str(config.get("rag.no_result_message"))
        return _finish(
            state, "generate", started, {"chars": len(message), "mode": "no_result"},
            {
                "generation": message,
                "generation_count": generation_count,
                "verified": False,
                "terminated_by": "no_result",
            },
        )

    context = _format_context(docs)
    messages = generation_messages(question, context, state.get("history") or [])
    answer = ""
    try:
        runtime.bump_llm()
        llm = LLMFactory.chat()
        for chunk in llm.stream(messages):
            content = chunk.content
            if isinstance(content, list):
                text = "".join(
                    str(part.get("text", "")) if isinstance(part, dict) else str(part)
                    for part in content
                )
            else:
                text = str(content or "")
            if text:
                answer += text
                runtime.emit_token(text)
        if not answer.strip():
            answer = str(llm.invoke(messages).content or "")
    except Exception as e:
        logger.warning("生成失败，使用抽取式兜底: %s", e)
        answer = "\n\n".join(
            f"【{doc.metadata.get('title') or doc.metadata.get('filename') or '资料'}】\n"
            f"{(doc.page_content or '')[:900]}"
            for doc in docs[:2]
        )
        return _finish(
            state, "generate", started, {"chars": len(answer), "mode": "extractive", "error": str(e)[:200]},
            {
                "generation": answer,
                "generation_count": generation_count,
                "verified": False,
                "source": "extractive",
                "terminated_by": "llm_error",
            },
        )
    return _finish(
        state, "generate", started, {"chars": len(answer)},
        {"generation": answer, "generation_count": generation_count},
    )


def grade_generation(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("grade_generation", "start")
    if state.get("terminated_by") == "no_result":
        return _finish(
            state, "grade_generation", started, {"grounded": "no", "answers_question": "no"},
            {"verified": False, "terminated_by": "no_result", "verdict": "give_up"},
        )
    question = state.get("original_question") or state.get("question", "")
    docs = state.get("documents") or []
    generation = state.get("generation", "")
    generation_count = int(state.get("generation_count", 0) or 0)
    transform_count = int(state.get("transform_count", 0) or 0)
    try:
        runtime.bump_llm()
        result = generation_grade_chain().invoke(
            {
                "documents": _format_context(docs),
                "question": question,
                "generation": generation,
            }
        )
        grounded = str(result.grounded).strip().lower()
        answers_question = str(result.answers_question).strip().lower()
    except Exception as e:
        logger.warning("生成校验不可用，改用引用完整性启发式校验: %s", e)
        cited = {int(x) for x in re.findall(r"\[(\d+)\]", generation)}
        valid_citations = bool(cited) and all(1 <= item <= len(docs) for item in cited)
        has_content = len(generation.strip()) >= 80
        accepted = valid_citations and has_content
        return _finish(
            state, "grade_generation", started,
            {
                "grounded": "heuristic",
                "answers_question": "heuristic",
                "citations": sorted(cited),
                "error": str(e)[:200],
            },
            {
                "verified": accepted,
                "terminated_by": "grade_unavailable",
                "verdict": "useful",
            },
        )

    detail = {"grounded": grounded, "answers_question": answers_question}
    if grounded != "yes":
        if generation_count >= int(config.get("rag.generation_max", 2)):
            return _finish(
                state, "grade_generation", started, detail,
                {"verified": False, "terminated_by": "grounded_failed", "verdict": "give_up"},
            )
        return _finish(
            state, "grade_generation", started, detail,
            {"verified": False, "verdict": "not supported"},
        )

    if answers_question == "yes":
        return _finish(
            state, "grade_generation", started, detail,
            {"verified": True, "terminated_by": "useful", "verdict": "useful"},
        )

    if transform_count >= int(config.get("rag.transform_max", 2)):
        return _finish(
            state, "grade_generation", started, detail,
            {"verified": True, "terminated_by": "rewrite_exhausted", "verdict": "give_up"},
        )
    return _finish(
        state, "grade_generation", started, detail,
        {"verified": True, "verdict": "not useful"},
    )


def generation_decision(state: dict) -> str:
    return str(state.get("verdict") or "give_up")


def transform_query(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("transform_query", "start")
    question = state.get("original_question") or state.get("question", "")
    try:
        runtime.bump_llm()
        better = rewrite_question(question)
    except Exception as e:
        logger.warning("问题改写失败: %s", e)
        better = question
    transform_count = int(state.get("transform_count", 0) or 0) + 1
    return _finish(
        state, "transform_query", started,
        {"rewritten_question": better[:500]},
        {
            "question": better,
            "original_question": question,
            "transform_count": transform_count,
        },
    )


def web_search(state: dict) -> dict:
    started = time.perf_counter()
    runtime.emit_node("web_search", "start")
    question = state.get("question", "")
    try:
        docs = WebSearch().search(question)
    except Exception as e:
        logger.warning("联网搜索失败: %s", e)
        docs = []
    return _finish(
        state, "web_search", started, {"results": len(docs)},
        {
            "documents": docs,
            "route": "web_search",
            "source": "web_search",
        },
    )
