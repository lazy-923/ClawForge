# ClawForge 系统设计文档

## 一、系统目标

ClawForge 的系统目标，是在 Mini-Claw 已有架构基础上增加一层 **Skill Gateway** 和一条 **Skill Evolution** 后台链路，使 Skill 从静态文件升级为可检索、可演化、可治理的显式工件。

系统设计必须满足以下原则：

1. 本地优先
2. 文件优先
3. 可观察
4. 可编辑
5. 半自动演化
6. 不破坏现有 Mini-Claw 的主干结构

---

## 二、设计原则

### 1. 保留 Mini-Claw 的核心特征

以下设计必须继承：

- `SKILL.md` 文件工件
- `skills/` 目录结构
- `workspace/*.md` + `MEMORY.md` 的 Prompt 组装体系
- 工具驱动的 instruction-following 风格
- 前端三栏工作台

### 2. 不采用“全自动技能入库”

ClawForge 不直接自动修改正式技能库，而是采用：

```text
自动抽取 Draft + 自动给建议 + 人工确认 Promote / Merge
```

### 3. 前台与后台分离

前台只负责：

- 技能激活
- 技能注入
- 对话执行

后台只负责：

- 技能草稿生成
- 技能治理建议
- 技能版本演化

---

## 三、核心抽象

## 3.1 正式技能（Formal Skill）

正式技能是可被系统检索和激活的技能工件，位于：

```text
backend/skills/<skill_name>/SKILL.md
```

正式技能的职责：

- 参与在线检索
- 被注入 Prompt
- 被前端展示
- 被版本管理

## 3.2 技能草稿（Skill Draft）

Skill Draft 是从真实交互中提取出的候选技能，不直接进入正式技能库，位于：

```text
backend/skill_drafts/<draft_id>.md
```

草稿职责：

- 承载抽取结果
- 等待治理
- 可审查与编辑

## 3.3 技能注册表（Skill Registry）

用于记录技能状态与治理信息，位于：

```text
backend/skill_registry/
```

包含：

- 技能索引
- 使用统计
- merge 历史
- lineage 信息
- draft 状态

## 3.4 Skill Gateway

Skill Gateway 是聊天主链路中的前置层，职责是：

- 改写 skill query
- 检索 skill
- 选择 skill
- 构建 skill context

## 3.5 Skill Evolution

Skill Evolution 是对话后的异步学习链路，职责是：

- 抽取 skill draft
- 检索相似 skill
- 生成治理建议
- 触发 promote / merge

---

## 四、系统总体架构

## 4.1 总体分层

```text
Frontend Workspace
    |
API Layer
    |
Serving Layer
    |- Chat API
    |- Skill Gateway
    |- Agent Runtime
    |
Learning Layer
    |- Draft Extractor
    |- Judge
    |- Merger
    |- Promotion Service
    |
Storage Layer
    |- sessions/
    |- memory/
    |- skills/
    |- skill_drafts/
    |- skill_registry/
    |- storage/
```

## 4.2 前后台双路径

### 前台路径：Serving Path

```text
user query
-> query rewrite
-> skill retrieval
-> skill selection
-> prompt injection
-> agent response
```

### 后台路径：Learning Path

```text
conversation turn end
-> draft extraction
-> related skill retrieval
-> add/merge/ignore suggestion
-> wait for promote decision
```

---

## 五、目录结构设计

建议在现有仓库基础上新增如下目录：

```text
backend/
├── gateway/
│   ├── query_rewriter.py
│   ├── skill_retriever.py
│   ├── skill_selector.py
│   ├── skill_context_builder.py
│   └── gateway_manager.py
├── evolution/
│   ├── draft_extractor.py
│   ├── related_skill_finder.py
│   ├── skill_judge.py
│   ├── skill_merger.py
│   ├── skill_versioning.py
│   └── promotion_service.py
├── skill_drafts/
├── skill_registry/
│   ├── skills_index.json
│   ├── draft_index.json
│   ├── usage_stats.json
│   ├── merge_history.json
│   └── lineage.json
└── api/
    ├── gateway.py
    └── drafts.py
```

---

## 六、Skill 文件规范

## 6.1 正式技能文件

仍采用 `SKILL.md` 格式，但建议从“纯步骤说明”升级为更结构化的形式：

```markdown
---
name: professional_rewrite
description: 用专业、清晰、克制的风格重写文本
version: 0.1.0
tags:
  - writing
  - rewrite
triggers:
  - 改写
  - 润色
  - 专业表达
---

# Goal
将用户提供的文本改写为更专业、更清晰的表达。

# Constraints & Style
- 保持原意
- 不夸张
- 避免空话

# Workflow
1. 识别原文目标
2. 保留关键信息
3. 优化表达
```

## 6.2 Skill Draft 文件

Draft 文件建议单独使用 `DRAFT.md` 风格结构，但仍存为 Markdown。

示例：

```markdown
---
draft_id: draft_20260412_001
source_session_id: s_abc123
confidence: 0.82
recommended_action: merge
related_skill: professional_rewrite
status: pending
---

# Draft Name
professional_rewrite_for_brief_reports

# Why Extracted
用户多次要求“简洁、专业、像机构汇报材料”。

# Goal
...

# Constraints & Style
...

# Evidence
- user: ...
- user: ...
```

---

## 七、前台主链路设计

## 7.1 在线对话流程

```text
POST /api/chat
-> SessionManager 读取历史
-> GatewayManager.activate_skills()
-> PromptBuilder 组装 Prompt
-> AgentManager.astream()
-> SSE 返回 token / tool / retrieval / skill_hit
-> SessionManager 持久化消息
-> 异步触发 DraftExtractor
```

## 7.2 Gateway 详细流程

### Step 1：Query Rewrite

输入：

- 当前用户问题
- 必要的最近历史

输出：

- 一条更适合检索技能的短查询

目标：

- 保留任务锚点
- 保留风格约束
- 去掉无关闲聊

### Step 2：Skill Retrieval

检索对象：

- 正式技能索引

检索策略：

- 语义检索
- 关键词检索
- 混合排序

输出：

- top-k skill hits

### Step 3：Skill Selection

职责：

- 过滤掉弱相关 skill
- 仅保留最适合当前任务的少量技能

输出：

- selected skills

### Step 4：Skill Context Injection

将 skill 以紧凑格式注入，而不是整库塞入 Prompt。

示例注入块：

```text
[Activated Skills]
- professional_rewrite
  goal: ...
  constraints: ...
- summarize_web_article
  goal: ...
  workflow: ...
```

---

## 八、后台学习链路设计

## 8.1 Draft Extractor

输入：

- 最近一轮或最近数轮对话

输出：

- 0 或 1 个高质量 Skill Draft

抽取规则：

- 必须 durable
- 必须 reusable
- 不要保留 one-off case
- 不要抄 assistant 自己的临时发挥

## 8.2 Related Skill Finder

对 Draft 检索最相似的现有正式技能，作为治理证据。

输出：

- top-n related skills

## 8.3 Skill Judge

输入：

- draft
- related skills

输出：

```json
{
  "action": "add | merge | ignore",
  "reason": "...",
  "target_skill": "..."
}
```

## 8.4 Skill Merger

当 action = merge 时：

- 不简单拼接文本
- 生成结构化 merge patch
- 保留旧 skill 身份
- 只引入新增且可复用的行为规范

## 8.5 Promotion Service

职责：

- 将 Draft Promote 为新 Skill
- 或执行 Merge
- 更新索引、版本、lineage 和快照

---

## 九、存储设计

## 9.1 skills/

正式技能目录。

```text
skills/
└── professional_rewrite/
    └── SKILL.md
```

## 9.2 skill_drafts/

候选技能目录。

```text
skill_drafts/
├── draft_20260412_001.md
└── draft_20260412_002.md
```

## 9.3 skill_registry/

### `skills_index.json`

存正式技能元数据与检索字段：

- id
- name
- description
- version
- tags
- triggers
- path

### `draft_index.json`

存 Draft 元数据：

- draft_id
- status
- source_session_id
- confidence
- recommended_action

### `usage_stats.json`

统计：

- retrieved_count
- selected_count
- adopted_count

### `merge_history.json`

记录：

- from_draft
- target_skill
- merged_at
- patch_summary

### `lineage.json`

记录：

- skill version
- parent version
- source draft
- operation type

---

## 十、API 设计

## 10.1 在现有 API 基础上新增

### `GET /api/gateway/last-hit/{session_id}`

获取最近一轮命中的技能。

### `GET /api/drafts`

列出所有 Skill Draft。

### `GET /api/drafts/{draft_id}`

获取 Draft 详情。

### `POST /api/drafts/{draft_id}/promote`

将 Draft Promote 为正式技能。

### `POST /api/drafts/{draft_id}/merge`

将 Draft 合并到目标 Skill。

### `POST /api/drafts/{draft_id}/ignore`

忽略 Draft。

### `GET /api/skills/{skill_name}/lineage`

获取技能版本历史。

### `GET /api/skills/{skill_name}/usage`

获取技能使用统计。

---

## 十一、前端设计配合

## 11.1 Sidebar

新增：

- Activated Skills
- Draft Skills
- Skill Governance

## 11.2 Chat Panel

新增一类可视化卡片：

- SkillHitCard

显示：

- 本轮命中的技能
- 命中原因摘要

## 11.3 Inspector Panel

支持打开：

- 正式 Skill
- Skill Draft
- Skill lineage

## 11.4 Governance Panel

展示：

- 推荐动作
- 相似技能
- Promote / Merge / Ignore 按钮

---

## 十二、与现有 Mini-Claw 的兼容策略

## 12.1 尽量不破坏现有模块

保留现有：

- `graph/agent.py`
- `graph/prompt_builder.py`
- `tools/skills_scanner.py`
- `api/chat.py`

通过新增层来增强：

- `gateway/`
- `evolution/`
- 新 API

## 12.2 渐进式改造

### 第一阶段

只增加 Gateway，不改 Skill 文件格式。

### 第二阶段

增加 Draft 与 Governance，但不启用自动 Promote。

### 第三阶段

增加版本历史、使用统计和 stale 审计。

---

## 十三、关键实现策略

## 13.1 不做全技能全量 Prompt 注入

改为：

- 快照只保留简要清单
- 只给主 Agent 注入命中技能的紧凑上下文

## 13.2 不做完全自动写库

改为：

- 自动生成草稿
- 自动给建议
- 人工确认入库

## 13.3 不做独立代理产品

ClawForge 以本地工作台为主，不以 OpenAI-compatible proxy 作为产品中心。

## 13.4 不照搬 Auto-Skill 命名体系

采用更符合 Mini-Claw 的命名：

- Skill Gateway
- Skill Draft
- Promote
- Merge Review
- Skill Registry

---

## 十四、里程碑

## M1：Gateway MVP

完成：

- Query Rewrite
- Skill Retrieval
- Skill Selection
- SkillHit 可视化

## M2：Draft MVP

完成：

- Draft Extraction
- Draft 列表
- Draft 详情页

## M3：Governance MVP

完成：

- Promote
- Merge
- Ignore
- Registry 更新

## M4：Evolution MVP

完成：

- Lineage
- Usage Stats
- stale 审计

---

## 十五、最终系统定义

ClawForge 的本质不是“一个会自动追加 Prompt 的系统”，而是：

> **一个面向本地 Agent 的显式技能操作系统：前台负责技能激活，后台负责技能锻造，用户始终可以看到、编辑、治理和演化这些技能。**

