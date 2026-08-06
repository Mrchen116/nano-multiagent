# bugfix-505-M1 — Progress

## 启动证据

- Sync Gate: `unit/bugfix-505`、`origin/unit/bugfix-505` 均为 `058564a0ce643ca0bfda4f1df46ba6116b258d4f`。
- Baseline: `npm test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-create.test.tsx`，2 files / 25 tests passed；存在基线已有 React `act(...)` warnings，无失败。
- Scope: 仅 Agent detail async shell、shared desktop rail 视觉语义、定向测试、M1 过程/evidence 与 lite `fix.md` 回填。

## R1 — 固化异步壳层回归并实现连续 desktop shell

- Status: DONE
- Context: `AgentDetailPage` 在构造 desktop layout 前直接返回初始 loading/error，导致切换 Agent 时连续导航消失；移动端仍须保持单栏。
- Decision: 把无数据 loading、initial error 和不完整 detail 状态统一送入 responsive state shell。desktop shell 先渲染既有 `AgentsRailDesktop`，内容区显示居中的轻量 loading card 或 error card；mobile 只渲染同一内容状态，不渲染 rail。
- Rationale: 修复根因所在的 early-return 边界，复用同一 rail，不复制列表或更改正常详情表单。
- Evidence:
  - Tests: 红测 `agent-detail-loading-shell.test.tsx` 3/3 失败，分别显示 desktop loading 无 rail、desktop error 无 rail、mobile 仍为裸 loading 文本；Green 后 3/3 passed。
  - Entry: 组件入口覆盖 route param `agent-two` 的无数据 pending 与 initial error；真实浏览器入口由 R3 验收。
  - Frontend State Matrix: loading/error/missing data/desktop/mobile 已覆盖；default 保持既有 detail 测试；其他状态 N/A，见 tasks.md。
  - Browser QA: R3 执行。
  - E2E/Regression: `src/IM/frontend/src/features/settings/agents/agent-detail-loading-shell.test.tsx`；`npm test -- src/features/settings/agents/agent-detail-loading-shell.test.tsx`。
  - Visual/Interaction: loading 使用窄幅白色面板、轻边框/阴影和单个 accent spinner；error 使用同一内容区与可重试卡片。R3 保存截图。
  - Prototype Comparison: 派发 reference contract 的 shell/mobile 项在组件层 match；浏览器对照在 R3。
- Rollback: revert 本 roadpoint commit，恢复旧 early returns。
- Commits: pending (this commit)
- Next: R2 修正 rail 视觉语义。

## R2 — 修正 rail 身份行视觉语义

- Status: TODO

## R3 — 真实浏览器验收与交付门禁

- Status: TODO

## Promotion Candidates

None.
