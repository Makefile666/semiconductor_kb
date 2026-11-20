"""页面入口。"""
import html
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from semikb.common.config import PROJECT_ROOT
from semikb.dao.document_dao import DocumentDao

router = APIRouter(tags=["pages"])
STATIC_INDEX = PROJECT_ROOT / "semikb" / "static" / "index.html"


def _fallback() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
        <title>芯知 SemiKB</title><style>
        body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f5f7fb;color:#14213d;
        display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
        .card{max-width:680px;padding:40px;background:#fff;border-radius:20px;box-shadow:0 18px 50px rgba(20,33,61,.12)}
        h1{margin:0 0 12px;font-size:30px} p{line-height:1.8;color:#4b5563}
        code{background:#eef2ff;padding:4px 8px;border-radius:6px}
        a{color:#2563eb;text-decoration:none}
        </style></head><body><div class="card"><h1>芯知 SemiKB</h1>
        <p>前端还没有构建。先在 <code>frontend</code> 目录执行 <code>npm install &amp;&amp; npm run build</code>，
        或开发时执行 <code>npm run dev</code> 打开 5174 端口。</p>
        <p>后端接口文档：<a href="/docs">/docs</a>　健康检查：<a href="/api/health">/api/health</a></p>
        </div></body></html>"""
    )


@router.get("/")
def index():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return _fallback()


@router.get("/admin")
def admin_page():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return _fallback()


def _doc_not_found(message: str = "文档不存在或已删除") -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
        <title>文档未找到 · 芯知 SemiKB</title><style>
        body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f5f7fb;color:#14213d;
        display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
        .card{{max-width:640px;padding:36px;background:#fff;border-radius:18px;box-shadow:0 18px 50px rgba(20,33,61,.12)}}
        h1{{margin:0 0 10px;font-size:24px}} p{{line-height:1.8;color:#4b5563}} a{{color:#2563eb;text-decoration:none}}
        </style></head><body><div class="card"><h1>没有找到这份原文</h1>
        <p>{html.escape(message)}</p><p><a href="/">返回问答页</a></p></div></body></html>""",
        status_code=404,
    )


@router.get("/document/{doc_uid}", response_class=HTMLResponse)
def document_view(doc_uid: str):
    row = DocumentDao().get(doc_uid)
    if not row or row.get("status") == "deleted":
        return _doc_not_found()
    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    try:
        source_path = source_path.resolve()
    except OSError:
        return _doc_not_found()
    if source_path.suffix.lower() not in {".md", ".markdown"} or not source_path.is_file():
        return _doc_not_found()
    try:
        content = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = source_path.read_text(encoding="utf-8", errors="replace")
    title = str(row.get("title") or row.get("filename") or "未命名文档")
    filename = str(row.get("filename") or source_path.name)
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 芯知 SemiKB</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f5f7fb;color:#14213d;font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.shell{{max-width:960px;margin:0 auto;padding:28px 24px 56px}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px;font-size:13px;color:#5d6b82}}
.top a{{color:#1d4ed8;text-decoration:none;font-weight:600}}
.doc{{background:#fff;border:1px solid #e8edf5;border-radius:18px;box-shadow:0 18px 50px rgba(20,33,61,.08);padding:36px 42px}}
.eyebrow{{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#7c8aa0;font-weight:700}}
h1{{font-size:26px;line-height:1.4;margin:8px 0 6px}} .filename{{font-size:12px;color:#7c8aa0;font-family:"Cascadia Code",Consolas,monospace}}
.content{{margin-top:26px;padding-top:24px;border-top:1px dashed #dbe4f0;white-space:pre-wrap;overflow-wrap:anywhere;
font-family:"Cascadia Code",Consolas,"Microsoft YaHei",monospace;font-size:13px;line-height:1.9;color:#334155}}
</style></head><body><main class="shell"><div class="top"><a href="/">← 返回问答页</a><span>原文 · 只读</span></div>
<section class="doc"><div class="eyebrow">Semiconductor Knowledge Base</div>
<h1>{html.escape(title)}</h1><div class="filename">{html.escape(filename)}</div>
<div class="content">{html.escape(content)}</div></section></main></body></html>"""
    return HTMLResponse(page, headers={"Cache-Control": "private, max-age=300"})


@router.get("/favicon.ico")
def favicon():
    return HTMLResponse(status_code=204)
