# ClawForge

ClawForge 是一个本地优先、文件驱动的 AI Agent 技能工作台。它把聊天、Prompt 组装、技能激活、长期记忆候选、技能草稿生成、技能治理、版本历史和回滚放在同一个项目里，方便你在本地观察和演化一个 Agent 的技能系统。

当前仓库已经清理为初始化状态：运行数据、测试数据、索引和历史 registry 都不随仓库提交。正式技能库里只保留一个种子技能：`backend/skills/get_weather`。

## 功能概览

- FastAPI 后端，提供 Chat、Session、File、Gateway、Draft、Skill、Memory API。
- Next.js 前端工作台，支持流式聊天、Agent 过程观察、会话管理、草稿治理、记忆候选治理和技能查看。
- 正式技能以 `backend/skills/*/SKILL.md` 文件存在。
- Skill Gateway 会按当前请求检索和筛选相关技能，而不是把全部技能塞进 Prompt。
- 对话结束后会抽取可复用技能草稿，支持人工 promote、merge preview、merge、ignore 和 rollback。
- 对话结束后会抽取长期记忆候选，支持人工 promote 或 ignore。
- 默认使用 BM25 检索；如果配置了 OpenAI-compatible embedding，则会额外启用向量检索。

## 技术栈

| 层级 | 技术 | 作用 |
| --- | --- | --- |
| 后端 | FastAPI + Uvicorn | HTTP API 与 SSE 流式响应 |
| Agent 运行时 | LangChain | OpenAI-compatible Chat API 与工具调用 |
| 检索 | LlamaIndex + BM25 | 技能、记忆、知识库检索 |
| 前端 | Next.js 15 + React 19 | 本地工作台界面 |
| 存储 | 本地文件系统 | Markdown、JSON、索引和 registry 文件 |

## 目录结构

```text
ClawForge/
+-- backend/
|   +-- app.py                 # FastAPI 应用入口和启动初始化
|   +-- config.py              # 环境变量和本地路径配置
|   +-- api/                   # HTTP 路由
|   +-- graph/                 # 会话、Prompt、Agent 运行时、索引
|   +-- gateway/               # 技能检索、筛选和上下文注入
|   +-- evolution/             # 草稿抽取、判断、合并、版本、registry
|   +-- memory_dreaming/       # 长期记忆候选抽取
|   +-- retrieval/             # BM25 / LlamaIndex 检索底座
|   +-- tools/                 # Agent 工具
|   +-- workspace/             # Prompt 组件：SOUL、IDENTITY、USER、AGENTS
|   +-- skills/                # 正式技能；当前种子技能为 get_weather
|   +-- sessions/              # 运行时 session JSON
|   +-- memory/                # 运行时 MEMORY.md 和 memory_candidates.json
|   +-- knowledge/             # 本地知识库文件
|   +-- skill_drafts/          # 运行时技能草稿 Markdown
|   +-- skill_registry/        # 运行时索引、lineage、merge history
|   +-- storage/               # 运行时检索索引和日志
+-- frontend/
|   +-- src/app/               # Next.js 工作台界面
+-- docs/                     # 产品和设计文档
+-- tests/                    # 后端测试与本地验证脚本
```

## 快速开始

### 环境要求

- 推荐 Python 3.11+
- 推荐 Node.js 20+
- OpenAI-compatible Chat API key 可选但推荐配置；不配置时后端会退回 mock / 规则逻辑，真实回答和自动治理质量会受限。

### 1. 克隆项目

```bash
git clone https://github.com/lazy-923/ClawForge.git
cd ClawForge
```

### 2. 配置后端

安装后端依赖：

```bash
pip install -r backend/requirements.txt
```

复制环境变量文件：

```bash
# Windows PowerShell
Copy-Item backend\.env.example backend\.env

# macOS / Linux
cp backend/.env.example backend/.env
```

编辑 `backend/.env`：

```env
APP_PORT=8002
API_PREFIX=/api

# 用于真实 LLM 回复。
# ClawForge 通过 ChatOpenAI 使用 OpenAI-compatible Chat API。
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TEMPERATURE=0.2

# 可选。不配置时，技能 / 记忆 / 知识库检索只使用 BM25。
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
```

这里的 LLM 配置不绑定具体供应商。只要服务兼容 OpenAI Chat API，就可以通过 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 接入。

阿里云百炼 / DashScope 兼容模式示例：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-flash
LLM_TEMPERATURE=0.2

EMBEDDING_API_KEY=your-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
```

Embedding 是可选的。只有同时配置 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` 和 `EMBEDDING_MODEL` 时，系统才会启用 OpenAI-compatible 向量检索；否则项目仍然可以使用 BM25 关键词检索正常运行。

### 3. 启动后端

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8002 --reload
```

后端地址：

- API base: `http://127.0.0.1:8002/api`
- OpenAPI 文档: `http://127.0.0.1:8002/docs`

后端启动时会自动扫描技能、重建 skill / memory / knowledge 索引，并初始化 Agent 运行时。

### 4. 配置前端

```bash
cd frontend
npm install
```

复制前端环境变量文件：

```bash
# Windows PowerShell
Copy-Item .env.example .env.local

# macOS / Linux
cp .env.example .env.local
```

默认前端 API 配置：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8002/api
```

### 5. 启动前端

```bash
npm run dev
```

打开：

```text
http://localhost:3000
```

## 种子技能

初始化仓库只保留一个正式技能：

```text
backend/skills/get_weather/SKILL.md
```

该技能用于按城市查询天气，并要求 Agent 用四个固定部分回答：

- `Weather Overview`
- `Clothing Advice`
- `Travel Risk`
- `Suitable Photography Time`

## 主要运行链路

```text
user message
-> session_manager.ensure_session()
-> query_rewriter
-> skill_retriever
-> skill_selector
-> skill context injection
-> agent runtime
-> save user / assistant messages
-> memory dreaming
-> evolution runner
```

流式聊天 API 会发送 process、skill hit、token、title、done 等事件，前端据此展示 Agent 运行过程和流式回答。

## 技能学习链路

```text
chat done
-> draft extractor
-> related skill finder
-> skill judge
-> write draft markdown
-> frontend governance
-> promote / merge-preview / merge / ignore
-> registry, lineage, merge history, and index refresh
```

如果配置了 LLM，`skill_judge.py` 会优先使用 LLM 判断草稿应该 add、merge 还是 ignore。LLM 不可用时会退回规则判断。合并前会生成 snapshot，因此后续可以 rollback。

## 长期记忆链路

```text
chat done
-> dreaming_service.extract_candidates_for_session()
-> memory_candidates.json
-> pending candidate
-> manual promote / ignore
-> MEMORY.md
-> memory index rebuild
```

长期记忆不会整文件注入每一轮 Prompt。系统会按当前 message 检索相关记忆片段，并只把命中的片段作为 `[Relevant Memory]` 注入。

## 主要 API

| API | 作用 |
| --- | --- |
| `POST /api/chat` | 聊天入口，支持 JSON 或 SSE 流式响应 |
| `GET /api/sessions` | 获取 session 列表 |
| `POST /api/sessions` | 创建 session |
| `DELETE /api/sessions/{session_id}` | 删除 session |
| `GET /api/drafts` | 获取技能草稿列表 |
| `POST /api/drafts/{draft_id}/merge-preview` | 预览草稿合并 |
| `POST /api/drafts/{draft_id}/promote` | 将草稿提升为正式技能 |
| `POST /api/drafts/{draft_id}/merge` | 合并草稿到正式技能 |
| `POST /api/drafts/{draft_id}/ignore` | 忽略草稿 |
| `GET /api/skills` | 获取正式技能列表 |
| `GET /api/skills/{skill_name}/lineage` | 查看技能 lineage |
| `GET /api/skills/{skill_name}/merge-history` | 查看技能合并历史 |
| `POST /api/skills/{skill_name}/rollback` | 回滚最近一次可回滚合并 |
| `GET /api/memory/candidates` | 获取记忆候选列表 |
| `POST /api/memory/candidates` | 创建记忆候选 |
| `POST /api/memory/candidates/{candidate_id}/promote` | 提升记忆候选 |
| `POST /api/memory/candidates/{candidate_id}/ignore` | 忽略记忆候选 |

## 测试

后端测试：

```bash
pytest tests
```

前端检查：

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:smoke
npm run test:e2e
```

`npm run test:smoke` 需要先启动后端。

## 运行数据

运行时生成的数据不会进入 Git。常见运行路径包括：

```text
backend/.test-tmp/
backend/memory/MEMORY.md
backend/memory/memory_candidates.json
backend/storage/*
backend/skill_registry/*.json
backend/skill_registry/snapshots/
backend/sessions/*.json
backend/skill_drafts/*.md
```

仓库通过 `.gitkeep` 保留这些目录，clone 后目录结构仍然存在。

## 文档

`docs/` 目录只保留适合公开展示的系统设计材料。README 以当前代码实现和运行方式为准。

- [系统设计文档](./docs/ClawForge%20系统设计文档.md)

## 当前定位

ClawForge 目前是一个单用户、本地优先的 Agent 技能工作台，不是多租户生产服务。技能来自文件，激活来自检索，持久化变更需要经过治理后才进入正式技能库。
