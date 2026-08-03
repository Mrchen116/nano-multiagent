# refactor-489-M13 — Progress

## Baseline / Audit

- Claim: M13 派发域在正确 worktree venv PATH 下可稳定收集/运行，并已定位退役入口、错层 helper 自测、脚本文本/轮询次数断言、并发误杀风险和无自动消费者的一次性 fixtures。
- Baseline: `origin/unit/refactor-489@52af340769`（初始测试基线在同步前 `ce66aa759`，其后仅吸收相邻 milestone）。
- Method: 完整读取 motivation/design/M1 处置规范、testing/worktree-runtime/e2e catalog 与 Gateway current specs；枚举 49 个 M13 tracked paths；运行 scoped pytest 与 collect-only；搜索 script text/private/test-import/retired mode/fixture consumers。
- Result: PATH 按文档加入主仓 `.venv/bin` 后 PASS：`23 passed, 18 skipped`（41 collected）；默认 skip 为显式 live-proxy gate。首轮未带该 PATH 时 fake-LLM fixture 因 `python3` 缺 PyYAML 报错，属已纠正的运行环境前置条件，不是测试回归。
- Limit: 基线未启动 `:4000` 真 LLM proxy；fake-LLM 真栈已执行。R4 将另跑不依赖真 proxy 的 lifecycle 与 resilience live paths。

## R1 — 删除退役、错层与一次性测试资产

- 状态: DOING

## R2 — 用真实栈结果取代脚本文本与轮询实现断言

- 状态: TODO

## R3 — 收敛 finalizer 与 interrupt 的进程所有权保护

- 状态: TODO

## R4 — catalog、全域与 live 证据收口

- 状态: TODO

## Promotion Candidates

None.
