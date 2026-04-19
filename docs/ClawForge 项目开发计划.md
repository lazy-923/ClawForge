# ClawForge 项目开发计划

## 1. 文档目标

本文档用于把 ClawForge 从“当前可运行 MVP”继续推进到“更完整、更稳定、更接近成品”的开发阶段。

它重点回答四个问题：

1. 当前项目已经做到哪里
2. 距离目标产品还差什么
3. 后续开发应该按什么顺序推进
4. 每个阶段完成后如何验收

---

## 2. 当前项目状态

结合当前仓库代码、阶段性提交记录以及 `docs/` 下的相关文档，项目已不处于纯文档或纯脚手架阶段，而是进入了 **MVP 已成形、质量与产品化继续推进** 的状态。

### 2.1 已完成的部分

后端已完成：

- 会话与聊天主链路
- Prompt 文件组装
- Skill Gateway 基础链路
- Skill Draft 生成
- Promote / Merge / Ignore 治理闭环
- Skill Registry / usage / lineage / stale audit
- 本地文件落盘
- 本地测试脚本与基础 smoke test

前端已完成：

- Session 列表与切换
- Chat 面板
- SSE 流式消息展示
- Activated Skills 面板
- Session Drafts 列表
- Draft 治理按钮
- Draft / Skill Inspector
- usage / lineage / stale audit 展示

### 2.2 当前仍明显属于 MVP 的部分

当前仍偏 MVP 的核心模块：

- Skill Gateway 检索质量
- Memory 检索质量
- Draft Extractor 抽取质量
- Related Skill Finder / Skill Judge 判断质量
- Skill Merge / Versioning 的结构化程度
- 完整测试体系
- 前端产品级交互与打磨

### 2.3 当前开发判断

项目当前更适合定义为：

```text
后端主链路 MVP 已完成
前端可测试工作台已完成
系统已具备联调与演示能力
但距离成品仍需继续补齐质量、稳定性和体验
```

---

## 3. 本阶段开发总目标

接下来的开发目标不再是“把模块搭出来”，而是分阶段把项目从 MVP 拉向更完整的产品形态。

本阶段总目标分为四类：

### 3.1 效果目标

- 提高 Skill Gateway 命中质量
- 提高 Draft 提取与治理判断质量
- 降低 stop words、误召回、误 merge 等问题
- 让 Gateway 与 Evolution 更接近 AutoSkill 的主链路设计

### 3.2 工程目标

- 建立更可靠的回归测试体系
- 提升后端模块间的一致性
- 降低测试过程和运行过程中的临时状态污染
- 统一 RAG / Skill Retrieval 的后端边界与可维护性

### 3.3 产品目标

- 把前端从“联调工作台”继续推进到“更成熟的工作台”
- 增强可观察性、可解释性、可治理性

### 3.4 发布目标

- 形成一个可持续演进的本地单用户 MVP 内测版
- 为后续真正的“成品版”打下稳定基础

---

## 4. 总体开发原则

### 4.1 继续坚持后端质量优先

前端已经能够驱动和观察主链路，因此后续优先级要回到：

- 检索质量
- 草稿质量
- 治理质量
- 测试质量

其中两个明确方向是：

- Skill Gateway 逐步对齐 AutoSkill 的 `rewrite -> hybrid retrieve -> selection -> inject`
- Skill Evolution 逐步对齐 AutoSkill 的异步 `extract -> judge -> merge`

### 4.2 所有阶段都要有验收标准

每个较大阶段必须满足至少一项：

- 可运行
- 可验证
- 可回归
- 可演示

### 4.3 保持文件优先与可审查性

后续新增能力仍需坚持：

- 本地文件可查看
- 状态可追踪
- 结果可审查
- 不隐藏在黑盒内部

### 4.4 按阶段提交 Git

后续开发继续遵循当前节奏：

- 每完成一个较大阶段，单独提交
- commit message 使用规范命名
- 阶段结束后推送到 GitHub

建议沿用：

- `feat(frontend): ...`
- `feat(backend): ...`
- `chore(project): ...`
- `docs(project): ...`
- `test(backend): ...`

---

## 5. 后续阶段规划

## 5.1 Phase A：后端检索质量升级

### 目标

把 Skill / Memory / Knowledge 检索从“可用”提升到“更稳”，并明确区分：

- Memory / Knowledge RAG
- Skill Gateway Retrieval

### 主要任务

- 把 Skill Gateway 检索升级为 `LlamaIndex` 驱动的 hybrid retrieval
- 让技能索引覆盖 `name / description / tags / triggers / Goal / Constraints / Workflow`
- 保留 `skill selection` 作为 retrieval 之后的第二道过滤层
- 调整 selection 阈值、排序策略和 hit reason 展示
- 补 Gateway 检索质量相关回归测试

### 当前状态

该阶段已部分推进：

- 已引入共享文本匹配模块
- 已改进 skill retrieval 的加权逻辑
- 已补基础 retrieval 测试
- `memory` / `knowledge` RAG 已切换到 `LlamaIndex`

### 后续补充

- 增加更多中文/英文任务样例
- 增加针对 rewrite / summary / weather / translate 的召回验证
- 完成 skill retrieval 的 dense + BM25 + fusion
- 将 top-1 skill hit 作为 evolution 的辅助 identity context

### 验收标准

- 常见 stop words 不再造成明显误命中
- `rewrite` 类 query 优先命中 `professional_rewrite`
- `weather` 类 query 优先命中 `get_weather`
- Gateway 检索后端不再主要依赖手写关键词规则
- 回归测试可稳定通过

---

## 5.2 Phase B：Draft Extractor 升级

### 目标

把当前关键词触发式草稿生成，升级为后台异步 `ExtractorSubAgent`，更接近“从多轮对话中提炼可复用规则”的版本。

### 主要任务

- 新增 `EvolutionRunner` 或同类后台调度模块
- 把 extraction 从同步工具函数升级为异步子智能体执行
- 扩展输入范围，不只看单轮 user message
- 引入最近多轮上下文
- 让 user messages 成为主证据，assistant 输出只作上下文
- 利用 top-1 retrieval hit 作为辅助 identity context
- 识别 durable / reusable / one-off 的差异
- 更稳定地生成：
  - goal
  - constraints
  - workflow
  - why_extracted
  - confidence

### 当前问题

当前 `draft_extractor.py` 仍主要依赖关键词映射：

- 泛化能力弱
- 容易误触发
- 不能真正反映“长期工作方式”
- 仍未形成独立的后台 evolution 编排

### 验收标准

- 多轮对话能够生成更合理的草稿候选
- 单次偶发请求不应轻易触发 Draft
- rewrite / summary / translation / weather 等典型场景输出更稳定
- 前台响应不需要等待 extraction 完成
- 可通过本地 runner + API 测试验证

---

## 5.3 Phase C：Skill Judge / Related Skill Finder 升级

### 目标

让 `JudgeSubAgent` 驱动的 `add / merge / ignore` 判断更稳，减少错误治理。

### 主要任务

- 提升 related skill 的召回质量
- 细化相似度判断逻辑
- 明确 add / merge 的边界条件
- 将 judge 从简单阈值判断升级为独立治理判断模块
- 增强 judge 的 reason 质量

### 当前问题

- 当前 related skill 基本复用 retrieval
- 当前 judge 主要依赖简单 score 阈值
- 容易出现“有点像就 merge”或“其实该 merge 却 add”问题

### 验收标准

- 典型草稿能更稳定给出合理 action
- reason 能解释为什么 add / merge / ignore
- 减少明显误 merge
- Judge 的输入输出可以独立测试和回放

---

## 5.4 Phase D：Skill Merge / Versioning 升级

### 目标

把治理后的结果从“能写进去”提升到“更可维护、更可回溯”。

### 主要任务

- 优化 merge patch 结构
- 完善 version bump 规则
- 补 lineage 与 merge history 的一致性约束
- 为 rollback 预留接口与数据结构
- 将 merge 动作收口到 `MergerSubAgent` / merger service 的明确边界中

### 当前问题

- 当前 merge 更偏“追加内容”
- 当前 versioning 还缺少完整 diff / rollback 能力

### 验收标准

- Merge 后 skill 文件结构可读性保持稳定
- version / lineage / merge history 一致
- 后续可扩展到 rollback
- Merge 不再等同于“向 skill 文件追加内容”

---

## 5.5 Phase E：测试体系补齐

### 目标

建立从“能跑”到“能持续回归”的工程保障。

### 主要任务

- 补 Gateway 单元测试
- 补 Draft / Governance 集成测试
- 补 Registry 一致性测试
- 补前端关键交互测试
- 整理测试产生的临时状态和清理策略

### 当前已有基础

- `tests/test_api_smoke.py`
- `tests/test_retrieval_quality.py`
- `tests/run_backend_local.py`

### 验收标准

- 核心链路至少具备基本回归保障
- 检索质量、草稿生成、治理动作可自动化验证
- 测试不会频繁污染工作区
- Gateway / Evolution 的关键决策路径可回放

---

## 5.6 Phase F：前端产品化打磨

### 目标

把当前“联调工作台”继续向“更成熟的产品工作台”推进。

### 主要任务

- 优化信息层级与布局
- 增强错误反馈、加载反馈、空状态
- 改进 Draft / Skill Inspector 的可读性
- 提升治理操作后的状态联动体验
- 增强前端测试与可维护性

### 当前已有基础

- Session list
- Chat panel
- SSE streaming
- Activated Skills
- Session Drafts
- Draft Governance
- Draft / Skill Inspector
- usage / lineage / stale audit

### 验收标准

- 前端不只是“能测”，而是“更好用”
- 关键状态切换更清晰
- Inspector 内容更容易理解
- 治理与观察流程更顺畅

---

## 6. 建议执行顺序

建议下一阶段继续按以下顺序推进：

```text
Phase A  Gateway LlamaIndex 检索升级
-> Phase B  ExtractorSubAgent + Evolution Runner
-> Phase C  JudgeSubAgent / Related Skill Finder 升级
-> Phase D  MergerSubAgent / Versioning 升级
-> Phase E  测试体系补齐
-> Phase F  前端产品化打磨
```

这样安排的原因是：

- 先提升“命中质量”
- 再提升“沉淀质量”
- 再提升“治理质量”
- 最后补“工程保障”和“产品体验”

---

## 7. 阶段性交付要求

每完成一个较大阶段，至少完成以下动作：

### 7.1 代码交付

- 完成该阶段核心功能
- 本地验证通过
- 不引入明显回归

### 7.2 测试交付

- 至少补一组对应测试
- 或补一个可重复执行的验证脚本

### 7.3 Git 提交

- 使用规范 commit message
- 提交单一阶段内容
- 推送到 GitHub

### 7.4 文档同步

- 必要时同步 README
- 必要时同步 `ClawForge 当前项目开发进度总结.md`
- 重要阶段建议同步本开发计划文档

---

## 8. 建议的近期优先级

如果只看“接下来最值得做的三件事”，建议优先：

### 1. 完成 Skill Gateway 的 LlamaIndex Hybrid Retrieval

原因：

- 它决定在线命中质量
- 也是后续 related skill retrieval 与 extraction identity context 的基础

### 2. 完成 ExtractorSubAgent + EvolutionRunner

原因：

- 它决定系统是不是在“学对东西”
- 当前 extraction 仍是最明显的 MVP 痕迹之一

### 3. 完成 Judge / Related Skill Finder 升级

原因：

- 它决定草稿最终会不会错误进入技能库
- 这会直接影响 skill 污染风险

---

## 9. 当前版本的阶段定义

基于现状，建议将当前项目定义为：

```text
ClawForge MVP 内测版
```

其特点是：

- 后端主链路已打通
- 前端可测试工作台已落地
- 核心能力可演示
- 仍需继续优化效果质量、治理质量、测试体系和产品体验

---

## 10. 总结

ClawForge 已经走过“从文档到可运行 MVP”的关键阶段，当前开发重点不再是简单补模块，而是：

```text
把 MVP 做稳
把关键质量做上去
把工作台做得更可用
把系统从演示态推向更可靠的内测态
```

因此，后续项目开发应围绕：

- 检索质量
- 草稿质量
- 治理质量
- 测试质量
- 产品体验

五个方向持续推进，并保持“每个阶段都有代码、测试、提交和文档同步”的开发节奏。
