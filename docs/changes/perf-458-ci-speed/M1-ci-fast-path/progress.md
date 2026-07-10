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

- 状态: DOING
- Context: Python job 的质量门禁完整但仍串行执行；`setup-python` 没有 pip cache，pytest 命令也没有并行调度或慢用例摘要。串行本地基线为 149.34s，已无法满足 90 秒远端目标。
- Decision: 保留单一 `Python checks` job 和原 lint 顺序；仅在 dev 依赖增加 `pytest-xdist>=3,<4`，在 setup-python 启用以 `pyproject.toml` 为键来源的 pip cache，并把同一完整 non-e2e 命令接为固定 6 worker worksteal + durations。
- Rationale: 单 job 不改变 branch protection check 名称或覆盖范围；4-worker 远端稳定但慢，8-worker 远端触发并发敏感测试，6-worker 是不修历史测试、不引入复杂分组的最小折中。
- Evidence:
  - Tests: 6-worker 完整 non-e2e 连续两轮均为 3444 passed, 2 skipped，分别 22.95s（wall 23.76s）与 22.15s（wall 22.78s）；上述两条 n=8 失败测试以 n=6 定向复跑 2 passed in 1.66s。完整串行为 3444 passed, 2 skipped in 104.81s；ruff 两门全绿；frontend 63 files / 615 tests passed in 12.02s（wall 13.09s）。
  - Entry: GitHub Actions `.github/workflows/ci.yml` 是贡献者唯一 CI 入口；job 名保持 `Python checks` / `Frontend checks`。4-worker draft PR #184 三轮均 success 但 91–96s 未达标；8-worker attempt 2 真实失败并使 workflow 红；6-worker 远端复验待收集。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: C2 后运行完整并行、串行、ruff、format 与 frontend vitest；远端 PR run 作为真栈性能验收。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型/reference）。
- Rollback: 回退 `47d65d3a` 可恢复 8-worker（快但远端不稳定）；回退 `0d6ab276` 可恢复 4-worker（远端稳定但 91–96s 未达标）；整体回退 `6236644b` 及前序测试改写可恢复原串行 CI。
- Commits: C1=`c833720f`，初始 C2=`6236644b`，4→8 Verify=`2a2f3aa1`，8-worker C2=`0d6ab276`，8→6 Verify=`d60e7b1e`，6-worker C2=`47d65d3a`，C3=待远端证据完成。
- Next: 6-worker 本地连续两轮完整门禁已绿并将推送；等待三次 GitHub Actions success，在此之前 R3 保持 DOING。

## [Design 修订] R3: 固定 4 worker → 固定 8 worker

- 现状方案: Python job 使用固定 4 worker；本地全量已绿，但 GitHub 普通托管 runner 的三次成功 attempt 总 required 时间分别为 94s、91s、96s，均未达到 ≤90s 退出标准。
- 新方案: 保持单 job、worksteal、完整 non-e2e、lint 顺序、check 名称和 pip cache 不变，只把固定并行度调为 8 worker。
- 原因: 远端稳定成本为 install 20s + pytest 61–64s，4 worker 已证明不足；design 现有本地基准已验证 8 worker 全绿且比 4 worker 更快（42.35s vs 52.73s），这是满足既定门槛的最小参数调优。
- 影响范围: 仅本 milestone；不影响后续 milestone（本 unit 只有 M1）。
- design.md 是否同步改: 是，已更新决策 2、命令、图示、风险、runbook 与 Milestone 退出命令，并追加 Changelog。
- Commits: 调优 Verify=`2a2f3aa1`，调优 C2=`0d6ab276`。
- 远端未达标证据:

| Run | Attempt | Python | Frontend | Required completion | 结论 |
|---|---:|---:|---:|---:|---|
| 29097094967 | 1 | 94s | 57s | 94s | success，但超过目标 4s（冷 cache） |
| 29097094967 | 2 | 91s | 67s | 91s | success，但超过目标 1s |
| 29097094967 | 3 | 96s | 71s | 96s | success，但超过目标 6s |

- Next: workflow 已调为 `-n 8`，本地完整并行门禁 22.51s 全绿；推送后等待新的三次远端证据，在此之前 R3 保持 DOING。

## [Design 修订] R3: 固定 8 worker → 固定 6 worker

- 现状方案: 固定 8 worker；本地全量 22.51s 全绿，但远端 attempt 1 在 91% 被 GitHub 取消，attempt 2 出现两条真实并发敏感测试失败。
- 新方案: 固定 6 worker；保持 worksteal、完整 non-e2e、lint/cache/check 名称不变，不按测试分组，不修改两条历史测试。
- 原因: attempt 2 的 `test_interrupt_reaps_foreground_subprocess_and_self_heals` 缺 `tool_call_recovery`，`test_interrupt_with_inflight_foreground_tool_force_cancels_carrier_task` 的 interrupt 命中第二个 run 且耗时 30.05s；这证明 8-worker 不是可签收的稳定配置。6 worker 是 4 与 8 之间唯一仍属简单参数调优的候选。
- 影响范围: 仅本 milestone；两个并发敏感测试属于 out-of-unit 发现，本 unit 不修。
- design.md 是否同步改: 是，已更新 Changelog、决策 2、命令、图示、风险、runbook 与 Milestone 退出命令。
- 远端失败证据:

| Run | Attempt | Python | Frontend | pytest | 结论 |
|---|---:|---:|---:|---:|---|
| 29097895298 | 1 | 约 70s 后 canceled | 66s success | 运行到 91%，无断言失败 | workflow failure；证明非 success required check 会阻断 |
| 29097895298 | 2 | 95s failure | success | 68s；3442 passed / 2 failed / 2 skipped | 两条并发敏感测试真实失败，8-worker 不可采用 |

- Commits: 调优 Verify=`d60e7b1e`，6-worker C2=`47d65d3a`。
- Out-of-unit: 两条历史并发测试的跨 run 串扰已登记 [GitHub issue #185](https://github.com/Mrchen116/nano-multiagent/issues/185)；本 unit 不修改它们。
- Next: n=6 完整全量连续两轮分别 22.95s / 22.15s 全绿，上述两条定向复跑也全绿；推送后等待远端三次 success。
