# 芯知 SemiKB · 半导体文档知识库系统

基于 RAG 的半导体文档问答系统。后端分层结构参考 `D:\项目1\ai_service`，检索增强链路参考 `D:\项目1\RAG_PROJECT\graph2`，知识库语料为 `D:\项目1\md` 下的 430 篇技术文档。

当前状态：已完成代码实现、数据库建表、Milvus 建集合、430 篇语料入库、前端构建与端到端联调。可直接启动后端，从 `http://127.0.0.1:8010` 使用问答页与管理台。

## 快速启动

后端：

```powershell
Set-Location D:\项目1\semiconductor_kb
.\.venv\Scripts\python.exe scripts\preflight.py
.\.venv\Scripts\python.exe run.py
```

前端开发模式：

```powershell
Set-Location D:\项目1\semiconductor_kb\frontend
npm install
npm run dev
```

生产模式已经构建到 `semikb\static`，运行后端后直接访问：

- 问答页 `http://127.0.0.1:8010/`
- 引用原文页 `http://127.0.0.1:8010/document/{doc_uid}`
- 管理台 `http://127.0.0.1:8010/admin`
- 接口文档 `http://127.0.0.1:8010/docs`
- 健康检查 `http://127.0.0.1:8010/api/health`

管理台默认账号 `admin`，默认密码 `123456`。数据库口令放在 `.env` 的 `SEMIKB_DB_PASSWORD`，管理员令牌密钥放在 `SEMIKB_ADMIN_SECRET`，不要把明文写进代码或提交到仓库。

## 当前运行状态

| 项 | 实际状态 |
|---|---|
| MySQL | 本机 `127.0.0.1:3306`，MySQL 8.0.42，库 `semi_kb_db` |
| 数据表 | `t_admin`、`t_session`、`t_message`、`t_citation`、`t_document`、`t_ingest_task` |
| Milvus | `http://127.0.0.1:19530`，服务端 3.0.2，SDK `pymilvus 3.0.2` |
| 物理集合 | `semi_kb_chunks_v1`，别名 `semi_kb_chunks` |
| 语料 | 430 篇 Markdown，全部 ready |
| 切片 | 2168 条，MySQL 与 Milvus 实际计数一致 |
| 对话模型 | `qwen-plus`，DashScope OpenAI 兼容接口 |
| 评分模型 | `qwen-plus`，低 token 预算，避免 `qwen-turbo` 限流导致校验失败 |
| 嵌入模型 | `text-embedding-v4`，1024 维 |
| 后端端口 | 8010 |
| 前端开发端口 | 5174，Vite 代理 `/api` 与 WebSocket 到 8010 |

管理台的文档、任务、消息审计三个表格统一使用 `PaginationBar`。数据超过一页时显示首页、上一页、页码、下一页、末页和页码输入跳转，当前页高亮，输入页码后按回车或点跳转都能生效。

问答页左侧新增历史会话列表，桌面端与窄屏端都可切换历史对话。列表中的 `conversation_id` 取该会话首条机器人消息的 id，内部仍用 `session_id` 拉取消息与连接 WebSocket。点击已结束的会话可只读查看历史，输入区会锁定；点击活跃会话会恢复连接。

## 核心实现

问答链路是 LangGraph `StateGraph`，主链路沿用 `graph2`，路由增加直接回答分支：

```text
route_question
      ├─ direct → direct_answer → END
      └─ retrieve → grade_documents → generate → grade_generation
                         ↘ transform_query ↗
                         ↘ web_search     ↗
```

- 路由节点先做半导体关键词短路，命中后直接走本地知识库，减少一次模型调用。
- 问候、感谢、告别、身份或能力询问命中寒暄规则后走 `direct_answer`，不生成查询向量、不检索 Milvus、不调用模型，直接返回简短介绍。管理台问答质量与延迟统计不把这类消息计入分母。
- 检索为稠密向量加 BM25 稀疏向量的混合检索，使用 `AnnSearchRequest` 与 `RRFRanker(k=100)`，候选 20 条，融合取 4 条。
- 文档评分先批量一次，批量失败时逐篇评分；评分模型限流时保留全部召回结果，避免整条链路被外部依赖拖死。
- 生成节点用 `llm.stream` 输出 token，通过线程安全回调推到 WebSocket。
- 生成校验合并 `grounded` 与 `answers_question` 两个判定；校验模型不可用时改用引用完整性启发式校验，回答仍可返回。
- 查询改写最多两次，重新生成最多两次，用户问答外层有 95 秒等待上限；配置中的 12 次模型调用预算当前只统计，不强制中断。
- 回答落库时写入来源、路由、引用、trace、时延、校验状态与用户评价。本地引用的链接统一为 `/document/{doc_uid}`，历史引用读取时也会归一化，点击原文可直接打开只读 Markdown 页面。

入库链路：

- Markdown 标题栈解析，保留层级标题路径，例如 `光刻 > EUV 光源 > 锡液滴`。
- 按语义块切片，默认单切片上限 5000 字符，硬上限 2400，最小 80 字符，重叠 120 字符。
- DashScope 批量嵌入，按 `batch_embed=10` 分批；Milvus 按 `batch_insert=50` 写入。
- 支持单篇上传、单篇重建、删除、全量影子集合重建与别名切换。
- 批量导入脚本支持多线程，`--workers 4` 时 430 篇约一分钟级完成，具体取决于嵌入接口响应。
- 批量导入只在结束时 flush 一次，避免每篇文档都触发一次 Milvus flush。

## 关键环境结论

Milvus 3.0.2 当前服务端没有开启 `common.storage.useLoonFFI`，创建 `TEXT` 字段会报：

```text
TEXT field requires StorageV3; enable common.storage.useLoonFFI
```

因此集合的 `text` 字段实际使用 `VARCHAR(12000)`，分词器为 `jieba`，过滤器为 `cnalphanumonly`，BM25 函数仍可正常工作。设计文档中关于 `TEXT` 的描述属于早期方案，实际实现以本 README 与 `semikb/ingest/milvus_store.py` 为准。

RRF 单路得分上限约为 `1/100`，不要使用 `0.1` 作为阈值，否则会把所有结果过滤掉。检索测试页默认阈值为 0。

## 目录结构

```text
semiconductor_kb/
├─ config/config.json          运行配置
├─ .env                        本地数据库口令与管理员密钥
├─ run.py                      后端启动入口
├─ requirements.txt            Python 依赖
├─ scripts/
│  ├─ init_db.sql              MySQL 建库建表与管理员种子
│  ├─ preflight.py             环境自检
│  ├─ ingest_cli.py            批量导入 Markdown
│  ├─ verify_counts.py         MySQL 与 Milvus 切片数核对
│  └─ ws_smoke_test.py         问答 WebSocket 端到端冒烟测试
├─ data/active_collection.txt  当前 Milvus 物理集合指针
├─ semikb/
│  ├─ main.py                  FastAPI 装配
│  ├─ config 与 common/        配置、常量、异常、日志
│  ├─ dao/                     六个 DAO 与连接池
│  ├─ ingest/                  解析、切片、Milvus 写入、入库流水线
│  ├─ rag/                     LangGraph 状态、节点、检索器、WebSocket 回调
│  ├─ service/                 问答、管理、统计、鉴权、限流、WebSocket 管理
│  ├─ api/                     REST、WebSocket、页面入口
│  └─ static/                  前端生产构建产物
├─ frontend/                   Vue3 + Pinia + Vue Router + Vite
│  ├─ src/views/ChatView.vue   问答页
│  ├─ src/views/admin/         管理台七个面板
│  ├─ src/components/          引用列表、trace 时间线、消息气泡、快捷问题
│  ├─ src/stores/              会话状态与管理台状态
│  ├─ src/sockets/             用户端与管理端 WebSocket 封装
│  └─ dist/                    前端构建结果
└─ docs/
   ├─ 01_架构设计.md
   └─ 02_接口设计.md
```

## 主要接口

用户端：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/chat/sessions` | 新建会话 |
| GET | `/api/chat/sessions` | 历史会话列表，conversation_id 为首条机器人消息 id |
| GET | `/api/chat/sessions/{id}` | 查询会话 |
| GET | `/api/chat/sessions/{id}/messages` | 查历史消息 |
| POST | `/api/chat/sessions/{id}/close` | 结束会话 |
| POST | `/api/chat/messages/{id}/rate` | 评价回答 |
| GET | `/document/{doc_uid}` | 引用原文只读页 |
| WS | `/api/chat/ws/{id}?debug=1` | 流式问答与节点推送 |

管理端：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/admin/login` | 管理员登录 |
| GET | `/api/admin/documents` | 文档列表 |
| GET | `/api/admin/documents/{doc_uid}` | 文档详情 |
| GET | `/api/admin/documents/{doc_uid}/chunks` | 查看切片 |
| POST | `/api/admin/documents/upload` | 上传 Markdown |
| POST | `/api/admin/documents/{doc_uid}/reindex` | 单篇重建 |
| POST | `/api/admin/documents/{doc_uid}/delete` | 删除文档 |
| GET | `/api/admin/tasks` | 入库任务列表 |
| POST | `/api/admin/rebuild` | 全量影子集合重建 |
| POST | `/api/admin/retrieval-test` | 检索调试 |
| POST | `/api/admin/qa-test` | 完整 RAG 链路测试 |
| GET | `/api/admin/stats/overview` | 运营统计 |
| GET | `/api/admin/messages` | 回答审计 |
| WS | `/api/admin/ws?token=...` | 任务与文档状态推送 |

鉴权头使用 `X-Admin-Token`，也兼容 `Authorization: Bearer`。

## 验收命令

环境自检：

```powershell
.\.venv\Scripts\python.exe scripts\preflight.py
```

切片计数核对：

```powershell
.\.venv\Scripts\python.exe scripts/verify_counts.py
```

问答 WebSocket 冒烟测试：

```powershell
.\.venv\Scripts\python.exe scripts\ws_smoke_test.py
```

接口手工验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-RestMethod http://127.0.0.1:8010/api/meta
```

## 前端构建

修改前端后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_frontend.ps1
```

脚本会进入 `frontend` 安装依赖、执行 Vite 构建，并把 `dist` 复制到 `semikb\static`。

## 已知边界

- 只接收 Markdown，不支持 PDF、Word、扫描件与 OCR。
- 没有多租户与细粒度权限，管理台只区分登录与未登录。
- 联网搜索依赖 Tavily 配额，失败时按空结果降级。
- 评分模型和生成模型共用 DashScope 账号，连续高频问答仍可能触发配额限制；代码已做重试、限流处理和引用完整性兜底校验。
- `Milvus get_collection_stats` 可能把已删除数据计入统计，切片核对请使用 `scripts/verify_counts.py` 的 `query count(*)` 结果。
- 全量影子集合重建接口与流水线已实现，但为避免切换当前可用集合，没有对 430 篇语料做破坏性重建演练；需要时可单独执行并验证别名切换。
