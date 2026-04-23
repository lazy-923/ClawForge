# ClawForge 系统设计文档

## 一、文档目的

本文档不是单纯描述“理想架构”，而是基于 **当前仓库实现** 与 **产品目标**，说明 ClawForge 这套系统目前是如何组织、如何运行、各模块如何协作，以及后续应该向什么方向演进。

写作原则采用“先总后分”的结构：

1. 先讲系统整体目标与总分层
2. 再讲两条核心链路
3. 再按模块逐层拆解实现方式
4. 最后说明当前实现与目标形态之间的差距

---

## 二、系统定义

ClawForge 的本质不是“另一个聊天壳”，而是一个面向本地 Agent 的 **Skill Gateway + Skill Evolution 工作台**。

它在既有本地 Agent 基线能力之上，进一步强化了两类关键能力：

- 前台的 **Skill Gateway**
- 后台的 **Skill Evolution**

目标是让 Skill 从静态文件升级为：

- 可检索
- 可激活
- 可沉淀
- 可治理
- 可版本化

系统最终希望做到：

```text
在线请求先命中合适技能
对话结束后提炼可复用技能草稿
草稿进入正式技能库前经过治理
所有关键状态都以本地文件形式可追踪
```

---

## 三、设计原则

## 3.1 本地优先

系统优先依赖本地文件、目录和索引，不依赖外部数据库作为核心真相源。

## 3.2 文件优先

技能、草稿、版本、统计、会话、命中记录都优先落盘为本地工件，而不是隐藏在运行时内存或黑盒服务里。

## 3.3 可观察、可编辑、可审查

用户应该能看到：

- 本轮命中了什么技能
- 为什么命中
- 草稿是怎么生成的
- 为什么被建议 add / merge / ignore
- skill 版本如何变化

## 3.4 半自动演化

ClawForge 不直接自动改写正式技能库，而是采用：

```text
抽取 Draft -> 给出治理建议 -> 人工确认 Promote / Merge
```

## 3.5 兼容既有本地 Agent 主干

当前设计尽量保留 ClawForge 已经具备的本地 Agent 基础形态：

- `SKILL.md` 技能文件
- `workspace/*.md` + relevant memory retrieval 的 Prompt 体系
- 基于工具的 Agent 执行方式
- 本地工作台式前端

---

## 四、系统总览

## 4.1 总体分层

从结构上看，当前系统可以分成六层：

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

## 4.2 两条核心链路

当前系统的运行可以理解成两条主链路并行存在。

### 1. 前台在线链路：Serving Path

负责“这一轮用户请求如何被处理”。

```text
user message
-> session load
-> gateway rewrite / retrieve / select
-> prompt build
-> agent response
-> message persist
```

### 2. 后台学习链路：Learning Path

负责“这一轮交互能不能沉淀成新的技能资产”。

```text
chat done
-> evolution enqueue
-> draft extraction
-> related skill retrieval
-> add / merge / ignore suggestion
-> wait for human governance
-> registry update
```

这两条链路的分离是 ClawForge 的核心设计之一：

- Serving Path 负责在线回答质量
- Learning Path 负责系统的长期演化

---

## 五、核心抽象

## 5.1 Formal Skill

正式技能位于：

```text
backend/skills/<skill_name>/SKILL.md
```

它是系统真正的技能资产，承担以下职责：

- 参与在线检索
- 被注入 Prompt
- 被前端展示
- 被版本管理

## 5.2 Skill Draft

技能草稿位于：

```text
backend/skill_drafts/<draft_id>.md
```

它不是正式技能，而是候选技能工件，承担以下职责：

- 承载从对话抽取出的候选能力
- 保存治理建议与证据
- 等待人工确认 Promote / Merge / Ignore

## 5.3 Skill Registry

技能注册表位于：

```text
backend/skill_registry/
```

它负责保存结构化治理状态，例如：

- `skills_index.json`
- `draft_index.json`
- `usage_stats.json`
- `merge_history.json`
- `lineage.json`

## 5.4 Session

会话是聊天主链路的上下文容器，位于：

```text
backend/sessions/<session_id>.json
```

每个 session 独立维护自己的 `messages` 列表，供后续轮次直接加载。

## 5.5 Memory

Memory 是全局长期记忆，不属于某个单独 session，当前主要来源是：

```text
backend/memory/MEMORY.md
```

它不再作为静态 Prompt 组件全量注入主提示词，而是作为检索源在每轮对话时补充相关片段。

---

## 六、目录结构与模块边界

当前后端关键目录如下：

```text
backend/
├── api/
├── graph/
├── gateway/
├── evolution/
├── retrieval/
├── tools/
├── skills/
├── skill_drafts/
├── skill_registry/
├── sessions/
├── memory/
├── knowledge/
├── storage/
└── workspace/
```

可将其理解为：

- `api/`：接口入口层
- `graph/`：聊天主运行链路
- `gateway/`：技能激活层
- `evolution/`：技能学习与治理层
- `retrieval/`：通用检索底层
- `tools/`：Agent 工具集
- 其余目录：文件工件与持久化状态

---

## 七、模块详细设计

下面按模块逐一说明“这个模块做什么、如何实现、与谁协作”。

## 7.1 启动层：应用入口与初始化

### 目标

应用启动时完成基础环境准备，让后续请求可以直接进入在线链路。

### 主要文件

- `backend/app.py`
- `backend/config.py`

### 当前实现

`backend/app.py` 中的 FastAPI 生命周期负责：

1. 扫描技能目录，读取技能元数据
2. 重建 skill / memory / knowledge 三类索引
3. 初始化 AgentManager
4. 在关闭时清理 `EvolutionRunner` 的挂起任务

它的作用不是承载业务，而是完成：

- 路由注册
- 生命周期管理
- 运行前预热

### 设计说明

这里采用“启动时预建索引”的方式，而不是每次请求都重新扫描，是为了：

- 降低首轮请求延迟
- 保持 skill / memory / knowledge 检索边界统一
- 让后续 Gateway 和 Memory Retrieval 直接可用

---

## 7.2 API 层：外部请求入口

### 目标

把系统能力暴露为稳定接口，同时保持路由层本身足够薄。

### 目录

```text
backend/api/
├── chat.py
├── sessions.py
├── files.py
├── gateway.py
├── drafts.py
├── skills.py
└── health.py
```

### 设计原则

API 层只做三件事：

1. 接收请求与参数校验
2. 调用下层模块
3. 组织 HTTP / SSE 响应

它不负责具体检索逻辑、抽取逻辑和治理逻辑。

### 当前实现说明

#### `chat.py`

聊天主入口，负责：

- 读取或创建 session
- 读取当前 session 历史
- 触发 Skill Gateway
- 调用 AgentManager
- 保存 user / assistant 消息
- 在响应后异步触发 EvolutionRunner

它是连接 Serving Path 与 Learning Path 的关键枢纽。

#### `gateway.py`

用于查询最近一轮的 skill hit，主要服务前端观察性。

#### `drafts.py`

提供 draft 列表、详情、promote / merge / ignore 操作。

#### `skills.py`

提供 lineage、usage、merge-history、stale audit 等技能侧观察接口。

---

## 7.3 Session 子系统：会话与消息持久化

### 目标

把聊天上下文与消息历史稳定地保存为本地文件，让每个 session 自己维护上下文状态。

### 主要文件

- `backend/graph/session_manager.py`

### 当前实现

每个 session 都对应一个 JSON 文件，典型结构为：

```json
{
  "session_id": "...",
  "title": "New Session",
  "created_at": 0,
  "updated_at": 0,
  "messages": []
}
```

它负责：

- 创建 session
- 判断 session 是否存在
- 读取与写回消息
- 自动维护 `updated_at`
- 在首轮对话后生成默认标题

### 设计说明

这里的 `messages` 是 **session 私有上下文**，与 `memory` 完全不同：

- `messages`：只属于当前 session
- `memory`：全局长期记忆

同一个 session 的每轮聊天会带上最近窗口内的 `messages`，不依赖 memory 检索来补 session 历史。超过 `SESSION_HISTORY_MAX_MESSAGES` 的旧消息会被自动压缩进 session `summary`，并在后续请求中以 `[Session Summary]` 补充。

---

## 7.4 Serving Path 总览

Serving Path 负责在线回答，可进一步拆成四个模块：

1. Skill Gateway
2. Prompt Builder
3. Agent Runtime
4. Tools

## 7.4.1 Skill Gateway

### 目标

决定当前这一轮请求应激活哪些技能，而不是把整个技能库塞进 Prompt。

### 目录

```text
backend/gateway/
├── query_rewriter.py
├── skill_retriever.py
├── skill_selector.py
├── skill_context_builder.py
├── skill_indexer.py
└── gateway_manager.py
```

### 整体流程

```text
message + recent history
-> rewrite query
-> retrieve candidate skills
-> select few skills
-> build compact context
-> save last-hit and usage stats
```

### 当前实现说明

#### A. Query Rewrite

文件：

- `backend/gateway/query_rewriter.py`

当前实现方式比较轻量：

- 取最近最多 4 条 user 历史
- 与当前 message 拼接
- 用 `extract_terms()` 提取关键词
- 截断为最多 12 个 term

这属于 **启发式 rewrite**，目标是尽量保留任务锚点，同时过滤噪声。

#### B. Skill Retrieval

文件：

- `backend/gateway/skill_retriever.py`
- `backend/gateway/skill_indexer.py`

`skill_retriever.py` 本身很薄，只负责调用 `skill_indexer.retrieve()`。

真正的核心在 `skill_indexer.py`：

- 将 skill metadata 和正文结构转换为统一检索文档
- 索引字段覆盖 `name / description / tags / triggers / goal / constraints / workflow`
- 使用 `BaseHybridIndexStore` 执行混合检索

#### C. Skill Selection

文件：

- `backend/gateway/skill_selector.py`

当前实现采用规则化过滤：

- 根据 `score` 做阈值过滤
- 默认最多保留 3 个技能
- 为每个命中 skill 生成 `reason`

`reason` 当前主要由以下信息组成：

- retrieval mode
- matched fields
- matched terms

这让前端和调试过程可以看到“为什么命中”。

#### D. Skill Context Injection

文件：

- `backend/gateway/skill_context_builder.py`

当前不是直接把完整 `SKILL.md` 注入 Prompt，而是生成紧凑的文本块：

- skill name
- description
- goal
- reason

这样做的目标是：

- 控制 Prompt 体积
- 保留足够解释信息
- 避免全技能库 Prompt 膨胀

#### E. Gateway Manager

文件：

- `backend/gateway/gateway_manager.py`

它把 rewrite / retrieve / select / context build 串起来，并负责：

- 保存 `last-hit`
- 更新 usage 统计中的 `retrieved_count` 和 `selected_count`

因此它是 Gateway 的编排入口。

### 当前状态判断

当前 Skill Gateway 已经可运行，但仍属于“首版可用”：

- 检索底层已统一
- hit reason 已可观察
- 但 rewrite、selection、样本覆盖仍有继续优化空间

---

## 7.4.2 Prompt Builder

### 目标

把系统的长期上下文与当前命中技能整合为模型可消费的系统提示词。

### 主要文件

- `backend/graph/prompt_builder.py`

### 当前实现

当前 PromptBuilder 会读取以下组件：

- `backend/workspace/SOUL.md`
- `backend/workspace/IDENTITY.md`
- `backend/workspace/USER.md`
- `backend/workspace/AGENTS.md`
- Activated Skills 上下文

最终将它们拼接成一个 system prompt。

### 设计说明

PromptBuilder 的定位不是“智能决策器”，而是“上下文编排器”：

- 它不决定命中什么 skill
- 它只负责把长期上下文和激活 skill 组织起来

---

## 7.4.3 Agent Runtime

### 目标

真正执行本轮请求，输出回答，并在必要时调用工具。

### 主要文件

- `backend/graph/agent.py`

### 当前实现

AgentManager 当前支持两种运行模式：

1. `mock`
2. 兼容 OpenAI API 的 LangChain Agent 模式

它的执行流程大致是：

```text
load memory retrieval
-> build messages
-> create agent
-> invoke agent
-> stream token / retrieval / done
```

### Memory Retrieval 在这里如何发挥作用

每轮请求进入 AgentManager 时，会先调用：

```text
memory_indexer.retrieve(message)
```

如果有命中结果，就作为一条额外的 system message 注入：

```text
[Relevant Memory]
- ...
- ...
```

因此 memory 是 **全局长期记忆补充**，而不是 session history 的替代品。

### 与 session history 的关系

当前 session 的历史消息由 `chat.py -> session_manager.load_session_for_agent()` 读取，然后在 `_build_messages()` 中逐条加入模型输入。

也就是说，当前 Agent 输入同时包含三类上下文：

1. system prompt
2. current session history window plus optional session summary
3. relevant memory retrieval

长期记忆写入需要先进入 memory candidate 队列，只有人工 promote 后才会追加到 `MEMORY.md` 并重建 memory index。

---

## 7.4.4 Tools

### 目标

给 Agent 提供可执行动作，而不把所有能力硬编码到模型本身。

### 目录

```text
backend/tools/
├── terminal_tool.py
├── python_repl_tool.py
├── read_file_tool.py
├── fetch_url_tool.py
├── search_knowledge_tool.py
└── skills_scanner.py
```

### 当前实现说明

#### `terminal_tool.py`

允许在受限范围内执行终端命令。

#### `python_repl_tool.py`

允许执行短 Python 代码。

#### `read_file_tool.py`

读取项目内文件。

#### `fetch_url_tool.py`

抓取网页文本。

#### `search_knowledge_tool.py`

检索 `backend/knowledge/` 中的知识内容。

#### `skills_scanner.py`

扫描 `backend/skills/*/SKILL.md` 并提取 metadata，供 Skill Gateway 索引与技能目录使用。

### 设计说明

工具层的目标不是替代业务模块，而是为 Agent Runtime 提供通用执行能力。

---

## 7.5 Retrieval Layer：统一检索底座

### 目标

让 skill / memory / knowledge 三类内容共享一套统一的混合检索能力，而不是分别维护完全不同的实现。

### 目录

```text
backend/retrieval/
├── text_matcher.py
└── llamaindex_store.py
```

### 当前实现说明

#### `text_matcher.py`

负责：

- 提取 terms
- BM25 分词
- 收集字段 term 集合

它是 rewrite、skill matching、governance matching 的共用基础。

#### `llamaindex_store.py`

这是当前检索层最核心的抽象。

它提供：

- 文档加载
- chunk 切分
- 向量索引持久化
- BM25 索引持久化
- hybrid merge
- fingerprint 检查与自动重建

### 统一抽象方式

当前通过 `BaseHybridIndexStore` 作为统一底座，分别派生出：

- skill 检索
- memory 检索
- knowledge 检索

这样做的好处是：

- 三类检索可以共享核心逻辑
- 后续调优时边界更清晰
- Gateway 与 Memory / Knowledge 检索策略更一致

---

## 7.6 Learning Path 总览

Learning Path 负责在聊天结束后异步分析交互内容，并决定是否形成 draft。

当前可以拆成六个模块：

1. Evolution Runner
2. Draft Extractor
3. Related Skill Finder
4. Skill Judge
5. Skill Merger
6. Promotion / Registry

## 7.6.1 Evolution Runner

### 目标

将 Learning Path 从主聊天链路中解耦，让后台学习不阻塞前台响应。

### 主要文件

- `backend/evolution/evolution_runner.py`

### 当前实现

`EvolutionRunner` 当前维护一个按 session_id 索引的任务表：

- `enqueue()` 创建异步任务
- `run_for_session()` 读取 session 历史并执行 draft 处理
- `wait_for_session()` 可用于本地验证
- `shutdown()` 负责应用关闭时清理

### 设计说明

这个模块当前还不是完整意义上的 `EvolutionAgent`，但已经承担了“后台学习调度器”的角色。

---

## 7.6.2 Draft Extractor

### 目标

从最近多轮对话中识别是否存在可复用、可迁移的技能模式。

### 主要文件

- `backend/evolution/draft_extractor.py`

### 当前实现

当前 Extractor 仍是启发式实现，但已具备首版结构：

- 定义若干 `IntentTemplate`
- 从最近多轮 user messages 中提取 intent signal
- 结合 identity context 判断 dominant intent
- 识别 repeated intent / reusable terms
- 生成结构化 `DraftCandidate`

输出内容包括：

- name
- description
- goal
- constraints
- workflow
- why_extracted
- confidence

### 设计说明

当前实现已经从“单轮关键词触发”升级为“多轮启发式抽取”，但还没有达到真正 `ExtractorSubAgent` 的形态。

后续增强方向应是：

- 更强的多轮归纳
- 更强的 durable / reusable 判定
- 更少的一次性污染

---

## 7.6.3 Draft Service

### 目标

负责将抽取结果落成 Draft 文件与索引记录，并衔接治理链路。

### 主要文件

- `backend/evolution/draft_service.py`

### 当前实现

它负责完成以下动作：

1. 从 recent messages 中寻找 latest user / assistant message
2. 调用 Extractor 获取 `DraftCandidate`
3. 调用 `find_related_skills()`
4. 调用 `judge_draft()`
5. 组织 draft payload
6. 去重检查
7. 写入 Markdown Draft 文件
8. 更新 `draft_index.json`

### 设计说明

它是 Learning Path 里的“落盘与编排中心”，把 Extractor、Related Finder 和 Judge 串起来。

---

## 7.6.4 Related Skill Finder

### 目标

为 Draft 提供治理侧的相似技能证据，而不是在线回答侧的最终技能选择。

### 主要文件

- `backend/evolution/related_skill_finder.py`

### 当前实现

当前实现分两步：

1. 先构造 governance query，并复用 skill retrieval 做召回
2. 再基于 candidate 与每个 formal skill 的 profile 计算治理视图

治理视图中会产生：

- `job_similarity`
- `constraints_similarity`
- `workflow_similarity`
- `governance_score`
- `governance_reason`

### 设计说明

它不是简单复用 Gateway selection，而是：

- 复用 retrieval 召回能力
- 重新按治理目标排序

这使其更适合作为 Judge 的证据层。

---

## 7.6.5 Skill Judge

### 目标

根据 Draft 信号强度和 related skills 证据，判断应当：

- add
- merge
- ignore

### 主要文件

- `backend/evolution/skill_judge.py`

### 当前实现

当前 Judge 属于规则化决策器，核心逻辑包括：

- 若没有 meaningful related skill，则在 `add / ignore` 之间判断
- 若 top skill 与 draft 高度一致，则优先 merge
- 若 governance_score 与 supporting signals 足够强，则 merge
- 若 confidence 与 evidence 都弱，则 ignore
- 否则 add

### 设计说明

它目前不是完整的 `JudgeSubAgent`，但已经把治理判断从“单一 score 阈值”升级到了“多信号综合判断”。

---

## 7.6.6 Skill Merger

### 目标

在 action=merge 时，将 Draft 的可复用内容结构化并入正式 Skill，同时维护版本演化信息。

### 主要文件

- `backend/evolution/skill_merger.py`
- `backend/evolution/skill_versioning.py`

### 当前实现

当前 merge 流程大致如下：

1. 读取目标 skill 文件
2. 解析 frontmatter 和正文结构
3. 提取原有 goal / constraints / workflow
4. 计算新增约束和新增 workflow
5. 执行 patch version bump
6. 生成新的 skill 文本
7. 生成结构化 `merge_patch`
8. 生成 `patch_summary`

`merge_patch` 当前包含：

- from_version / to_version
- goal 变化
- constraints 变化
- workflow 变化
- rollback 保留字段

### 设计说明

当前实现已经不是“把草稿内容简单追加到文件末尾”，而是更接近“结构化版本化合并”。

但它仍属于首版：

- rollback 还只是保留字段
- diff / history 浏览还需要继续补

---

## 7.6.7 Promotion Service

### 目标

把 Draft 的治理动作落实到正式 skill 与注册表上。

### 主要文件

- `backend/evolution/promotion_service.py`

### 当前实现

它负责三类动作：

#### Promote

- 将 Draft 变成新 skill 文件
- 写入 `backend/skills/`
- 更新 draft 状态
- 刷新 skill index
- 更新 usage 与 lineage

#### Merge

- 调用 `merge_draft_into_skill()`
- 更新 draft 状态
- 刷新索引
- 更新 merge history、usage、lineage

#### Ignore

- 仅更新 draft 状态

### 设计说明

PromotionService 是治理动作的执行层，不负责决定 action，而负责确保 action 的副作用完整落盘。

---

## 7.6.8 Registry Service

### 目标

集中维护 skill registry 中的结构化状态文件。

### 主要文件

- `backend/evolution/registry_service.py`

### 当前实现

它负责：

- refresh skills index
- append merge history
- append lineage
- increment usage
- query usage / lineage / merge history / stale skills

### 设计说明

这个模块的价值在于把“治理副作用”集中起来，避免多个模块各自写 JSON 文件造成状态分散和不一致。

---

## 7.7 存储层：文件工件如何组织

### 目标

让系统关键状态都能以“目录 + 文件”的形式落盘。

### 当前目录职责

#### `backend/skills/`

正式技能库，每个 skill 一个目录。

#### `backend/skill_drafts/`

草稿技能 Markdown 文件。

#### `backend/skill_registry/`

结构化治理状态与注册表。

#### `backend/sessions/`

按 session 持久化聊天消息。

#### `backend/memory/`

全局长期记忆文件与 memory candidate 队列。

#### `backend/knowledge/`

供 `search_knowledge_base` 使用的本地知识目录。

#### `backend/storage/`

运行时产物与索引目录，例如：

- gateway hit 记录
- memory index
- knowledge index
- skill index

### 设计说明

这里的核心思想是：**文件工件就是系统状态本身**。

这既有利于：

- 调试
- 回放
- 手工审查
- 后续治理

也意味着设计时要特别重视：

- 文件结构稳定性
- 索引重建能力
- 运行时与工件的一致性

---

## 八、关键运行流程

## 8.1 一轮聊天是如何完成的

```text
frontend submit message
-> POST /api/chat
-> ensure_session()
-> load_session_for_agent()
-> gateway_manager.activate_skills()
-> agent_manager.astream()/collect_response()
-> session_manager.save_message(user)
-> session_manager.save_message(assistant)
-> evolution_runner.enqueue()
```

### 关键点

- 当前 session history 直接参与模型输入
- memory retrieval 作为额外上下文补充
- skill hit 在回答前完成
- evolution 在回答后异步启动

## 8.2 一轮学习是如何完成的

```text
evolution job start
-> load session messages
-> extract draft candidate
-> find related skills
-> judge add/merge/ignore
-> write draft markdown
-> append draft index
-> wait human governance
```

## 8.3 一次治理是如何完成的

```text
frontend choose promote / merge / ignore
-> drafts api
-> promotion_service
-> write skill / update draft
-> refresh index
-> update registry
```

---

## 九、前端配合关系

虽然本文档重点在后端，但当前系统设计本身就是工作台形态，因此前端不是可有可无。

前端当前主要承担三类职责：

1. 驱动聊天与会话切换
2. 展示 skill hit、draft、skill registry 观察结果
3. 提供 promote / merge / ignore 的治理入口

从系统角度看，前端是：

- Serving Path 的观察面板
- Learning Path 的治理入口

而不是一个纯装饰层。

---

## 十、当前实现与目标形态的差距

## 10.1 Skill Gateway

当前已具备统一混合检索底座，但仍需继续增强：

- rewrite 仍偏启发式
- selection 仍偏规则化
- 检索样本和阈值调优还不够

## 10.2 Extractor / Judge / Merger

当前三者都已有首版实现，但还不是真正的后台子智能体：

- Extractor 仍偏模板化
- Judge 仍偏规则判断
- Merger 虽已结构化，但 rollback 未完成

## 10.3 测试与回放

系统已有测试基础，但离“关键路径可稳定回归”还有距离。

这部分是系统从 MVP 走向可靠内测版的关键。

---

## 十一、后续设计演进方向

从设计角度看，后续最重要的不是继续堆新抽象，而是把当前模块继续做实。

## 11.1 先把工程保障补齐

重点：

- Gateway 单元测试
- Draft / Governance 集成测试
- Registry 一致性测试
- 回放与样本验证

## 11.2 再继续增强 Serving Path

重点：

- 更稳的 query rewrite
- 更稳的 retrieval / selection
- 更强的 hit reason 可解释性

## 11.3 再增强 Learning Path

重点：

- 更像抽取器的 Extractor
- 更可靠的 Judge
- 更结构化的 Merger

## 11.4 最后补版本与工作台体验

重点：

- rollback / diff
- lineage 浏览体验
- 更成熟的前端治理界面

---

## 十二、最终系统定义

ClawForge 的最终形态不是“自动偷偷改 Prompt 的系统”，而是：

> **一个面向本地 Agent 的显式技能操作系统：前台负责技能激活，后台负责技能锻造，用户始终可以看到、编辑、治理和演化这些技能。**
