# M10 — Heartbeat/Cron 真实终态与持久化复杂度

## Goal

修复 Round 4 verifier/code review 识别的 background lifecycle 缺口：heartbeat 在 submit 前捕获静默清理基线并显式处理 failed/cancelled；cron 无论是否配置 IM delivery 都必须消费真实 Kernel 终态；cron history 更新不得随累计 run 数产生二次 I/O。

## Exit criteria

- [ ] heartbeat transcript baseline 在 submit 前捕获并随 run record 传递；极快 `HEARTBEAT_OK` 也只移除本轮新增记录。
- [ ] heartbeat 对 completed/failed/cancelled 分流；failed/cancelled 有明确失败终态，不进入 silent-success trim。
- [ ] cron terminal consumer 为 mandatory dependency，IM observer/delivery 为 optional adapter；no-delivery 配置等待并持久化真实 terminal。
- [ ] missing terminal/stream failure 不得写 completed，失败 partial text 不写成功 awareness。
- [ ] CronRunsStore 启动/首次使用时 materialize 一次，状态 append/update 不再全量重放；并发、restart、limit 语义不变。
- [ ] 永久单元/真 Kernel 失败回归、`ruff check .` 与 `pytest -m "not e2e"` 全部通过。
- [ ] milestone 分支合入并推送 `unit/refactor-463`，随后清理 milestone worktree/branch及自启服务。

## Test strategy

- heartbeat scheduler/runner：submit gate + 快完成 run，断言 baseline 来自 submit 前；failed/cancelled 不 trim 且走失败呈现。
- cron owner chain：delivery present/absent 下 completed/failed/cancelled/missing-terminal 统一消费；只有 completed 写 awareness。
- CronRunsStore：instrument `_materialize_all`/文件读取次数，重复状态更新不随历史增长；并发更新和新实例重载结果一致。
- 隔离真 Kernel/fixture：公开 cron history 从 running 收敛到 failed/cancelled，conversation 不出现成功 awareness；使用高位端口并清理 PID，保留用户 `LLM_PROXY --ui`。
- 非前端改动，无 frontend build/test 要求。
- 永久测试落点：扩展 `test_heartbeat_scheduler.py` 与 `test_heartbeat_session_trim.py`；cron owner 扩展 `test_cron_execution_owner_chain.py`；run history 从已超 400 行且混合多职责的 `test_cron_delivery_chain.py` 拆到专属 `test_cron_run_history.py`。

## Roadpoints

### R1 — Heartbeat pre-submit baseline 与非成功终态 (DONE)

- [x] C1 红测：锁定快完成 silent run、failed/cancelled 不 trim。
- [x] C2 实现：由 scheduler 传递 baseline，consumer 分流 typed outcome。
- [x] C3 文档：记录用户可观察失败与 transcript 证据。

### R2 — Mandatory cron terminal consumer

- [x] C1 红测：锁定 no-delivery failed/cancelled/missing-terminal 不得 completed。
- [ ] C2 实现：解耦 mandatory consume 与 optional delivery/observer。
- [ ] C3 文档：记录真实 history/awareness 证据。

### R3 — Incremental cron history owner

- [ ] C1 红测：锁定重复 update 不全量读取、restart materialization 正确。
- [ ] C2 实现：单次装载的进程内 materialized index + append-only durable update。
- [ ] C3 文档：记录复杂度、并发与重启证据。
