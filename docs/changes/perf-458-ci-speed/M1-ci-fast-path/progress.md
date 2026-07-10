# perf-458-M1 — Progress

## Baseline

- Context: 在任何实现前复跑 unit 分支现有门禁，确认不是在红色基线上优化。
- Evidence:
  - Python: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e"` → 3444 passed, 2 skipped, 22 deselected in 149.34s（wall 151.14s）。
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .` 与 `ruff format --check .` → 全绿，769 files already formatted。
  - Frontend: `npm ci && npm run test` → 63 files / 615 tests passed，vitest 13.63s（wall 15.19s）。
- Scope guard: 仅修改 design Milestone 表列出的 workflow、pyproject 和七个测试文件；`src/`、`docs/specs/`、前端源码均不修改。

## R1 — 移除 IM integration 的 live-config 固定等待

- 状态: DONE
- Context: 五条旅程测试读取的只是持久化 `profile_version`，但默认 `source=live` 会先向同一测试线程持有的 Gateway websocket 发 RPC；主线程此时阻塞在 HTTP GET，无法消费并回复 frame，因此每条稳定吃满 5 秒 fallback。
- Decision: C1 先保留未优化实现并对五个完整测试文件做 timing profile，证明慢点精确落在 design 指定的五条目标旅程，而不是其它 fixture 或产品路径。
- Rationale: 本 roadpoint 是测试驱动方式的性能重构，产品行为不变且不新增生产能力；C1 使用 Verify 基线而非人为制造产品红测，C2 只改已有旅程测试的配置读取方式。
- Evidence:
  - Tests: 未优化五个文件共 12 tests passed in 30.00s（wall 31.43s）；改写后连同专门 live-config 文件共 28 tests passed in 8.20s（wall 9.55s）。
  - Entry: 五条目标旅程继续通过真实 TestClient HTTP + Gateway websocket 入口，改写后单条为 0.21–0.23s；创建、PATCH、`config.sync` 与 relay 断言均保留。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: `pytest -q --durations=20 --durations-min=0.1` 对五个目标文件及 `test_agent_config_api.py` 全绿；专门 live-config 用例 `test_get_agent_config_prefers_live_gateway_snapshot` 继续通过（0.21s），证明协议覆盖未被删除。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型/reference）。
- Rollback: 回退 `0e43ac7d` 即恢复五条测试原有 live-config 往返；产品代码从未改变。
- Commits: C1=`19ae3ed7`，C2=`0e43ac7d`，C3=本提交。
- Next: R1 已完成；进入 R2，量取 ShellRunner 两条负断言与输出上限测试的未优化耗时。

## R2 — 消除 ShellRunner 与输出上限测试的确定性成本

- 状态: DONE
- Context: 两条 stop 负断言用 `Event.wait(5.0)` 睡满窗口证明“没有失败回调”，实际 monitor 通常更早完成；输出上限测试以 1 KiB 块反复打开文件约 26 万次才越过 256 MiB，测试成本远大于被测行为所需。
- Decision: C1 保留未优化测试并独立 profile 三条目标用例；C2 将 stop 测试等待 monitor 清理 `_stopped` 的完成条件，并在输出测试中先断言生产常量、再 monkeypatch 小上限覆盖边界。
- Rationale: 真实完成条件能同时证明 monitor 已走完所有终态分支；小上限不改变生产常量，仍在同一个 `BashFileOutput.append` 行为边界验证上限内保留与越界截断。
- Evidence:
  - Tests: 未优化三条目标测试 3 passed in 17.40s（wall 17.59s）；改写后 3 passed in 2.64s（wall 2.82s），完整 `test_platform_adapters.py` 23 passed in 7.86s。
  - Entry: N/A（本 roadpoint 只重写内部测试同步方式，不改变产品入口或 `src/`）。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 输出上限用例由 6.79s 降到 <0.005s；stop 静默用例由 5.33s 降到 0.33s；stop+timeout 清理由 5.22s 降到 2.23s（保留生产 SIGTERM 2 秒宽限路径）。ruff/format 对该文件全绿。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型/reference）。
- Rollback: 回退 `e82edf42` 恢复原有 `Event.wait(5.0)` 和 256 MiB 实写测试；生产代码不受影响。
- Commits: C1=`5a25350a`，C2=`e82edf42`，C3=本提交。
- Next: R2 已完成；进入 R3，记录当前 workflow 缺少 xdist/cache/durations 的 Verify 证据并完成 CI 接线。

## R3 — 接入 xdist、pip cache 与完整门禁

- 状态: TODO
- Next: R2 完成后记录 workflow 缺失能力并接线。
