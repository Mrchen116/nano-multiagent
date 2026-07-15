# refactor-463-M3: SessionRunCoordinator 与最终窄 facade — Tasks

> 对齐: ../design.md（2026-07-15 Approved 基线）

## 目标

以 `SessionRunCoordinator` 成为每个 Gateway session 从 admission 到 terminal cleanup 的唯一运行 owner，原子隐藏 queue / active run / steer / stop / watchdog / reconcile；`InboundPipeline` 只保留 route、group gate、shadow sync 与 ignored chatter append，composition root、heartbeat 和 shutdown 只经公开 owner interface 协作，同时保持全部既有用户行为与 M2 resource lifecycle 不变。

## 退出标准

- [ ] Coordinator 的同一 per-session transition lock 线性化 active-check / destructive group drain / image resolve / steer 与 normal submit -> active marker；stop/steer 不可观察 submit 后、marker 前的半提交状态。
- [ ] steer race fallback 复用同一份 prepared parts，群背景 destructive drain 与图片 resolve 均恰好一次；同 session FIFO、跨 session 并行和连续 steer 保持。
- [ ] active `/stop` 固定 mark -> interrupt -> append -> original stream reconcile；idle direct 友好提示、idle group 零副作用；completed/cancelled/failed/stall/stream-end/shutdown 的 active/interrupt cleanup 全部单点收口。
- [ ] quiet alive heartbeat 持续刷新 idle watchdog，真实 stall cancel + failed lifecycle 后释放 queue；`NO_REPLY`、terminal failure、external/shadow trigger-source 与原目标投递不变。
- [ ] `SessionRunQueue` 的 M2 O(1) seal、async settle 与 shared-deadline worker drain 只成为 coordinator 私有实现，不重写算法或 shutdown reason。
- [ ] heartbeat 只经 coordinator public `is_session_busy()`；GatewayRuntime 只经 coordinator public seal/settle/drain，`main.py` 不单独持有 queue lifecycle。
- [ ] `InboundPipeline` 不拥有 run/session/media/subscriber state；runtime lifecycle 不反向 import facade；32 个既有 `InboundPipeline` 测试文件完成行为覆盖盘点，对等 private access 删除而非改名迁移。
- [ ] architecture contract、`ruff check src tests`、`pytest -m "not e2e"` 与关键路径 e2e 全绿；隔离真栈 durable evidence 覆盖同/跨 session、连续插话、群背景/sender、active+idle stop、quiet+stall、NO_REPLY/failure、external/shadow、启动/停止/重连。

## 测试策略

- 被测行为（来自退出标准）：coordinator admission/linearization/steer fallback；stop ordering 与 terminal cleanup；watchdog liveness/stall；queue M2 lifecycle delegation；pipeline route/gate/shadow narrow facade；heartbeat/composition/shutdown public wiring；32 文件行为盘点；完整真栈用户旅程。
- 已有测试在：`tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py`、`test_gateway_stop_command.py`、`test_inbound_pipeline_permission_watchdog.py`、`test_inbound_pipeline_sse.py`、`test_inbound_pipeline_session.py`、`test_gateway_pipeline_sender_prefix.py`、`test_gateway_pipeline_no_fanout.py`、`test_gateway_build_runtime.py`、`test_heartbeat_session_binding.py`、`test_run_queue.py` 与既有 integration/e2e（迁到公开 facade/coordinator 行为并删除 private-layout 断言）；新建 `test_session_run_coordinator_admission.py`、`test_session_run_coordinator_terminal.py`，理由：新 deep owner 尚无合适 public behavior 测试归属；扩展 `test_gateway_inbound_ownership_contract.py`，理由：防旧 owner/private seam 回流。
- 落层/目录/marker：coordinator 纯逻辑与模块协作落 `tests/unit/personal_assistant/`，marker：无；源码 ownership 闸落 `tests/contract/`，marker：无；真进程/真 LLM 路径复用 `tests/e2e/critical_paths/`，marker：e2e。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时真栈驱动脚本；durable 命令输出、日志/IM/SQLite/session 对账与 32 文件盘点落 `M3-session-run-coordinator/evidence/`。
- 用户路径分类：N/A（无前端 UI 变更）。
- UI 状态矩阵：N/A。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 建立 coordinator admission 与线性化 owner

- 状态: DONE
- 步骤: 先提交 public dispatch/stop/is_session_busy 红测，覆盖同/跨 session、连续 steer、submit 暂停点、steer race prepared-parts 恰好一次与 queue lifecycle delegation；再实现 coordinator 独立 owner，不切生产 facade。
- 验证: `pytest tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_run_queue.py`

### R2 — 迁入 stop/terminal/watchdog 并收窄 pipeline

- 状态: DONE
- 步骤: 先提交 public terminal/stop/liveness/failure/NO_REPLY 红测并迁移旧 private assertions；再把 run/session/media/subscriber 状态与完整 terminal consumer 原子移入 coordinator，pipeline 只 route/gate/shadow/group append 后委托。
- 验证: coordinator terminal + stop/watchdog/SSE/route/group/external-delivery 聚焦门禁。

### R3 — 切换 composition/heartbeat/contracts 并完成真栈验收

- 状态: DOING
- 步骤: 先提交 build-runtime/heartbeat/shutdown/architecture 红测与 32 文件盘点；再一次构造 coordinator 并让 GatewayRuntime/heartbeat 只用公开 lifecycle/busy interface，删除旧 queue/facade owner seam；跑全量门禁与隔离真栈并落 durable evidence。
- 验证: 聚焦 wiring + contract；`ruff check src tests`；`pytest -m "not e2e" -n 4 --dist worksteal`；隔离高位端口关键路径 e2e 与持久化/日志对账。
