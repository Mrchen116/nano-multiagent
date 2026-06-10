# M4: unified-cron-run — Tasks

## 目标

- 在 `agent.core.tools` 定义 `HostCapabilityDispatcher` + `HostCapabilityContext` 类型
- `agent.sdk` re-export 并在 `build_kernel()` 增加可选 `host_capabilities` 参数注入
- `cron tool` 的 `run` 动作改为调用 `host_capabilities.invoke("personal_assistant.cron.enqueue", ...)`，删除 `gateway_cron_url` 旁路
- `personal_assistant.scheduler` 将 `CronRunner` + `_cron_tick_for_agent` 收敛为长生命周期 `CronExecutionService`，`scheduled` 与 `manual` 入口使用同一 `enqueue` 方法
- Gateway 关闭时先等 `CronExecutionService` drain 完成
- `runs.jsonl` 结构化历史：accepted→running→terminal 三阶段追加；启动时遗留 accepted/running 收敛为 `failed(gateway_restarted)`
- `cron runs` 工具动作查询 runs.jsonl，返回最新 records

## 退出标准 (来自 design.md M4 行)

- SDK/core 无 cron 类型或语义
- scheduled/manual 只调用同一 execution service，不存在 `gateway_cron_url` 或 loopback HTTP
- run history 覆盖 accepted→running→terminal、manual/scheduled、失败与重启遗留状态，`cron runs` 返回最新 records
- 一次性 job 保持成功 submit 后删除
- `pytest -xvs tests/unit/personal_assistant/test_cron_tool_openclaw.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/unit/personal_assistant/test_cron_runner_awareness.py tests/unit/personal_assistant/test_cron_scheduler_tick.py tests/contract/test_cron_coding_cli_isolation.py tests/contract/test_agent_sdk_surface_contract.py` 全绿

## 测试策略

后端/API 任务，入口验证为真实测试调用路径。

- **R1**: HostCapabilityDispatcher 类型定义 (core/sdk)，无 cron 类型 — 单元测试 + contract 测试
- **R2**: cron tool run 动作改为 host capability dispatch — 单元测试（红→绿）；test_cron_tool_openclaw.py 中的 run 动作测试覆盖
- **R3**: `CronExecutionService` + runs.jsonl 历史 — 单元测试（red: test_cron_delivery_chain.py 中增加结构化历史测试）
- **R4**: Gateway composition 改用 `CronExecutionService`，手动/定时共用 enqueue — test_cron_scheduler_tick.py 覆盖；test_cron_runner_awareness.py 覆盖
- **R5**: 启动收敛遗留 accepted/running 记录 + runs 查询从 runs.jsonl 读取最新 records

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | HostCapabilityDispatcher 类型定义 + sdk re-export + build_kernel 注入 | DONE |
| R2 | cron tool run 动作改用 host capability dispatch，删除 gateway_cron_url | DONE |
| R3 | CronExecutionService + runs.jsonl 三阶段历史 | DONE |
| R4 | Gateway composition 改用 CronExecutionService (scheduled+manual 共用 enqueue) | DONE |
| R5 | 启动遗留记录收敛 + cron runs 从 runs.jsonl 返回最新 records | TODO |
