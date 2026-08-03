# refactor-489-M15 — Progress

## Baseline / Audit

- Claim: M15 当前 25 个 settings test files 可运行，但混有 mock shape、旧 prototype/CSS/元素缺席、milestone 命名与跨文件重复断言；真实 account/policies/agent/node/channel/realtime 风险可在同域更直接的 interaction/API-state tests 中保留。
- Baseline: `origin/unit/refactor-489@8ceeb39eb`。
- Method: 读取 motivation/design/M1 处置规范、testing 与 IM current specs；枚举 25 files / 6036 lines / 132 tests；按测试名、SUT、用户/API seam 和重复 owner 审计；复用主仓 frontend `node_modules` 的 ignored symlink 运行全域。
- Result: 基线 PASS，`25 passed` files、`132 passed` tests（6.37s）。输出同时暴露大量 React `act(...)` 与无效 user-stream fetch 告警，主要来自只渲染旧布局/缺席状态但不建立完整交互 seam 的测试。
- Limit: 本 milestone 零 UI delta，不以真实浏览器或截图重新验收视觉；完成标准是保留可重复的 interaction/API-state regression 并让 build/全域 Vitest 通过。

## R1 — 删除设置壳、mock 与历史视觉终态

- 状态: TODO

## R2 — 合并 Agent 配置与 API 重复保护

- 状态: TODO

## R3 — 收敛 channel 状态并完成全域门禁

- 状态: TODO

## Promotion Candidates

None.
