# ClawForge 前端开发计划

这个 README 用来记录 ClawForge 前端工作台的开发方向、架构约束和验证方式。

后端现在已经足够支撑单用户本地运行，前端不应该只停留在“调试页面”，而应该逐步变成真正可用的本地工作台。当前不需要删除整个 `frontend/` 项目；Next.js 项目骨架、依赖锁文件、lint/typecheck、smoke 脚本和 Playwright 配置都应该保留，主要重构和扩展发生在 `src/` 应用层。

## 当前判断

现有前端已经能验证后端主链路，但仍有继续产品化的空间：

- `src/lib/api.ts` 已开始承接后端 API 调用。
- `src/lib/types.ts` 已开始集中维护后端响应类型。
- `src/lib/sse.ts` 已开始拆出 SSE 解析逻辑。
- `src/app/page.tsx` 仍然承担较多工作台状态和 UI，需要后续继续按 feature 拆分。
- `src/app/globals.css` 仍然包含大部分视觉系统和组件样式。
- 当前 UI 已覆盖 health、sessions、chat streaming、gateway hit、memory candidates、draft governance、skill inspector、merge preview 和 rollback 入口。
- Knowledge 和更完整的文件编辑工作流还没有成为一等视图。

结论：保留项目壳，继续把应用层拆成清晰模块。

## 应保留

除非有明确原因，以下文件和目录应继续保留：

- `package.json`
- `package-lock.json`
- `next.config.mjs`
- `eslint.config.mjs`
- `tsconfig.json`
- `playwright.config.ts`
- `scripts/smoke-backend.mjs`
- `tests/e2e/`
- `.env.example`

现有测试可能会随着 UI 演进调整断言，但测试框架本身有价值。

## 继续重构

后续重点不是继续扩大单个页面组件，而是拆分边界：

- `src/app/page.tsx`：继续瘦身，迁移到 feature 组件。
- `src/app/globals.css`：逐步拆成更清晰的基础样式和组件样式。
- 新增工作流时，优先放入 `features/` 或 `lib/`，避免重新堆回 route component。

## 目标结构

推荐结构：

```text
frontend/src/
+-- app/
|   +-- layout.tsx
|   +-- page.tsx
|   +-- globals.css
+-- components/
|   +-- app-shell.tsx
|   +-- button.tsx
|   +-- panel.tsx
|   +-- status-pill.tsx
|   +-- tabs.tsx
+-- features/
|   +-- chat/
|   +-- sessions/
|   +-- memory/
|   +-- drafts/
|   +-- skills/
|   +-- knowledge/
+-- lib/
    +-- api.ts
    +-- sse.ts
    +-- types.ts
```

这不是为了引入复杂框架，而是为了避免后端契约、UI 状态和视觉组件重新挤在一个文件里。

## 工作台信息架构

第一屏应该是实际可操作的工作台，不是 landing page。

推荐布局：

- 左侧：sessions、backend health、快速创建 session。
- 中间：chat stream、retrieval events、active gateway decision、composer。
- 右侧：memory candidate、draft、skill 或 knowledge 的上下文 inspector。
- 下方或 tab 区域：Memory、Drafts、Skills、Knowledge、Audit。

界面气质应接近本地操作控制台：信息密度足够，重复使用舒服，状态清楚。

## 第一阶段功能范围

前端优先覆盖后端已经存在的能力：

- Health：`GET /api/health`
- Sessions：列表、创建、重命名、读取消息/history
- Chat：SSE stream，事件包括 `skill_hit`、`retrieval`、`token`、`title`、`done`
- Gateway：最近一次 hit inspection
- Memory：候选列表、创建候选、promote、ignore
- Drafts：列表、详情、promote、merge preview、merge、ignore
- Skills：列表、usage、lineage、merge history、rollback、stale audit
- Files：读取和保存允许范围内的 workspace/memory/skills/knowledge 文件
- Knowledge：至少展示真实可用入口或诚实的空状态，不伪造后端还没有的能力

不要为后端不存在的能力做假按钮。未来功能可以有清晰空状态，但 API 契约要保持真实。

## API 层规则

统一使用 `src/lib/api.ts` 作为 typed API 层。

规则：

- UI 组件不直接硬编码 fetch URL。
- 后端响应类型放在 `src/lib/types.ts`。
- SSE 解析放在 `src/lib/sse.ts` 或 `features/chat/`。
- API 边界负责把错误整理成用户可读信息。
- 前端事件处理要匹配当前后端，不沿用旧假设。

当前 chat stream 事件：

```text
process
skill_hit
retrieval
token
title
done
```

## 状态管理规则

避免回到 20 多个 `useState` 都堆在 route component 的状态。

建议：

- 独立 UI 状态靠近拥有它的 feature component。
- 多 pane 共享的状态放在小型 parent shell。
- 每个 feature 有清晰的 reload 函数，不依赖一个巨大 bootstrap 做所有事情。
- 暂不引入全局状态库，除非真的出现跨模块复杂共享需求。

## 视觉方向

ClawForge 是本地工作台，不是营销页。

准则：

- 使用全高工作台布局。
- 优先使用紧凑面板、表格、列表、inspector、tabs 和 split panes。
- 避免过大的 hero 区域。
- 避免嵌套卡片和纯装饰表面。
- 使用克制颜色，但状态提示要明确。
- 桌面端要适合密集阅读，移动端要可用。
- 操作状态要明确：loading、disabled、pending、promoted、merged、ignored、failed。

## 测试和验证

前端最小验证流程：

```powershell
npm run lint
npm run typecheck
npm run build
npm run test:smoke
npm run test:e2e
```

说明：

- `test:smoke` 从 Node 侧验证后端 API 合约。
- `test:e2e` 验证浏览器中的工作台主路径。
- e2e 应尽量使用 mock LLM 配置，避免真实模型波动影响测试稳定性。

后续 Playwright 应覆盖：

- 工作台加载并显示 backend health。
- 可以创建 session。
- chat message 可以收到响应。
- gateway hit 和 retrieval events 可见。
- memory candidates 可列出和治理。
- drafts 可检查。
- merge preview 和 rollback 控件只在有效场景出现。

## 里程碑

### M1：前端骨架

- 将 API 类型和 fetch helper 拆到 `lib/`。
- 用 app shell 替代巨大的 route component。
- 保留当前 chat/session happy path。
- 保持 lint、typecheck、build、smoke、e2e 可运行。

### M2：核心工作台

- 完善 Memory candidate 视图。
- 完善 Draft 列表、详情和治理视图。
- 完善 Skill inspector，包括 usage、lineage、merge history、rollback。
- 完善 Gateway decision 和 retrieval event inspection。

### M3：产品打磨

- 改进 empty/loading/error 状态。
- 完善 merge preview / diff 体验。
- 按需增加允许文件的编辑保存能力。
- 改进响应式布局。
- 扩展 Playwright 主流程覆盖。

### M4：Knowledge 与安全 UX

- 增加与当前后端能力匹配的 Knowledge 视图。
- 明确展示工具安全和后端运行模式。
- 增加 stale skills、rollback history、风险操作等审计视图。

## 决策

不要删除整个前端项目。

继续以现有 Next.js 项目骨架为稳定基础，逐步重建和拆分 `src/` 应用层。
