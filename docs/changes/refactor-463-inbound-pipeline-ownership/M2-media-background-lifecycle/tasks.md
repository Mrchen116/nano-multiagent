# refactor-463-M2: 图片、后台订阅与 ingress resource ownership — Tasks

> 对齐: ../design.md（2026-07-15 Approved 基线）

## 目标

把图片解析、后台 session 订阅、入站 root/queue worker 与 detached delivery task 的生命周期收回各自 concrete owner，并让 Gateway 以一个从 shutdown 请求时点派生的 80% absolute deadline 完成 seal → settle → Kernel close → consumer/delivery drain → IM close；用户可见的图片反馈、后台原会话回复、停止终态与外部 channel 离线自治保持不变。

## 退出标准

- [x] `ImageAttachmentResolver.resolve()` 返回 typed `ImageResolution(parts, failure)`，保留有效图片、raw URL、MIME authority、整轮失败和固定可见反馈语义。
- [x] `BackgroundSubscriptionManager` 公开验证 ensure-once、replay anchor、BACKGROUND_TASK dedupe key、seal 和 Kernel 后 close；已有 subscriber 在 Kernel 前不被 cancel。
- [x] `SessionRunQueue` 在 seal 时拒绝新 work、摘除尚未开始项并以明确 shutdown exception 完成 future，持续追踪/按同一 deadline drain worker；`InboundDispatcher` 同时追踪 loop task 与 thread-safe future roots。
- [x] observer 所有 detached coroutine 都经 concrete `RuntimeDeliveryTaskTracker`；producer 结束后 tracker close-and-repeat-drain，关闭后无 delivery task。
- [x] Gateway shutdown 在任何 await 前从首次 `request_shutdown()` 时点建立单个 80% absolute deadline；所有 producer O(1) seal，settle admission 后先 Kernel close，再以同一 deadline 并发 drain AppRunner、active heartbeat、cron、accepted roots、queue workers、subscribers，最后 delivery → IM。
- [x] active heartbeat/HTTP handler 不阻塞 Kernel close；单项 timeout/异常不跳过其余 drain；关闭后无 `bg-sse-sub:*`、queue worker、inbound root 或 delivery task。
- [x] 无旧 private callback post-wiring、`_InboundDispatcher`/`PipelineResult`/`RelayLifecycleUpdate` 旧 class re-export；新增/拆分测试文件不超过 400 行，最窄测试、`ruff check src tests` 与 `pytest -m "not e2e"` 全绿。
- [x] 隔离真栈 durable evidence 证明有效/失败图片、后台结果原会话且不重复、停止时 active/queued 明确终态，以及 IM 离线不阻断外部 channel；pytest/stub 只作回归补充。

## 测试策略

- 被测行为（来自退出标准）：resolver typed 成功/失败；subscriber ensure/replay/dedupe/seal/close；queue seal/cancel/drain；dispatcher 同 loop/跨线程 accepted root；observer tracker ownership；单 deadline shutdown 顺序、timeout isolation、task 零残留；真实图片/后台/stop/offline journey。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_image_inbound.py`、`test_background_session_events.py`、`test_inbound_pipeline_sse.py`、`test_gateway_shutdown_order.py`、`test_gateway_runtime_lifecycle.py`、`test_internal_dispatch_endpoint.py`、`test_heartbeat_scheduler.py`、`test_cron_scheduler_tick.py`、`test_gateway_build_runtime.py`（扩展并删/改 private-layout 断言）；新建 `test_image_attachment_resolver.py`、`test_background_subscription_manager.py`、`test_inbound_dispatcher.py`、`test_runtime_delivery_task_tracker.py`，理由：四个新 concrete owner 尚无合适公开行为测试归属；新增 shutdown resource-graph 测试文件，理由：既有 shutdown 文件已接近/超过 400 行且新行为是一条独立公开生命周期。
- 落层/目录/marker：owner 逻辑与 composition 协作落 `tests/unit/personal_assistant/`，marker：无；旧符号/private wiring 禁止回流落 `tests/contract/`，marker：无；真进程/真 LLM 验收复用 `tests/e2e/critical_paths/` 与 unit durable evidence，marker：e2e。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`M2-media-background-lifecycle/evidence/` 下的隔离真栈命令输出、日志摘录、IM API/SQLite/session 对账；临时驱动脚本收尾删除。
- 用户路径分类：N/A（无前端 UI 变更）。
- UI 状态矩阵：N/A。
- Prototype / Reference Contract：N/A。
- 范围说明：M2 范围列漏列 `scheduler/cron_service_registry.py` 与 `scheduler/cron_execution_service.py`，但 D6 与 M2 退出标准已明确要求 cron O(1) seal / same-deadline drain；orchestrator 已授权把这两个真实 owner 纳入，仅补 admission seal、具名 current task drain/timeout isolation 与 GatewayRuntime 公共接线，不改变 cron 调度、持久化或投递语义。

## Roadpoints

### R1 — 迁出 typed models 与图片解析策略

- 状态: DONE
- 步骤: 先提交 resolver typed output 与 pipeline 可见成功/固定失败红测，再新增 `inbound_models.py` / `image_attachments.py`，切换 pipeline/lifecycle/context 导入并删除旧 class re-export/private resolver 测试。
- 验证: `pytest tests/unit/personal_assistant/test_image_attachment_resolver.py tests/unit/personal_assistant/test_gateway_image_inbound.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`

### R2 — 收回 subscriber、dispatcher 与 queue worker 生命周期

- 状态: DONE
- 步骤: 先提交公开 ensure/replay/dedupe/seal/close、accepted roots 与 pending cancellation/worker drain 红测，再实现 manager/dispatcher/queue lifecycle 并切换 pipeline/main。
- 验证: `pytest tests/unit/personal_assistant/test_background_subscription_manager.py tests/unit/personal_assistant/test_background_session_events.py tests/unit/personal_assistant/test_inbound_dispatcher.py tests/unit/personal_assistant/test_run_queue.py`

### R3 — 收回 observer detached delivery task 所有权

- 状态: DONE
- 步骤: 先提交 tracker start/seal/repeat-drain/timeout 红测与 observer 无裸 task contract，再实现 composition-root singleton tracker 并改接所有 detached coroutine。
- 验证: `pytest tests/unit/personal_assistant/test_runtime_delivery_task_tracker.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py`

### R4 — 关闭完整 ingress resource graph 并证明真入口

- 状态: DONE
- 步骤: 先提交单 deadline、O(1) seal、active heartbeat/HTTP、queued/active terminal、timeout isolation/零残留红测，再接 GatewayRuntime、internal dispatch、heartbeat、cron、consumer/delivery/IM 顺序；删除 private post-wiring/旧 class re-export；最后跑隔离真栈并落 durable evidence。
- 验证: 相关最窄单测 + contract；`ruff check src tests`；`pytest -m "not e2e" -n 4 --dist worksteal`；隔离高位端口真栈图片/后台/stop/offline journey 与持久化对账。
