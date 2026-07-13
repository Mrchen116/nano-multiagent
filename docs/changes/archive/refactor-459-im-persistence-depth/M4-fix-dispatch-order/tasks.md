# refactor-459-M4: 修正 dispatch 与注册顺序 — Tasks

> 对齐: ../design.md（2026-07-11 acceptance round 1 Changelog）

## 目标

在保持公开协议、SQLite schema shape 与既有非原子副作用边界不变的前提下，恢复 Gateway advertisement 的输入顺序，并让跨 connection/process 的同 key agent dispatch 只有 durable winner 被 relay，所有 ack 复用 winner。

## 退出标准

- [x] register 的首次 online 广播按非字典序 advertisement 输入顺序产生 `agent.status_changed` 与递增 seq；heartbeat/disconnect 仍使用数据库稳定排序。
- [x] 两个独立 SQLite connection/handler 竞争同一 dispatch key 时，只有 durable winner 被 relay，两个 ack 均引用 winner message。
- [x] reviewer 的 shadow conversation HTTP duplicate finding 已用相同公开入口与 headers 在 `origin/main`、unit 分支完成差分；两边相同，仅记录 baseline-equivalent，未改变产品行为。
- [x] 真栈重复 dispatch、完整 non-e2e、e2e-critical 与 ruff 全绿。

## 测试策略

- 被测行为（来自退出标准）：非字典序 register 的 owner WS 广播顺序/seq；跨 connection first-write-wins 的 relay/ack；main/unit shadow HTTP duplicate 差分；真 Gateway duplicate dispatch。
- 已有测试在：`tests/im_service/integration/test_status_broadcast_e2e.py`（扩展）；跨 connection 的两个真实 SQLite handler 需要独立并发 fixture，新建 `tests/im_service/unit/test_gateway_dispatch_concurrency.py`，不与既有单 handler replay 测试重复。
- 落层/目录/marker：`tests/im_service/integration/` 与 `tests/im_service/unit/`，marker：无；真进程证据使用已有 `tests/e2e/critical_paths/` 与一次性 HTTP/WS 驱动。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：origin/main 与 unit HTTP 差分命令输出；真栈 Gateway register/dispatch frame 与公开 history/DB 计数。
- 前端 UI：N/A。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 恢复 advertisement 广播顺序

- 状态：DONE
- 步骤：先完成 main/unit shadow HTTP baseline；再用真实 FastAPI user/gateway WS 写非字典序 register 红测，修正 typed result 仅保留 protocol 输入顺序。
- 验证：公开 HTTP 两分支差分已记录；register online agent frames 与 seq 按 advertisement 顺序，disconnect DB 排序不变。

### R2 — 收口跨 connection dispatch winner

- 状态：DONE
- 步骤：用两个独立 SQLite connection、两个 handler 与确定性竞争屏障复现 loser relay/ack；handler 消费 `record_dispatch()` durable winner，loser 跳过自身 relay并复用 winner ack。
- 验证：两个 ack message id 相同且等于 durable winner；仅一个 relay task 指向 winner message；schema 与消息落盘副作用边界不变。

### R3 — 真栈与完整门禁收口

- 状态：DONE
- 步骤：按 reviewer Runbook 启动真 IM + Gateway；验证非字典序 register 广播和重复 dispatch winner ack/relay；运行完整门禁并记录 durable evidence。
- 验证：真实入口结果符合 R1/R2，`pytest -m "not e2e"`、`scripts/e2e-critical.sh -m "not slow"`、ruff check/format 全绿。
