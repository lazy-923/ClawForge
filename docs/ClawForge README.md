# ClawForge

一个本地优先、文件驱动、透明可控的 AI Agent 技能工作台。  
它在 Mini-Claw 的基础上进一步引入 **Skill Gateway** 与 **Skill Evolution**，让系统不仅能“读取技能”，还能够“激活技能、生成技能草稿、治理技能、演化技能”。

## 项目定位

如果说 Mini-Claw 解决的是：

- Agent 如何读取本地 Skill 文件
- Agent 如何结合 Memory、Tools 和 Prompt 完成任务

那么 ClawForge 解决的是：

- 当前这轮请求到底该激活哪些技能
- 交互中产生的稳定经验如何沉淀为技能草稿
- 技能草稿如何进入正式技能库
- 技能如何合并、升级、治理和回滚

换句话说：

```text
Mini-Claw 更像一个文件驱动的 Agent 工作台
ClawForge 更像一个显式技能的操作系统
```

## 为什么要做 ClawForge

传统 AI Agent 项目往往有两个典型问题：

1. 技能是静态的  
- 技能只能靠人工预先编写  
- 系统不会从真实交互中沉淀出新的做事方式

2. 技能激活是模糊的  
- 往往把全量技能或大段 Prompt 直接塞给模型  
- 缺少专门的技能检索、选择和注入层

ClawForge 的目标就是补上这两块：

- 前台引入 **Skill Gateway**
- 后台引入 **Skill Evolution**

这样系统既能保留文件驱动的透明性，又能获得“边用边长”的能力。

## 核心理念

### 1. 文件优先

技能、草稿、版本、统计、治理记录都优先落盘为本地文件，而不是隐藏在数据库或黑盒服务里。

### 2. 显式技能

系统不依赖隐式 Prompt 漂移，而是把能力沉淀为显式工件：

- 正式技能 `SKILL.md`
- 技能草稿 `Draft`
- 技能版本历史
- 技能使用统计

### 3. 半自动演化

ClawForge 不追求“每轮对话自动入库”，而是采用：

```text
交互结束 -> 提取 Skill Draft -> 给出 add/merge/ignore 建议 -> 人工确认 Promote
```

这让系统具备学习能力，同时保持可控。

### 4. 前后台分离

前台路径负责：

- 技能激活
- 技能检索
- 技能注入
- Agent 对话执行

后台路径负责：

- 技能草稿生成
- 相似技能发现
- 治理建议
- 版本演化

## 系统全景

ClawForge 的整体形态可以概括为：

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
    |- Skill Judge
    |- Skill Merger
    |- Promotion Service
    |
Storage Layer
    |- skills/
    |- skill_drafts/
    |- skill_registry/
    |- memory/
    |- sessions/
```

## 两条核心链路

## 1. 在线链路：Skill Gateway

每当用户发起一个请求，系统不会直接把全部技能塞进 Prompt，而是先走一条技能网关链路：

```text
user query
-> query rewrite
-> skill retrieval
-> skill selection
-> skill context injection
-> agent response
```

这条链路的核心目标是：

- 只激活少量相关技能
- 控制 Prompt 膨胀
- 提升技能命中精度
- 让“为什么命中这个技能”变得可解释

## 2. 后台链路：Skill Evolution

每轮对话结束后，系统会异步分析交互内容，尝试生成新的技能草稿：

```text
conversation turn end
-> draft extraction
-> related skill retrieval
-> add/merge/ignore suggestion
-> wait for promote decision
```

这条链路的目标是：

- 从稳定交互中提炼可复用能力
- 避免把一次性内容污染进技能库
- 让技能库有版本、有来源、有治理

## 关键抽象

### 1. Formal Skill

正式技能，位于：

```text
backend/skills/<skill_name>/SKILL.md
```

职责：

- 参与在线检索
- 被注入 Prompt
- 被前端展示
- 被版本管理

### 2. Skill Draft

技能草稿，位于：

```text
backend/skill_drafts/<draft_id>.md
```

职责：

- 承载抽取出的候选能力
- 等待 add / merge / ignore 治理
- 作为正式技能的来源证据

### 3. Skill Registry

技能注册表，位于：

```text
backend/skill_registry/
```

用于存储：

- 技能索引
- 草稿索引
- 技能使用统计
- merge 历史
- lineage 版本关系

## 项目结构（目标形态）

```bash
ClawForge/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── api/
│   │   ├── chat.py
│   │   ├── gateway.py
│   │   ├── drafts.py
│   │   ├── files.py
│   │   ├── sessions.py
│   │   ├── tokens.py
│   │   ├── compress.py
│   │   └── config_api.py
│   ├── graph/
│   │   ├── agent.py
│   │   ├── prompt_builder.py
│   │   ├── session_manager.py
│   │   ├── memory_indexer.py
│   │   └── knowledge_indexer.py
│   ├── gateway/
│   │   ├── query_rewriter.py
│   │   ├── skill_retriever.py
│   │   ├── skill_selector.py
│   │   ├── skill_context_builder.py
│   │   └── gateway_manager.py
│   ├── evolution/
│   │   ├── draft_extractor.py
│   │   ├── related_skill_finder.py
│   │   ├── skill_judge.py
│   │   ├── skill_merger.py
│   │   ├── skill_versioning.py
│   │   └── promotion_service.py
│   ├── tools/
│   ├── workspace/
│   ├── memory/
│   ├── sessions/
│   ├── skills/
│   ├── skill_drafts/
│   ├── skill_registry/
│   ├── knowledge/
│   └── storage/
│
└── frontend/
    └── src/
        ├── app/
        ├── components/
        │   ├── chat/
        │   ├── layout/
        │   ├── editor/
        │   └── governance/
        └── lib/
```

## Skill 文件设计

ClawForge 不改变 Mini-Claw “Skill 是文件工件”的基础，但会把技能从“简单步骤说明”升级为更适合检索与演化的结构。

### 正式技能

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

### 技能草稿

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

## 与 Mini-Claw 的关系

ClawForge 不是对 Mini-Claw 的否定，而是它的下一阶段升级。

### Mini-Claw 保留的部分

- 本地优先
- 文件驱动 Prompt
- `SKILL.md` 技能工件
- 工具驱动执行
- 前端工作台

### ClawForge 新增的部分

- Skill Gateway
- Skill Drafting
- Skill Governance
- Skill Versioning
- Skill Usage Stats

因此可以把两者关系理解为：

```text
Mini-Claw = 文件驱动 Agent 工作台
ClawForge = 文件驱动 Agent 技能操作系统
```

## 与 Auto-Skill 的关系

ClawForge 吸收了 Auto-Skill 的几个关键思想：

- Skill 作为显式工件
- 前台 serving 与后台 learning 分离
- candidate -> judge -> merge 的治理流程
- Skill 版本与 lineage 思维

但 ClawForge 并不是 Auto-Skill 的直接移植，它有明确不同：

1. 以本地工作台为中心，而不是以代理服务为中心
2. 以文件工件为核心，而不是以运行时服务为核心
3. 采用半自动 Promote 机制，而不是默认全自动入库
4. 更强调前端可视化审查、人工编辑与治理

## 目标用户

ClawForge 主要面向两类用户：

### 1. Agent / Prompt 开发者

他们需要：

- 审查技能命中过程
- 审查技能草稿来源
- 手工修改技能
- 管理技能版本

### 2. 重度本地 AI 工作流使用者

他们需要：

- 长期积累自己的工作方式
- 减少重复描述流程和风格
- 让系统逐步学会“怎么做事”

## 产品价值

ClawForge 的核心价值不是“让模型更聪明”，而是：

1. 让技能激活更精准  
2. 让经验沉淀更结构化  
3. 让技能演化更可控  
4. 让 Agent 系统更像一个可治理的软件系统，而不是只会堆 Prompt 的黑盒

## 阶段路线图

## Phase 1：Skill Gateway MVP

完成：

- Query Rewrite
- Skill Retrieval
- Skill Selection
- Skill Context Injection
- 前端展示本轮命中技能

## Phase 2：Skill Draft MVP

完成：

- 对话后异步抽取 Skill Draft
- Draft 存储到本地
- 前端查看 Draft 列表与详情

## Phase 3：Skill Governance MVP

完成：

- add / merge / ignore 建议
- Promote / Merge / Ignore 操作
- Registry 更新

## Phase 4：Skill Evolution 增强

完成：

- lineage 历史
- 使用统计
- stale skill 审计
- 文档到技能的离线提炼

## 当前文档

本项目当前已经提供两份核心文档：

- [ClawForge 产品需求文档.md](d:/develop/Code/python/AgentLearning/OpenClaw/miniClaw/docs/ClawForge%20产品需求文档.md)
- [ClawForge 系统设计文档.md](d:/develop/Code/python/AgentLearning/OpenClaw/miniClaw/docs/ClawForge%20系统设计文档.md)

它们分别回答：

- 这个项目为什么做、要做什么
- 这个项目准备怎么做、系统怎么拆

## 最终定义

ClawForge 的最终目标不是做一个“会聊天的 Agent”，而是做一个：

> **能够把显式技能、技能检索、技能草稿生成、技能治理和技能演化统一起来的本地 Agent 技能工作台。**

