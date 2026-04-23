# ClawForge

ClawForge 是一个本地优先、文件驱动、透明可控的 AI Agent 技能工作台。

它把本地 Agent 的几类核心能力统一到一个项目里：

- 会话与聊天
- Prompt 文件组装
- 长期记忆与知识检索
- 工具驱动执行
- Skill Gateway
- Skill Draft 生成
- Skill Governance
- Skill Versioning
- 前端工作台观察与治理

它的目标不是只做一个“会聊天”的应用，而是把请求处理、技能激活、经验沉淀、技能治理和版本演化放进同一套本地系统中。

## 项目定位

ClawForge 面向的是一种可长期使用、可持续演进的本地 Agent 工作方式。

系统主要解决四类问题：

1. 当前这轮请求到底该激活哪些技能
2. 对话中暴露出的稳定做事方式如何沉淀为技能草稿
3. 草稿如何进入正式技能库而不污染已有技能
4. 技能的使用、合并、版本和来源如何被持续追踪

因此，ClawForge 的核心目标不是“堆更多 Prompt”，而是建设一个：

```text
可检索
可激活
可沉淀
可治理
可版本化
```

的本地技能系统。

## 技术选型

| 层级 | 技术 | 说明 |
| --- | --- | --- |
| 后端框架 | FastAPI + Uvicorn | 异步 HTTP 与 SSE 流式响应 |
| Agent 引擎 | LangChain `create_agent` | 兼容工具驱动 Agent 运行时 |
| 模型接口 | OpenAI-compatible Chat API | 默认可走 `mock`，也可接兼容 OpenAI 的 LLM 服务 |
| 检索 | LlamaIndex Core + BM25 | 混合检索底座，用于 skill / memory / knowledge |
| Embedding | OpenAI-compatible Embedding API | 默认模型为 `text-embedding-3-small` |
| 前端框架 | Next.js 15 + React 19 | 本地工作台 UI |
| 存储 | 本地文件系统 | Markdown + JSON + 本地索引目录 |

## 当前能力

当前仓库已经不是脚手架状态，而是具备一套可运行的 MVP 主链路。

### 后端已具备

- FastAPI 应用入口与生命周期初始化
- Chat / Sessions / Files / Gateway / Drafts / Skills API
- Session 持久化
- Prompt 组装
- Memory 检索
- Knowledge 检索
- 工具驱动 Agent 运行时
- Skill Gateway 首版
- Skill Draft 生成首版
- Promote / Merge / Ignore 治理闭环
- Usage / Lineage / Merge History / Stale Audit

### 前端已具备

- Session 列表与切换
- Chat 面板
- SSE 流式消息展示
- Activated Skills 面板
- Session Drafts 面板
- Draft Governance 操作
- Draft / Skill Inspector
- Usage / Lineage / Stale Audit 展示

## 项目结构

```text
ClawForge/
├── backend/
│   ├── app.py                 # FastAPI 入口，生命周期初始化
│   ├── config.py              # 环境变量与路径配置
│   ├── api/                   # API 路由层
│   ├── graph/                 # 会话、Prompt、Agent 主链路
│   ├── gateway/               # 技能激活链路
│   ├── evolution/             # 技能学习与治理链路
│   ├── retrieval/             # 通用检索底座
│   ├── tools/                 # Agent 可调用工具
│   ├── workspace/             # Prompt 组件文件
│   ├── memory/                # 长期记忆
│   ├── knowledge/             # 本地知识库
│   ├── sessions/              # 会话 JSON
│   ├── skills/                # 正式技能
│   ├── skill_drafts/          # 技能草稿
│   ├── skill_registry/        # 索引、统计、历史
│   └── storage/               # 索引和运行时状态
├── frontend/
│   └── src/
│       └── app/               # Next.js 页面与样式
├── docs/                      # PRD、系统设计、开发计划等文档
└── tests/                     # 测试与本地验证脚本
```

## 环境配置

后端配置来自 `backend/.env`，默认通过 `backend/config.py` 读取。

关键配置包括：

- `APP_HOST` / `APP_PORT`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `EMBEDDING_API_KEY`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`

如果没有配置可用 LLM，系统会自动退回 `mock` 模式。

## 启动方式

推荐使用本地 conda 环境：

```bash
conda activate mini-claw
```

### 启动后端

```bash
pip install -r backend/requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8002 --reload
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 前端配置

```bash
copy frontend\\.env.example frontend\\.env.local
```

如果后端地址不是 `http://127.0.0.1:8002/api`，可以在 `frontend/.env.local` 中修改 `NEXT_PUBLIC_API_BASE_URL`。

### 前端验证

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:smoke
npm run test:e2e
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8002`

## 系统全景

系统整体可以理解成六层：

```text
Frontend Workspace
    |
API Layer
    |
Serving Layer
    |- Session & Chat Flow
    |- Skill Gateway
    |- Prompt Builder
    |- Agent Runtime
    |- Tools
    |
Learning Layer
    |- Evolution Runner
    |- Draft Extractor
    |- Related Skill Finder
    |- Skill Judge
    |- Skill Merger
    |- Promotion / Registry
    |
Retrieval Layer
    |- text matcher
    |- llamaindex hybrid store
    |
Storage Layer
    |- skills/
    |- skill_drafts/
    |- skill_registry/
    |- sessions/
    |- memory/
    |- knowledge/
    |- storage/
```

## 两条核心链路

### 1. 在线链路：Serving Path

每轮请求先走技能激活链路，再进入 Agent：

```text
user message
-> session load
-> query rewrite
-> skill retrieval
-> skill selection
-> skill context injection
-> agent response
-> message persist
```

### 2. 后台链路：Learning Path

每轮对话结束后，再异步分析是否应沉淀为技能草稿：

```text
chat done
-> evolution enqueue
-> draft extraction
-> related skill retrieval
-> add / merge / ignore suggestion
-> wait for governance action
-> registry update
```

## 后端架构详解

## 1. 应用入口 `backend/app.py`

启动时通过 FastAPI lifespan 完成几件初始化工作：

1. 扫描 `skills/` 目录，读取技能元数据
2. 重建 skill / memory / knowledge 三类索引
3. 初始化 AgentManager
4. 在关闭时清理 `EvolutionRunner` 挂起任务

这样做的目的是让：

- Skill Gateway 直接可用
- Memory 与 Knowledge 检索直接可用
- Agent 每次请求都建立在最新文件状态上

## 2. API 层 `backend/api/`

API 层负责接住前端请求，并调用下层模块。

当前主要路由包括：

- `chat.py`：聊天主入口
- `sessions.py`：会话管理
- `files.py`：文件读取与保存
- `gateway.py`：最近一轮 skill hit 查询
- `drafts.py`：draft 列表、详情与治理
- `skills.py`：usage、lineage、merge-history、stale audit
- `health.py`：健康检查

其中 `POST /api/chat` 是最核心的接口，它负责：

1. 创建或读取 session
2. 读取当前 session 历史
3. 执行 Skill Gateway
4. 调用 AgentManager
5. 以 JSON 或 SSE 返回结果
6. 保存 user / assistant 消息
7. 异步触发 EvolutionRunner

## 3. Session 管理 `backend/graph/session_manager.py`

每个 session 都对应一个本地 JSON 文件：

```text
backend/sessions/<session_id>.json
```

它负责：

- 创建 session
- 判断 session 是否存在
- 读取会话
- 保存消息
- 维护 `updated_at`
- 在首轮对话后生成默认标题

当前实现中，同一个 session 的历史消息会在后续轮次直接带入 Agent 输入，不依赖 memory 检索来补历史。

## 4. Prompt Builder `backend/graph/prompt_builder.py`

系统每次调用 Agent 前，都会重新读取并拼装 Prompt 组件。

当前会读取：

- `workspace/SOUL.md`
- `workspace/IDENTITY.md`
- `workspace/USER.md`
- `workspace/AGENTS.md`
- `memory/MEMORY.md`
- Skill Gateway 本轮激活的 Activated Skills 上下文

这样做的好处是：

- 工作区文件一改，下一次请求立刻生效
- 只有 Gateway 改写、检索、筛选后的相关技能进入上下文
- 长期记忆和系统约束始终是最新的

## 5. Agent Runtime `backend/graph/agent.py`

AgentManager 当前支持两种模式：

1. `mock`
2. 兼容 OpenAI API 的 LangChain Agent 模式

每轮调用时，它会：

1. 先执行 memory retrieval
2. 再组装 messages
3. 创建 Agent
4. 调用模型并流式返回结果

在流式场景下，前端能接收到的事件类型包括：

- `skill_hit`
- `retrieval`
- `token`
- `done`

## 6. Skill Gateway `backend/gateway/`

Skill Gateway 负责决定“当前请求到底该激活哪些技能”。

模块拆分如下：

- `query_rewriter.py`：把消息和最近历史压缩成检索 query
- `skill_retriever.py`：调用 skill index 做候选召回
- `skill_selector.py`：按分数和证据筛选技能
- `skill_context_builder.py`：生成紧凑的 Activated Skills 文本块
- `skill_indexer.py`：把 skill 转成统一检索文档并建立索引
- `gateway_manager.py`：串起整条链路，并写入 last-hit 与 usage 统计

Gateway 的核心目标是：

- 不把全量技能塞进 Prompt
- 只保留少量相关技能
- 让命中结果可解释

## 7. Evolution `backend/evolution/`

这部分负责对话后的技能沉淀与治理。

当前模块包括：

- `evolution_runner.py`：后台异步调度
- `draft_extractor.py`：从最近多轮对话提取 DraftCandidate
- `draft_service.py`：落盘 draft 并串起相关治理逻辑
- `related_skill_finder.py`：寻找相似正式技能
- `skill_judge.py`：判断 add / merge / ignore
- `skill_merger.py`：结构化合并到 skill 文件
- `skill_versioning.py`：版本号与 rollback 保留字段
- `promotion_service.py`：执行 promote / merge / ignore
- `registry_service.py`：维护 registry JSON 文件

它的目标不是自动无脑写库，而是：

```text
抽取
-> 判断
-> 给建议
-> 等待人工治理
-> 更新索引和历史
```

## 记忆系统

ClawForge 的记忆不是单一概念，而是三层结构。

### 1. Session Memory

也就是当前 session 的 `messages`。

它负责：

- 维持同一会话的上下文连续性
- 保存用户消息与助手消息
- 为后续轮次直接提供历史

### 2. Long-term Memory

也就是：

```text
backend/memory/MEMORY.md
```

它既会作为静态 Prompt 组件被读取，也会在每轮请求时做一次检索补充。

### 3. Knowledge Memory

也就是：

```text
backend/knowledge/
```

它用于存放本地知识文档，主要通过 `search_knowledge_base` 工具按需检索。

### 当前记忆工作方式

每轮对话时，Agent 输入中同时可能包含三种上下文：

1. 当前 session 的历史消息
2. `MEMORY.md` 的静态内容
3. 当前 message 触发的 relevant memory retrieval

这三者并不互相替代。

## 核心工具

当前 Agent 内置五个核心工具：

| 工具 | 文件 | 作用 |
| --- | --- | --- |
| `terminal` | `terminal_tool.py` | 在项目工作区内执行终端命令 |
| `python_repl` | `python_repl_tool.py` | 执行短 Python 代码 |
| `fetch_url` | `fetch_url_tool.py` | 抓取网页或 HTTP 资源 |
| `read_file` | `read_file_tool.py` | 读取项目内文件 |
| `search_knowledge_base` | `search_knowledge_tool.py` | 检索本地知识库 |

此外还有一个关键辅助模块：

- `skills_scanner.py`：扫描 `skills/*/SKILL.md` 并提取 metadata，供 Skill Gateway 索引与技能目录使用

工具系统的核心意义是：

- Skill 本身不是硬编码函数
- Skill 是指导 Agent 如何组合使用工具的说明书
- Agent 读取 skill 后，再用工具真正执行任务

## 检索系统

当前 skill / memory / knowledge 三类检索共用统一底座：

- `backend/retrieval/text_matcher.py`
- `backend/retrieval/llamaindex_store.py`

底层能力包括：

- term 抽取
- BM25 检索
- 向量检索
- hybrid merge
- 索引持久化
- fingerprint 变化检测与自动重建

这让三类检索可以共享逻辑，同时保持各自的索引边界。

## 前端架构概览

前端当前是一个基于 Next.js 的本地工作台。

当前真实目录很轻：

```text
frontend/src/app/
├── layout.tsx
├── page.tsx
└── globals.css
```

职责上它承担三类事情：

1. 聊天与会话切换
2. 展示 skill hit、draft、usage、lineage、stale audit
3. 提供治理入口和 Inspector 视图

虽然实现上目前仍偏“联调工作台”，但它已经是系统的重要观察与治理界面，而不是单纯展示页。

## 核心数据流

### 用户发送一条消息

```text
前端
-> POST /api/chat
-> session_manager.ensure_session()
-> session_manager.load_session_for_agent()
-> gateway_manager.activate_skills()
-> agent_manager.astream()/collect_response()
-> session_manager.save_message(user)
-> session_manager.save_message(assistant)
-> evolution_runner.enqueue()
-> 前端更新消息与面板
```

### Memory 在请求中的作用

```text
user message
-> memory_indexer.retrieve(message)
-> 命中的 memory 片段作为 [Relevant Memory] 注入
-> 仅参与本次请求，不替代 session history
```

### Draft 生成与治理

```text
chat done
-> evolution runner
-> draft extractor
-> related skill finder
-> skill judge
-> write draft markdown
-> update draft_index.json
-> frontend 展示 draft
-> user choose promote / merge / ignore
-> promotion service
-> refresh registry and indexes
```

## 关键设计决策

| 决策 | 理由 |
| --- | --- |
| 文件驱动而非数据库 | 所有状态对开发者透明可查 |
| 每次请求重建 Prompt 组件 | workspace / memory / skill 修改后可立即生效 |
| Skill Gateway 与 Learning Path 分离 | 在线回答与长期演化职责不同 |
| 技能是 Markdown 工件 | 保持技能可读、可编辑、可治理 |
| memory retrieval 结果不持久化到 session | 避免会话文件膨胀 |
| skill / memory / knowledge 共用统一检索底座 | 保持检索策略一致、便于演进 |
| Promote / Merge 需要人工确认 | 防止技能库自动污染 |

## 当前开发重点

当前项目最需要的不是继续堆新模块，而是把已经落地的主链路做稳。

当前主线主要有三件事：

1. 补测试体系，把关键链路做成可持续回归
2. 继续提升 Skill Gateway 的命中质量和解释性
3. 继续提升 Draft Extractor、Judge、Merger 的治理质量

## 文档入口

如果你想快速理解项目，建议从这几份文档开始：

- [产品需求文档](./docs/ClawForge%20产品需求文档.md)
- [系统设计文档](./docs/ClawForge%20系统设计文档.md)
- [开发计划](./docs/ClawForge%20项目开发计划.md)

## 最终一句话

ClawForge 的目标不是做一个“只会聊天”的 Agent，而是做一个能够把 **显式技能、技能激活、技能草稿、技能治理和技能演化** 统一起来的本地 Agent 技能工作台。
