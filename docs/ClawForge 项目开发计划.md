# ClawForge 项目开发计划

## 1. 计划目标

基于现有 `docs/ClawForge README.md`、`docs/ClawForge 产品需求文档.md` 和 `docs/ClawForge 系统设计文档.md`，将 ClawForge 按“先建立可运行基线，再逐步引入技能演化能力”的方式推进落地。

本计划服务于两个目标：

1. 把文档中的产品设想拆成可执行的研发阶段。
2. 在当前仓库尚未进入实装阶段的前提下，明确优先级、交付物、验收标准与风险控制方式。

## 2. 项目范围

### 2.1 本期建设目标

- 搭建本地优先、文件驱动的 Agent 工作台基线
- 实现 Skill Gateway 主链路
- 实现 Skill Draft 生成与审查
- 实现 Promote / Merge / Ignore 治理闭环
- 建立 Skill Registry、版本记录和基础统计
- 提供前端可观察、可查看、可编辑的工作台界面

### 2.2 本期不做

- 全自动无人值守写入正式技能库
- 多租户 SaaS 化
- 外部重型向量数据库依赖
- 以代理服务为核心的独立平台化产品

## 3. 规划原则

- 后端能力优先落地，前端以最小可验证界面配合开发
- 先复用 Mini-Claw 的成熟主干，再做 ClawForge 增量能力
- 先做 P0 闭环，再补 P1/P2 增强能力
- 所有关键状态优先落本地文件，避免黑盒状态
- 所有自动演化能力都要保留人工确认入口
- 前台链路和后台链路解耦，避免在线响应被学习流程拖慢

## 4. 开发假设

为便于排期，默认按一个小型研发小队估算：

- 1 名后端 / Agent 工程师
- 1 名前端 / 全栈工程师
- 1 名产品 / 测试兼任成员

建议开发节奏为 **8 到 10 周**。若团队人数更少，可按里程碑顺延；若已有 Mini-Claw 可直接迁移，则可压缩 1 到 2 周。

若本阶段明确采用“后端优先”策略，则默认按以下资源倾斜执行：

- 后端 / Agent 工程作为主线
- 前端只提供 API 验证、草稿查看和治理操作所需的最小界面
- 在后端主链路跑通前，不投入完整工作台体验打磨

## 5. 总体阶段划分

| 阶段 | 周期 | 目标 | 结果 |
| --- | --- | --- | --- |
| Phase 0 | 第 1 周 | 建立后端优先的基线工程与开发规范 | 后端骨架可运行、目录成型、基础文档和环境就绪 |
| Phase 1 | 第 2-3 周 | 迁移 / 重建 Mini-Claw 后端核心能力 | 聊天、会话、文件编辑、技能快照、Memory、索引能力可用 |
| Phase 2 | 第 4-5 周 | 完成 Skill Gateway MVP | 技能检索、选择、注入、命中记录闭环跑通 |
| Phase 3 | 第 6-7 周 | 完成 Skill Draft MVP | 对话后生成草稿、草稿存储、列表与详情 API 跑通 |
| Phase 4 | 第 8 周 | 完成 Governance MVP | add / merge / ignore 建议与人工治理入库 |
| Phase 5 | 第 9-10 周 | 完成 Evolution 增强与前端补齐 | lineage、usage stats、stale 审计、最小工作台联调完成 |

## 5.1 后端优先执行策略

本项目当前建议采用“**后端主链路先闭环，前端随后补齐**”的实施方式。

### 执行顺序

```text
后端工程基线
-> 聊天 / 会话 / Prompt / 工具链路
-> Skill Gateway
-> Skill Draft
-> Skill Governance
-> Skill Registry / Versioning / Stats
-> 前端最小联调
-> 前端完整工作台增强
```

### 原因

- 当前仓库仍处于文档阶段，真正的项目风险主要在后端主链路能否跑通
- ClawForge 的核心差异化能力主要集中在 Gateway、Evolution、Registry 等后端模块
- 前端可以先用最小界面或接口调试工具支撑开发，不必一开始投入完整工作台建设
- 先把文件落盘、状态一致性、异步学习链路和治理闭环做稳，后续前端接入成本更低

## 6. 分阶段开发计划

## 6.1 Phase 0：项目基线搭建

### 目标

建立以后端为主的工程骨架、环境配置、开发规范和最小可运行项目。

### 主要任务

- 初始化仓库目录结构
  - `backend/`
  - `frontend/`
  - `docs/`
  - 基础 `skills/`、`memory/`、`sessions/`、`storage/` 目录
- 搭建后端基础框架
  - FastAPI 应用入口
  - 配置管理
  - 基础 API 路由注册
- 搭建前端基础框架
  - 仅初始化最小前端壳
  - 预留后续联调入口
- 建立工程规范
  - Python lint / format
  - TypeScript lint / format
  - 基础日志规范
  - `.env.example`
- 输出初版数据结构约定
  - `SKILL.md`
  - `sessions/*.json`
  - `skill_registry/*.json`

### 交付物

- 可启动的前后端空壳工程
- 初版目录结构
- 环境配置模板
- 开发规范文档

### 验收标准

- 后端健康检查可用
- 后端可正常启动并返回健康检查
- 仓库结构与系统设计文档保持一致

## 6.2 Phase 1：Mini-Claw 基线能力迁移 / 重建

### 目标

先把 ClawForge 赖以演进的后端承载层搭起来，确保后续 Gateway 和 Evolution 有稳定基础。

### 主要任务

- 实现基础会话系统
  - `POST /api/chat`
  - `GET /api/sessions`
  - 会话持久化
  - 首次会话标题生成
- 实现 Prompt 组装器
  - `SKILLS_SNAPSHOT.md`
  - `workspace/*.md`
  - `MEMORY.md`
- 实现核心工具能力
  - terminal
  - python_repl
  - fetch_url
  - read_file
  - search_knowledge_base
- 实现技能扫描器
  - 扫描 `skills/*/SKILL.md`
  - 生成 `SKILLS_SNAPSHOT.md`
- 实现 Memory 索引与基础 RAG
- 提供最小验证入口
  - Swagger / OpenAPI 调试
  - 可选的简单前端调试页

### 交付物

- 一个可用的 Mini-Claw 风格后端基线
- 基础技能加载机制
- 文件编辑与会话查看 API 能力

### 验收标准

- 用户可发起对话并看到流式回复
- Agent 可读取技能文件并执行任务
- 用户可通过 API 查看并编辑 `MEMORY.md` 或 `SKILL.md`
- 会话与文件变更可正确落盘

## 6.3 Phase 2：Skill Gateway MVP

### 目标

把“主 Agent 自行猜技能”升级为显式的技能激活链路。

### 主要任务

- 实现 `gateway/` 模块
  - `query_rewriter.py`
  - `skill_retriever.py`
  - `skill_selector.py`
  - `skill_context_builder.py`
  - `gateway_manager.py`
- 建立技能检索索引
  - 解析正式技能 frontmatter
  - 建立关键词字段
  - 预留语义检索扩展点
- 改造聊天主链路
  - 在 `POST /api/chat` 前置调用 Gateway
  - 将命中技能以紧凑上下文注入 Prompt
- 增加命中结果输出
  - SSE 增加 `skill_hit`
  - `GET /api/gateway/last-hit/{session_id}`
- 暂只要求输出可消费的命中结果
  - SSE `skill_hit`
  - last-hit 查询接口

### 交付物

- 可运行的 Gateway 激活链路
- 基础命中记录接口
- 前端可接入的结构化返回

### 验收标准

- 每轮对话前可筛出少量相关技能
- Prompt 中不再注入全量技能内容
- 接口可返回本轮命中技能及原因摘要
- 线上响应时延可接受，且不明显劣化基础聊天体验

## 6.4 Phase 3：Skill Draft MVP

### 目标

将对话中稳定、可复用的行为规则沉淀为候选技能草稿。

### 主要任务

- 实现 `evolution/` 初版模块
  - `draft_extractor.py`
  - `related_skill_finder.py`
  - `skill_judge.py`
- 设计并落地 Draft 文件格式
- 实现对话后异步草稿生成
  - 对最近一轮或最近数轮对话做提炼
  - 控制每轮最多产出 0 或 1 个高质量 Draft
- 建立 `skill_drafts/` 和 `draft_index.json`
- 增加 Draft 查询接口
  - `GET /api/drafts`
  - `GET /api/drafts/{draft_id}`
- 补充 Draft 结果 API 契约，供后续前端消费

### 交付物

- 可落盘的 Skill Draft 生成链路
- Draft 列表、详情、来源信息 API 能力

### 验收标准

- 对话结束后可异步产出结构化 Draft
- Draft 至少包含 Goal、Constraints、Evidence、confidence、recommended_action
- API 可以返回草稿内容和来源会话

## 6.5 Phase 4：Skill Governance MVP

### 目标

建立从 Draft 到正式 Skill 的人工治理闭环。

### 主要任务

- 实现治理动作接口
  - `POST /api/drafts/{draft_id}/promote`
  - `POST /api/drafts/{draft_id}/merge`
  - `POST /api/drafts/{draft_id}/ignore`
- 实现 `promotion_service.py`
- 实现 `skill_merger.py`
  - merge patch 生成
  - 保留旧技能身份
  - 仅增补可复用规则
- 建立 `skill_registry/`
  - `skills_index.json`
  - `draft_index.json`
  - `merge_history.json`
  - `lineage.json`
- 输出治理操作所需的完整接口与响应结构

### 交付物

- 完整治理闭环
- 技能索引与治理记录
- 基础版本演化记录
- 前端可接入的治理接口

### 验收标准

- Draft 能被 Promote 为新技能
- Draft 能被 Merge 到已有技能
- Ignore 后 Draft 状态正确更新
- 技能索引、merge 记录、lineage 可正确更新

## 6.6 Phase 5：Evolution 增强与发布准备

### 目标

补齐版本、统计、审计和质量保障能力，为内部试运行或首版发布做准备。

### 主要任务

- 实现 `skill_versioning.py`
  - patch 级版本递增
  - 前后差异记录
  - 回滚预留
- 建立使用统计
  - retrieved_count
  - selected_count
  - adopted_count
- 实现 stale skill 审计规则
- 补齐知识文档到技能的离线提炼预留能力
- 建立测试体系
  - Prompt / Gateway 单元测试
  - API 集成测试
  - 前端关键交互测试
  - 回归验证用例
- 完成发布准备
  - 安装文档
  - 演示数据
  - MVP 试用说明

### 交付物

- Skill 使用统计
- 版本历史与 lineage 查询
- 稳定性测试报告
- 最小工作台联调结果
- 首版发布文档

### 验收标准

- 技能使用情况可被统计和查看
- 版本历史可追溯
- stale 技能可被识别
- 核心主链路具备可回归验证能力

## 7. 工作流拆分建议

为保证开发效率，建议以后端为主、前端配合的方式推进：

### 7.1 后端 / Agent 主工作流

- FastAPI 路由
- AgentManager 与 PromptBuilder
- Gateway 与 Evolution 模块
- 文件落盘与注册表维护
- 索引构建与一致性校验
- 版本与统计能力

### 7.2 前端配合工作流

- 先做 API 调试页或极简控制台
- 后做三栏工作台
- 后补 Activated Skills / Drafts / Governance 面板
- 后补 Inspector 文件查看与编辑

### 7.3 数据与检索工作流

- Skill frontmatter 规范
- 技能索引构建
- Draft 格式与注册表结构
- usage stats / lineage 结构定义

### 7.4 测试与验收工作流

- 核心链路回归用例
- Prompt 注入前后效果对比
- 技能命中准确性抽样验证
- Draft 污染率与误提取率检查
- API 契约测试

## 8. 优先级建议

### P0

- Mini-Claw 基线能力
- Skill Gateway 主链路
- Skill Draft 生成
- Draft 列表与详情 API
- 基础治理建议接口

### P1

- Promote / Merge / Ignore 闭环
- Skill Versioning
- Usage Stats
- Skill lineage 查询接口

### P2

- stale skill 审计
- 文档到技能离线提炼
- Replay 驱动技能评估
- 完整前端工作台增强

## 9. 关键风险与应对

### 风险 1：当前仓库没有 Mini-Claw 基线代码

影响：

- 若直接开发 ClawForge，会缺少稳定承载层

应对：

- 将“基线迁移 / 重建”单独作为第一优先级阶段
- 优先保证聊天、技能读取、文件编辑、会话落盘可运行

### 风险 2：技能检索质量不稳定

影响：

- 命中错误会直接削弱 Gateway 价值

应对：

- 第一版先做关键词 + 结构化字段召回
- 再逐步叠加语义检索与混合排序
- 建立典型任务集做命中效果回归

### 风险 3：Draft 污染技能库

影响：

- 一次性上下文被沉淀为正式技能，导致技能库退化

应对：

- 严格限制 Draft 抽取规则
- 每轮最多产出少量高质量 Draft
- 必须经过人工 Promote / Merge

### 风险 4：Prompt 注入再次膨胀

影响：

- 在线链路性能和回答质量下降

应对：

- 注入内容只保留命中技能的紧凑摘要
- 不把完整技能库重新塞回系统提示词

### 风险 5：文件状态与索引状态不一致

影响：

- 可能出现前端显示正确但后端注册表未同步的问题

应对：

- 所有 Promote / Merge / Ignore 统一经服务层写入
- 启动时提供一次索引重建能力
- 为关键注册表编写一致性校验脚本

## 10. 验收指标建议

### 功能指标

- 聊天主链路稳定可用
- Gateway 可在对话前完成技能筛选和注入
- 对话后可生成可审查 Draft
- 用户可完成 Promote / Merge / Ignore 操作
- 所有核心能力均可通过 API 独立验证

### 质量指标

- 技能命中结果可解释
- Draft 质量可人工接受
- 技能库增长可控，无明显重复和污染
- 前端核心视图能完整呈现技能状态

### 产品指标

- 用户重复描述流程和风格约束的频率下降
- 相比“全量技能快照”方案，技能命中精度提升
- 技能逐步沉淀为可维护的长期资产

## 11. 建议的首版发布口径

首版建议定义为 **MVP 内测版**，范围控制在：

- 本地单用户使用
- 单机文件存储
- 已支持技能激活、草稿生成、基础治理
- 已支持基础版本记录和使用统计
- 前端以最小可用工作台为主，不追求完整体验

不建议在首版承诺：

- 全自动技能演化
- 大规模知识库管理
- 多人协作或云端同步

## 12. 结论

ClawForge 的正确落地顺序，不是直接做“技能会自己长”的高级能力，而是：

```text
先搭工作台基线
-> 再做 Skill Gateway
-> 再做 Skill Draft
-> 再做 Skill Governance
-> 最后补 Skill Evolution 增强
```

在“后端优先”的前提下，这样可以先把项目真正有技术风险和产品价值的部分做实，再让前端围绕稳定接口快速补齐展示与交互层，既符合当前文档设定，也更适合当前仓库从文档走向实现的实际状态。
