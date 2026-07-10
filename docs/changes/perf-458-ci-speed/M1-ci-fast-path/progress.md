# perf-458-M1 — Progress

## Baseline

- Context: 在任何实现前复跑 unit 分支现有门禁，确认不是在红色基线上优化。
- Evidence:
  - Python: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e"` → 3444 passed, 2 skipped, 22 deselected in 149.34s（wall 151.14s）。
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .` 与 `ruff format --check .` → 全绿，769 files already formatted。
  - Frontend: `npm ci && npm run test` → 63 files / 615 tests passed，vitest 13.63s（wall 15.19s）。
- Scope guard: 仅修改 design Milestone 表列出的 workflow、pyproject 和七个测试文件；`src/`、`docs/specs/`、前端源码均不修改。

## R1 — 移除 IM integration 的 live-config 固定等待

- 状态: DOING
- Context: 五条旅程测试读取的只是持久化 `profile_version`，但默认 `source=live` 会先向同一测试线程持有的 Gateway websocket 发 RPC；主线程此时阻塞在 HTTP GET，无法消费并回复 frame，因此每条稳定吃满 5 秒 fallback。
- Decision: C1 先保留未优化实现并对五个完整测试文件做 timing profile，证明慢点精确落在 design 指定的五条目标旅程，而不是其它 fixture 或产品路径。
- Rationale: 本 roadpoint 是测试驱动方式的性能重构，产品行为不变且不新增生产能力；C1 使用 Verify 基线而非人为制造产品红测，C2 只改已有旅程测试的配置读取方式。
- Evidence:
  - Tests: 五个文件共 12 tests passed in 30.00s（wall 31.43s）。
  - Entry: 目标五条旅程均通过真实 TestClient HTTP + Gateway websocket 入口，单条分别为 5.23–5.27s；其它同文件旅程均为 0.21–0.30s。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: `pytest -q --durations=0` 对五个 integration 文件全绿；目标分别为 create-agent 5.25s、direct-chat config-sync 5.25s、group-chat config-sync 5.27s、heartbeat config-sync 5.23s、roundtrip config-sync 5.23s。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型/reference）。
- Rollback: 回退本 roadpoint C1 Verify commit 只会移除 timing 记录，不影响代码。
- Commits: C1=待本提交落定，C2=待完成，C3=待完成。
- Next: 把五处持久化版本读取改为 `source=mirror`，删除随之失效的 live RPC frame 往返并复测专门 live-config 测试。

## R2 — 消除 ShellRunner 与输出上限测试的确定性成本

- 状态: TODO
- Next: R1 完成后量取三条目标测试的未优化耗时，提交 Verify 证据。

## R3 — 接入 xdist、pip cache 与完整门禁

- 状态: TODO
- Next: R2 完成后记录 workflow 缺失能力并接线。
