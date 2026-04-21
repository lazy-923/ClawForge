# ClawForge 开发计划

## 1. 这份计划解决什么问题

这不是对旧阶段文档的机械续写，而是一份基于 **当前代码现状**、**PRD 目标** 和 **系统设计约束** 重新整理的执行计划。

它服务于三个目标：

1. 明确 ClawForge 现在已经做到了什么
2. 明确接下来真正值得做的开发主线
3. 给后续每一轮开发提供可执行、可验收、可提交的节奏

---

## 2. 当前项目判断

结合当前仓库代码与文档，ClawForge 现在不是“从零开始”，也不是“接近成品”，而是处于下面这个状态：

```text
后端主链路已跑通
Skill Gateway 与 Skill Evolution 已有首版实现
治理闭环与文件落盘已成形
前端已有可测试工作台
但系统整体仍停留在 MVP 到内测版之间
```

换句话说，项目已经跨过了“能不能做出来”的阶段，进入了“怎么把它做稳、做准、做得可持续演进”的阶段。

---

## 3. 当前代码基线

## 3.1 已经完成的部分

当前仓库已经具备以下真实能力，而不是文档层面的规划：

- FastAPI 后端主应用、路由和生命周期初始化
- 聊天主链路、会话持久化、SSE 输出
- Prompt 文件组装体系
- Skill Gateway：rewrite、retrieval、selection、context injection、last-hit
- Skill Evolution：draft extraction、related skill finding、judge、promote / merge / ignore
- Skill Registry：skills index、draft index、usage、merge history、lineage
- 文件优先的本地工件落盘
- 基础测试与本地验证脚本
- 前端联调工作台

对应的主要实现模块包括：

- `backend/api/`
- `backend/graph/`
- `backend/gateway/`
- `backend/evolution/`
- `backend/retrieval/`
- `tests/`

## 3.2 当前最重要的事实

从当前代码看，有几个关键事实必须作为后续计划的前提：

### 1. Skill Gateway 首版已经落地

`memory / knowledge / skill` 三类检索已经开始统一到同一类混合检索实现上，Skill Gateway 不再只是手写规则的占位层。

### 2. Evolution 首版已经落地

系统已经不是“聊天后同步生成 draft”的最早期形态，而是具备异步 `EvolutionRunner`、多轮消息抽取和 identity context 接入的首版学习链路。

### 3. Governance 闭环已经可运行

`promote / merge / ignore`、merge history、lineage、usage 等文件工件都已经存在，说明治理不是纸面功能。

### 4. 当前最大短板不是缺模块，而是缺质量保障

现在继续盲目加功能，收益会越来越低；更关键的是把已完成的链路做稳、做准、做得可回归。

---

## 4. 产品目标与工程边界

这部分不是重新发明需求，而是把 PRD 和设计文档里的要求落到执行边界上。

## 4.1 产品目标

ClawForge 要做的不是一个普通聊天壳，而是一个本地优先的 **Skill Gateway + Skill Evolution 工作台**。

系统最终应具备四类核心能力：

1. 在线请求能够稳定命中并注入最相关技能
2. 多轮交互能够沉淀出可复用的技能草稿
3. 草稿进入正式技能库前有可审查的治理过程
4. 技能的来源、合并、版本和历史都可追踪

## 4.2 工程边界

后续开发必须持续遵守以下边界：

- 本地优先
- 文件优先
- 可观察
- 可编辑
- 半自动演化
- 不把正式技能库变成黑盒自动写入系统

这意味着后续不应该为了“更智能”牺牲：

- 工件可读性
- 状态可追踪性
- 治理可控性
- 调试与回放能力

---

## 5. 当前核心问题

如果只看当前最影响项目质量的事情，主要有五类问题。

## 5.1 检索能力已经能用，但还不够稳

当前 Skill Gateway 已有首版能力，但还存在：

- 命中质量不够稳定
- 样本覆盖不足
- 中英文 query 验证不够
- selection 阈值和排序策略还偏粗
- hit reason 虽然存在，但还不够“可解释到能调”

这会直接影响在线回答质量，也会影响后续 evolution 的 identity context。

## 5.2 Draft 抽取已经异步化，但仍偏启发式

当前抽取能力能工作，但距离“从交互中学习工作方式”还有明显差距：

- 更像规则模板，不像真正的抽取器
- 对 durable / reusable / one-off 的区分还不够强
- 对多轮对话的结构化理解有限
- 缺少回放评估能力

## 5.3 Governance 已闭环，但决策可信度还不足

当前 add / merge / ignore 已可用，但还没有达到“长期运行也不容易污染技能库”的程度。

主要问题：

- add 和 merge 的边界还不够稳
- related skill 的召回质量还有提升空间
- judge reason 够用，但还不够强
- merge 的结构化程度仍然有继续提升空间

## 5.4 Versioning 已有记录，但还不是真正可演化

当前有 lineage、merge history、patch version 和 rollback 预留字段，但还缺：

- 实际可执行 rollback
- 更清晰的 diff / history 浏览
- 更强的版本一致性约束

## 5.5 测试体系仍然是最大的工程短板

这是当前最现实、最值得优先补的部分：

- 测试分散，尚未形成完整回归网络
- 集成链路测试还不够系统
- 临时文件和真实工作区之间的隔离还不够干净
- 关键决策路径缺少更明确的回放样本

---

## 6. 总体开发策略

接下来的开发不应按“继续堆功能模块”的思路走，而应按下面的顺序推进：

```text
先补工程保障
再提升在线命中质量
再提升学习与治理质量
最后补版本演化与产品体验
```

原因很简单：

- 没有测试保障，继续优化 A/B/C/D 只会越来越难验证
- 没有稳定的在线检索质量，后续 evolution 的判断基础也会偏
- 没有可靠治理，就会把错误经验沉淀进技能库

所以，当前主线不是“再发明一个新阶段”，而是围绕几个工作流持续推进。

---

## 7. 后续开发按五条工作流推进

## 工作流 A：回归测试与工程保障

这是当前第一优先级。

### 目标

把当前“能跑”的系统变成“能稳定回归”的系统。

### 要做的事

- 补 Gateway 单元测试
- 补 Draft 到 Governance 的集成测试
- 补 Registry / Lineage / Merge History 一致性测试
- 建立测试隔离策略，避免污染真实目录
- 整理本地验证入口，形成固定回归执行方式

### 完成标志

- 后端关键链路至少都能自动化验证一遍
- 测试执行后不会频繁留下真实垃圾状态
- 每次改检索、抽取、治理逻辑时，都有明确的回归反馈

## 工作流 B：Serving Path 质量提升

这条工作流对应在线效果。

### 目标

把当前的 Skill Gateway 从“可用首版”提升到“更稳、更可调”的状态。

### 要做的事

- 扩充 skill retrieval 的 query 样本
- 调整 selection 阈值与排序逻辑
- 改善 hit reason 表达
- 补充典型任务场景验证
- 继续统一 skill / memory / knowledge 检索边界

### 重点场景

- rewrite
- summary
- translation
- weather
- stop words 干扰
- 中英文混合表达

### 完成标志

- 常见 query 的命中明显更稳定
- 误召回下降
- selection 逻辑更可解释
- 检索问题能通过测试和样本快速定位

## 工作流 C：Learning Path 质量提升

这条工作流对应 Skill Draft 的真实性和可复用性。

### 目标

让系统更像是在“提炼稳定工作方式”，而不是“捕捉一次性关键词”。

### 要做的事

- 提升 Extractor 的多轮归纳能力
- 强化 reusable / durable 识别
- 提高 identity context 的利用质量
- 增加回放样本
- 逐步向更明确的 `ExtractorSubAgent` 形态演进

### 完成标志

- draft 候选更像技能而不是单次请求摘要
- one-off 污染显著减少
- 抽取逻辑可以通过样本回放稳定评估

## 工作流 D：Governance 与 Versioning 提升

这条工作流对应技能库长期健康度。

### 目标

降低误 merge、误 add，逐步把版本演化做成真正可信的工件系统。

### 要做的事

- 继续提升 related skill 召回质量
- 细化 add / merge / ignore 边界
- 提升 judge 的 reason 质量
- 优化 merge patch 结构
- 增强 version / lineage / history 一致性
- 为 rollback 与 diff 打基础

### 完成标志

- 治理建议更稳定
- 技能库污染风险降低
- merge 结果更可读、更可追踪

## 工作流 E：前端工作台产品化

这条工作流目前不是第一优先级，但不能长期忽略。

### 目标

让工作台从“联调工具”逐步变成“真正可用的技能工作台”。

### 要做的事

- 优化信息层级
- 提高 Draft / Skill Inspector 可读性
- 增强错误、加载、空状态反馈
- 改进治理动作后的状态联动
- 补充前端关键交互测试

### 开始时机

建议在工作流 A 稳定、工作流 B/C 至少完成一轮质量提升后，再集中投入。

---

## 8. 里程碑安排

为了让执行更清楚，后续建议按四个里程碑推进，而不是继续堆很多抽象 phase 名称。

## 里程碑 M1：测试网络成形

### 核心目标

先把系统变成“可持续回归”的状态。

### 交付内容

- Gateway 关键路径测试
- Draft / Governance 集成测试
- Registry 一致性测试
- 测试隔离与清理策略

### 这是当前最近的目标

当前开发应首先完成 M1。

## 里程碑 M2：在线命中质量显著提升

### 核心目标

让 Serving Path 的稳定性明显上一个台阶。

### 交付内容

- 更稳的 retrieval / selection
- 更清晰的 skill hit reason
- 更完整的 query 场景覆盖

## 里程碑 M3：学习与治理质量显著提升

### 核心目标

让系统更可靠地“学对东西”，并减少技能库污染。

### 交付内容

- 更强的 draft extraction
- 更稳的 judge
- 更合理的 related skill 召回
- 更强的 merge 结构化结果

## 里程碑 M4：版本演化与工作台体验补齐

### 核心目标

把项目从内测雏形继续推向更成熟的单用户工作台。

### 交付内容

- rollback / diff 的进一步能力
- 前端治理体验优化
- 更完整的观察、追踪与编辑体验

---

## 9. 最近一段时间的具体执行顺序

如果只看接下来最值得做的几件事，建议顺序是：

### 1. 完成 M1

也就是优先把测试体系补齐到“足以支撑持续开发”的程度。

### 2. 基于测试回头继续打磨 Gateway

先把在线命中质量再做稳一轮。

### 3. 再继续优化 Extractor / Judge / Merger

有了测试和更稳的 Gateway，再继续做 Learning Path 才更容易得到真实收益。

### 4. 最后再集中做前端产品化

前端当前已经够用来联调，不需要抢在后端质量之前成为主线。

---

## 10. 开发方式约定

## 10.1 提交节奏

每完成一个里程碑或一个较完整的工作包，就单独提交一次 Git。

建议使用规范 commit message：

- `feat(backend): ...`
- `test(backend): ...`
- `refactor(backend): ...`
- `docs(project): ...`
- `chore(project): ...`

## 10.2 验收方式

每个阶段性工作包至少满足以下一项：

- 可运行
- 可验证
- 可回归
- 可演示

如果一个改动不能被验证，就不算真正完成。

## 10.3 文档同步方式

当前以 `docs/ClawForge 项目开发计划.md` 作为主计划文档。

后续每当项目状态发生明显变化，应至少同步：

- 当前目标是否变化
- 当前工作流优先级是否变化
- 当前里程碑是否完成

## 10.4 环境约定

当前后端开发环境默认使用：

- conda 环境：`mini-claw`
- Python：`D:\develop\miniconda3\envs\mini-claw\python.exe`

---

## 11. 最终一句话

ClawForge 接下来的开发重点，不是再去证明“这套系统能不能工作”，而是把已经存在的 **Skill Gateway + Skill Evolution + Governance** 主链路，逐步建设成一个 **可回归、可解释、可治理、可持续演进** 的本地技能工作台。
