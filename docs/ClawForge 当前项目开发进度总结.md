# ClawForge 当前项目开发进度总结

## 1. 总体结论

结合 `docs/` 下的产品、设计、开发计划文档，以及当前仓库实现情况，ClawForge 已经不再停留在纯文档阶段。

当前项目的真实状态更接近：

- 后端主链路已经从 Phase 0 / Phase 1 推进到 **Phase 4 附近的 MVP 状态**
- 前端已经完成 **可测试工作台版本**，但仍未达到完整产品版
- Phase 5 中的部分能力已经提前落地，但整体还未完成

可以概括为：

```text
后端原型已成形
前端可测试工作台已落地
核心能力可跑通
智能化程度和产品完成度仍偏早期
```

---

## 2. 与规划文档的对照结果

依据 `docs/ClawForge 项目开发计划.md` 中的阶段划分，当前进度判断如下：

### Phase 0：项目基线搭建

状态：**已完成**

已具备：

- `backend/`、`frontend/`、`docs/` 基础目录
- FastAPI 应用入口
- 基础 API 路由注册
- Next.js 前端壳
- 本地文件存储目录

### Phase 1：Mini-Claw 基线能力迁移 / 重建

状态：**基本完成**

已具备：

- 聊天接口
- 会话持久化
- Prompt 组装
- Skills Snapshot 扫描
- Memory 检索
- 文件查看与保存 API
- 工具接入能力

### Phase 2：Skill Gateway MVP

状态：**已完成首版**

已具备：

- Query Rewrite
- Skill Retrieval
- Skill Selection
- Skill Context Injection
- `skill_hit` 返回
- `last-hit` 查询接口

### Phase 3：Skill Draft MVP

状态：**已完成首版**

已具备：

- 对话后生成 Draft
- Draft 落盘
- Draft 索引
- Draft 列表与详情接口

### Phase 4：Skill Governance MVP

状态：**已完成首版**

已具备：

- Promote
- Merge
- Ignore
- Registry 更新
- lineage / merge history 记录

### Phase 5：Evolution 增强与发布准备

状态：**部分完成**

已具备：

- usage stats 初版
- lineage 查询
- stale audit 初版
- 最小前端工作台联调
- 前端 Draft 治理入口
- 前端 SSE 聊天可观察性
- 前端 Inspector 详情面板

尚未完成：

- 更完整的测试体系
- 更可靠的版本演化机制
- 文档到技能离线提炼
- Replay 评估
- 更成熟的前端产品体验与打磨

---

## 3. 当前已完成的核心能力

## 3.1 后端应用骨架

以下能力已经具备：

- FastAPI 应用入口与生命周期初始化
- 健康检查接口
- Chat / Sessions / Files / Gateway / Drafts / Skills API 路由
- 启动时扫描技能并初始化 Agent

对应实现：

- `backend/app.py`
- `backend/config.py`
- `backend/api/`

## 3.2 会话与聊天主链路

当前后端已经具备一个可运行的聊天主链路：

```text
用户请求
-> 创建/读取 session
-> 读取历史
-> 激活技能
-> 组装 prompt
-> Agent 响应
-> 保存消息
-> 生成 draft
```

已落地内容包括：

- 会话创建与重命名
- 会话消息持久化到本地 `sessions/*.json`
- 首轮消息自动生成标题
- 支持流式和非流式聊天
- SSE 返回 `token`、`retrieval`、`skill_hit`、`draft_generated`、`done`

对应实现：

- `backend/api/chat.py`
- `backend/graph/session_manager.py`

## 3.3 Prompt 组装机制

当前 PromptBuilder 已经能从本地文件拼装主提示上下文，读取以下内容：

- `SKILLS_SNAPSHOT.md`
- `workspace/SOUL.md`
- `workspace/IDENTITY.md`
- `workspace/USER.md`
- `workspace/AGENTS.md`
- `memory/MEMORY.md`
- Activated Skills 上下文

说明项目已经具备 Mini-Claw 风格的文件驱动 Prompt 基线。

对应实现：

- `backend/graph/prompt_builder.py`

## 3.4 Agent 运行时与工具接入

当前 AgentManager 已支持两种模式：

- `mock` 模式
- 配置了兼容 OpenAI API 后的 LangChain / LLM 模式

并已接入以下工具：

- `terminal`
- `python_repl`
- `fetch_url`
- `read_file`
- `search_knowledge_base`

对应实现：

- `backend/graph/agent.py`
- `backend/tools/`

## 3.5 Skill Gateway 首版

Skill Gateway 已经不是规划中的空模块，而是能实际参与聊天流程。

当前已实现：

- Query Rewrite
- 候选技能检索
- 技能筛选
- Activated Skills 上下文构建
- 命中结果存档
- 技能使用次数统计

当前判断：

- 这条链路已经形成首版 MVP
- 但 skill retrieval 仍主要是规则 / 关键词驱动
- 尚未完成借鉴 AutoSkill 的 `LlamaIndex hybrid retrieval + selection` 形态

对应实现：

- `backend/gateway/query_rewriter.py`
- `backend/gateway/skill_retriever.py`
- `backend/gateway/skill_selector.py`
- `backend/gateway/skill_context_builder.py`
- `backend/gateway/gateway_manager.py`
- `backend/api/gateway.py`

## 3.6 Skill Draft 生成链路

当前系统已具备对话结束后生成技能草稿的流程。

已实现：

- 从用户消息中抽取候选草稿
- 查找相关技能
- 给出推荐动作
- 写入 `backend/skill_drafts/*.md`
- 维护 `draft_index.json`

对应实现：

- `backend/evolution/draft_extractor.py`
- `backend/evolution/related_skill_finder.py`
- `backend/evolution/skill_judge.py`
- `backend/evolution/draft_service.py`

## 3.7 Governance 治理闭环

当前系统已具备从 Draft 到正式 Skill 的基础治理能力。

已实现动作：

- Promote：将 Draft 生成正式 Skill
- Merge：将 Draft 合并到已有 Skill
- Ignore：忽略 Draft

同时会更新：

- Draft 状态
- Skills Index
- Usage Stats
- Merge History
- Lineage

对应实现：

- `backend/evolution/promotion_service.py`
- `backend/evolution/skill_merger.py`
- `backend/evolution/registry_service.py`
- `backend/api/drafts.py`
- `backend/api/skills.py`

## 3.8 文件与注册表落盘

目前项目已经建立起文件驱动的数据落盘结构，且仓库中已有真实数据：

- `backend/skills/`
- `backend/skill_drafts/`
- `backend/skill_registry/`
- `backend/sessions/`
- `backend/storage/`

这说明项目核心思路“文件优先”已经进入实际运行状态，而不是停留在设计层。

## 3.8.1 RAG 检索后端现状

当前与 RAG 相关的后端能力已经开始向文档目标收敛：

- `memory` 检索已切换到 `LlamaIndex`
- `knowledge` 检索已切换到 `LlamaIndex`
- 已支持向量检索 + BM25 混合召回的本地持久化形态

但需要特别区分：

- 这部分是 Memory / Knowledge RAG
- 还不等于 Skill Gateway 已完成同等形态的技能检索升级

## 3.9 前端可测试工作台

前端已经不再只是占位页，而是完成了一个能对接当前后端主链路的可测试工作台。

已实现：

- Session 列表与切换
- Chat 面板
- 非流式基础联调
- SSE 流式聊天展示
- Activated Skills 面板
- Session Drafts 面板
- Draft `promote / merge / ignore` 操作
- Draft Inspector
- Skill Inspector
- usage / lineage 展示
- stale audit 展示

对应实现：

- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`

这意味着当前前端已经可以作为后端能力的可视化测试台使用，而不是只承担展示项目阶段信息的说明页。

---

## 4. 当前项目里已经能看到的运行结果

仓库中已能看到以下实际产物：

- 已存在正式技能：
  - `get_weather`
  - `professional_rewrite`
- 已存在多份 Draft 文件
- 已存在 `draft_index.json`
- 已存在 `skills_index.json`
- 已存在 `usage_stats.json`
- 已存在 `lineage.json`
- 已存在多份 `sessions/*.json`

这说明以下场景至少已经被验证过：

- 聊天会话可落盘
- Skill Gateway 可命中技能
- Draft 可生成
- Promote / Merge / Ignore 至少跑通过一轮
- 前端可以直接驱动会话、聊天、技能命中观察和 Draft 治理

---

## 5. 当前未完成或仍较薄弱的部分

虽然主链路已经搭起来，但距离文档中的完整产品形态还有明显差距。

## 5.1 前端工作台仍非完整产品版

当前前端已经具备可测试工作台，但仍然更偏“联调工作台”而不是成熟产品界面。

已具备：

- 三栏工作台雏形
- 聊天与会话切换
- Activated Skills 查看
- Session Drafts 与治理操作
- Draft / Skill / stale audit Inspector

仍然缺少或较弱的部分：

- 更细致的交互打磨
- 更完整的状态反馈
- 更成熟的草稿详情浏览体验
- 更完整的工作台信息结构
- 前端自动化测试

## 5.2 Skill Retrieval / Selection 仍然偏规则化

当前 Gateway 虽然已可用，但整体还是 MVP 级实现：

- Query Rewrite 主要靠停用词过滤和简单拼接
- Skill Retrieval 主要靠关键词匹配
- Skill Selection 主要按分数截断

与设计文档目标相比，还缺少：

- `LlamaIndex` 驱动的技能检索
- dense + BM25 混合召回
- 更强的相关性判断
- 更可解释的选择逻辑

补充说明：

- `memory / knowledge` 的 RAG 检索后端已开始切到 `LlamaIndex`
- 真正还没升级完成的是 `Skill Gateway` 的技能检索

## 5.3 Draft 提取已完成 Phase B 首版

当前后端已经不再是“聊天结束后同步关键词触发 draft”的旧形态，而是完成了 Phase B 的首版升级：

- 已新增后台异步 `EvolutionRunner`
- 前台聊天响应不再等待 extraction 完成
- Draft Extractor 已扩展为读取最近多轮消息，而不只看单轮 user message
- 已接入 top-1 skill hit 的 identity context
- 已增加“单次偶发请求不轻易触发 draft”的基础去噪逻辑
- 已补 API smoke test、extractor 单测与本地 runner 验证

但这部分仍未完全达到 PRD 中的最终目标，当前剩余问题主要是：

- 抽取仍是启发式规则驱动，还不是完整的 `ExtractorSubAgent`
- durable / reusable / one-off 的判断仍偏轻量
- merger 仍未升级到独立子智能体编排
- 与完整的 evolution 回放、评估和治理质量提升相比仍有差距

## 5.4 Judge / Related Skill Finder 已完成 Phase C 首版

当前后端已经完成 Phase C 的首版升级：

- related skill 不再只是简单复用 retrieval 结果，而是增加了面向治理的相似度视图
- 已细化 job-to-be-done、constraints、workflow 等维度的相似度计算
- judge 已从简单 score 阈值升级为 `add / merge / ignore` 的综合判断逻辑
- draft 中已保留更可解释的 related skill 指标与 judge reason
- 已补 governance 单测，并通过 API smoke 与本地 runner 验证

但这一部分仍未完全达到最终目标，当前剩余问题主要是：

- 仍不是完整的 `JudgeSubAgent`
- 仍缺少独立回放评估与更丰富的治理样本集
- merger / versioning 的结构化升级还未开始

## 5.5 Skill Merge / Versioning 还比较初级

当前 Merge 已经能工作，但更像“把 Draft 追加到 Skill 文件”。

还缺少更完整的版本治理能力，例如：

- 更结构化的 merge patch
- 更严格的差异管理
- 回滚机制
- 更完整的版本查询体验

## 5.6 测试覆盖仍需继续补强

当前测试只有一个 smoke test 文件：

- `tests/test_api_smoke.py`

已有基础验证价值，但离文档中提到的测试体系还有较大差距：

- Prompt / Gateway 单元测试
- API 集成测试扩展
- 前端交互测试
- 回归测试用例

## 5.6 README 与部分项目说明需要持续同步

项目根 README 此前曾停留在 `Phase 0 in progress` 的早期状态，说明文档和实现状态容易出现不同步。随着后续阶段推进，仍需要持续同步：

- README 当前状态
- 前端完成度
- 可运行方式
- 后端与前端阶段性能力

---

## 6. 当前阶段的综合判断

从“项目是否进入实现期”这个问题看，答案是：**已经进入，而且后端已经形成可运行雏形。**

从“是否达到文档中的完整产品状态”这个问题看，答案是：**还没有。**

更准确的判断是：

```text
项目已经完成后端主链路 MVP
项目已经具备前端可测试工作台
但离完整产品化仍有明显距离
当前最成熟的是后端骨架、文件驱动治理流程和前端联调工作台
最薄弱的是检索质量、草稿智能化、工程测试体系和产品级打磨
```

---

## 7. 建议的后续重点

若继续按当前文档路线推进，建议优先顺序如下：

### 1. 把 Skill Gateway 检索升级到 LlamaIndex Hybrid Retrieval

优先增强：

- 更可靠的 Query Rewrite
- 更合理的 Skill Retrieval
- 更稳定的 Skill Selection
- 检索与选择分层

### 2. 重做 Draft Extractor，并引入后台 Evolution 子智能体编排

目标应从“关键词触发”升级为：

- 面向多轮对话
- 可识别 durable / reusable 规则
- 可减少 one-off 污染
- 前台响应与后台学习解耦

### 3. 升级 Judge / Related Skill Finder，再补齐测试体系

建议至少增加：

- Gateway 单元测试
- Draft / Governance 集成测试
- 前端关键交互测试
- 回归测试样例

### 4. 打磨前端工作台体验

优先增强：

- 更清晰的 Draft / Skill 信息组织
- 更友好的状态与错误反馈
- 更好的细节交互
- 更完整的 Inspector 浏览体验

### 5. 持续同步 README 与阶段文档

建议每完成一个较大阶段，都同步更新：

- 根目录 README
- 当前项目开发进度总结
- 必要的开发 / 使用说明

---

## 8. 一句话总结

ClawForge 当前已经完成了“**后端优先的技能工作台 MVP 骨架 + 前端可测试工作台**”，核心链路包括聊天、技能激活、草稿生成、基础治理、注册表统计以及前端观察与治理入口都已落地；但检索质量、智能化抽取、测试体系和产品级体验仍需继续建设。
