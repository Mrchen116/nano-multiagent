# refactor-489-M15 — Progress

## Baseline / Audit

- Claim: M15 当前 25 个 settings test files 可运行，但混有 mock shape、旧 prototype/CSS/元素缺席、milestone 命名与跨文件重复断言；真实 account/policies/agent/node/channel/realtime 风险可在同域更直接的 interaction/API-state tests 中保留。
- Baseline: `origin/unit/refactor-489@8ceeb39eb`。
- Method: 读取 motivation/design/M1 处置规范、testing 与 IM current specs；枚举 25 files / 6036 lines / 132 tests；按测试名、SUT、用户/API seam 和重复 owner 审计；复用主仓 frontend `node_modules` 的 ignored symlink 运行全域。
- Result: 基线 PASS，`25 passed` files、`132 passed` tests（6.37s）。输出同时暴露大量 React `act(...)` 与无效 user-stream fetch 告警，主要来自只渲染旧布局/缺席状态但不建立完整交互 seam 的测试。
- Limit: 本 milestone 零 UI delta，不以真实浏览器或截图重新验收视觉；完成标准是保留可重复的 interaction/API-state regression 并让 build/全域 Vitest 通过。

## R1 — 删除设置壳、mock 与历史视觉终态

- 状态: DONE
- Context: settings 树含 mock fixture 字段 shape、旧二级导航缺席、mobile DOM 缺席、node 不请求 agent list，以及 Account/Nodes/Agents list 的旧 prototype 卡片、CSS class、icon/KPI/chevron 等交付终态；这些断言不经过当前保存或 API 状态 seam。
- Decision: 删除 4 个纯终态文件；Account 收敛为加载后保存与 Discard，Nodes 收敛为在线创建入口、alias PATCH、status/error/empty，Agents list 收敛为列表打开详情、empty 与 load-error retry。移除退役 endpoint 负断言和 CSS palette 检查。
- Rationale: 页面布局或某元素“不存在”会被任何等价 UI 重构击穿，却不能证明设置可用；同一渲染成本应观察用户能否改值、提交、进入对象，或从失败恢复。删除项对应的产品风险要么不存在，要么归 M16 app/router/responsive owner。
- Evidence:
  - Tests: Account/Agents list/Nodes/Policies 5 files、9 tests 全绿（1.91s）。
  - Entry: jsdom 从真实 app routes 进入 `/settings/account`、`/settings/agents`、`/settings/nodes`、`/settings/policies`；执行输入、选择、保存、Discard、打开详情和 Retry。
  - Frontend State Matrix: default、empty、error、disabled（offline node / clean form）、submitting 后回显；visual/mobile N/A（无 UI delta）。
  - Browser QA: N/A；仅测试资产改动，未改组件或 UI。
  - E2E/Regression: 保留 page-level interaction regression；未新增浏览器 E2E，因没有产品行为变化。
  - Visual/Interaction: 交互由 Testing Library role/label 驱动；无截图或 reference。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `7c51d7058`。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 合并 Agent form/API 的 feature、allowlist、preview 与历史迁移重复。

## R2 — 合并 Agent 配置与 API 重复保护

- 状态: TODO

## R3 — 收敛 channel 状态并完成全域门禁

- 状态: TODO

## Promotion Candidates

None.
