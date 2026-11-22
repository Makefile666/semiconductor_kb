"""Markdown 解析与切片。

优先使用 unstructured 的 MarkdownLoader；不可用时退回自研的标题栈解析器，
保证离线与依赖异常时仍能入库。两种实现都输出相同结构：
{"text", "title", "category_depth", "chunk_index"}
"""
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from semikb.common.config import Config
from semikb.common.logger import get_logger

logger = get_logger(__name__)


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_with_heading_stack(text: str, fallback_title: str) -> list[dict]:
    lines = text.splitlines()
    stack: list[tuple[int, str]] = []
    blocks: list[dict] = []
    current_lines: list[str] = []
    current_title = fallback_title
    current_depth = 0

    def flush():
        nonlocal current_lines
        body = _clean("\n".join(current_lines))
        if body:
            # 只有标题行、没有正文的块直接丢掉，避免产生 20 字的空切片。
            if len(body) <= len(current_title) + 4 and body.startswith(current_title):
                current_lines = []
                return
            blocks.append(
                {
                    "text": body,
                    "title": current_title,
                    "category_depth": current_depth,
                }
            )
        current_lines = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            stack = [(lv, tx) for lv, tx in stack if lv < level]
            stack.append((level, title))
            current_title = " > ".join(tx for _, tx in stack)
            current_depth = len(stack)
            current_lines = [current_title, ""]
        else:
            current_lines.append(line)
    flush()
    return blocks


def _parse_with_unstructured(path: Path, fallback_title: str) -> list[dict]:
    from langchain_community.document_loaders import UnstructuredMarkdownLoader

    loader = UnstructuredMarkdownLoader(
        file_path=str(path), mode="elements", strategy="fast"
    )
    docs = list(loader.lazy_load())
    if not docs:
        return []
    blocks: list[dict] = []
    stack: list[tuple[int, str]] = []
    for doc in docs:
        category = (doc.metadata or {}).get("category", "")
        content = _clean(doc.page_content or "")
        if not content:
            continue
        if category == "Title":
            level = 1
            stack.append((level, content))
            title = " > ".join(tx for _, tx in stack)
            blocks.append({"text": title, "title": title, "category_depth": len(stack)})
        else:
            title = " > ".join(tx for _, tx in stack) or fallback_title
            blocks.append({"text": content, "title": title, "category_depth": len(stack)})
    return blocks


def parse_markdown(path: Path) -> tuple[str, list[dict]]:
    text = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    first_heading = next(
        (m.group(2).strip() for m in re.finditer(r"^(#{1,6})\s+(.*)$", text, re.M)),
        "",
    )
    title = first_heading or path.stem
    blocks: list[dict] = []
    blocks = _parse_with_heading_stack(text, title)
    if not blocks:
        try:
            blocks = _parse_with_unstructured(path, title)
        except Exception as e:
            logger.warning("unstructured 解析失败: %s", e)
    if not blocks:
        blocks = [{"text": text, "title": title, "category_depth": 0}] if text else []
    return title[:255], blocks


class MarkdownChunker:
    def __init__(self):
        self.config = Config.instance()
        self.char_limit = int(self.config.get("ingest.chunk_char_limit", 5000))
        self.hard_max = int(self.config.get("ingest.chunk_hard_max", 2400))
        self.overlap = int(self.config.get("ingest.chunk_overlap", 120))
        self.min_chars = int(self.config.get("ingest.min_chunk_chars", 80))
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.hard_max,
            chunk_overlap=self.overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
            keep_separator=True,
        )

    def split(self, blocks: list[dict]) -> list[dict]:
        output: list[dict] = []
        for block in blocks:
            body = _clean(block["text"])
            if not body:
                continue
            parts = [body] if len(body) <= self.char_limit else self.splitter.split_text(body)
            for part in parts:
                part = _clean(part)
                if not part:
                    continue
                if len(part) < self.min_chars and output:
                    output[-1]["text"] = output[-1]["text"] + "\n\n" + part
                    continue
                output.append(
                    {
                        "text": part,
                        "title": block["title"],
                        "category_depth": int(block["category_depth"]),
                    }
                )
        for index, item in enumerate(output):
            item["chunk_index"] = index
        return output
