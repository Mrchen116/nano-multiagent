# refactor-463-M2 — Progress

## 启动基线

- Context: M1 已合入并推送 `unit/refactor-463`；milestone worktree 从 `origin/unit/refactor-463` 的 `45f4cda271883ae270d47b7cacc27da055b6d634` 创建。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3347 passed, 1 skipped`（38.40s）。
- Leader alignment: M2 必须覆盖 typed image、subscriber/queue/dispatcher/delivery owner、one 80% deadline 与完整 shutdown graph，并留下真端到端图片/后台/stop/offline 证据。
- Scope rationale: M2 范围列漏列 `scheduler/cron_service_registry.py` 与 `scheduler/cron_execution_service.py`，但 D6/退出标准已明确要求 cron O(1) seal / same-deadline drain。orchestrator 确认两文件是落实既定 decision 的必要真实 owner，不需改 design；变更只限 admission seal、具名 current task drain/timeout isolation 与公开接线，不改变 cron 调度、持久化或投递语义。

## R1 — 迁出 typed models 与图片解析策略

- Context: 图片 fetch/size/structure/MIME/data-URL 策略与 `PipelineResult` / `RelayLifecycleUpdate` 都定义在 1,800 行 pipeline 内；图片测试还直接 import 私有检测函数，runtime delivery 反向依赖 façade 内的 DTO。
- Decision: 新增 concrete `ImageAttachmentResolver` 与 frozen `ImageResolution(parts, failure)`，完整迁入 raw URL、下载、5MB cap、结构校验与 MIME authority；pipeline 只负责恰好调用一次 resolver 和把 typed failure 映射到既有固定可见文案。共享 DTO 迁到 `inbound_models.py`，所有生产/测试调用方改从 owner 导入，旧 pipeline 不保留 class alias/re-export。
- Rationale: 媒体策略可以独立变化而不要求调用方学习下载/格式规则；failure 文案与“不 submit/不写 Kernel history”仍在 inbound transaction 边界，避免 resolver 反向拥有投递。DTO 脱离 façade 消除 runtime-delivery → inbound-pipeline 的类型依赖。
- Evidence:
  - Tests: typed resolver + pipeline/lifecycle/heartbeat/streaming 聚焦门禁 → `92 passed`；全部 inbound pipeline 回归 → `102 passed`；相关 `ruff check` → passed。
  - Entry: `InboundPipeline.handle_inbound()` 公开入口验证有效 PNG 以 detected `image/png` data URL 到达 Kernel；download/oversize/corrupt 均不 submit、原会话收到固定文案；下一纯文本轮仍可正常 submit。真 Gateway/IM 图片入口统一在 R4 durable evidence 复核。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `tests/unit/personal_assistant/test_image_attachment_resolver.py` 与 `test_gateway_image_inbound.py`；R1 是 owner 迁移，真进程入口在对象图与 shutdown 全部切线后的 R4 执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `174b4043f` 恢复 pipeline 内图片策略与 DTO；C1 可随同回退。
- Commits: C1=`c2b2240ea`；C2=`174b4043f`；C3=本次 docs commit。
- Next: R2 C1 锁定 subscriber、dispatcher 与 queue 的公开资源生命周期。

## R2 — 收回 subscriber、dispatcher 与 queue worker 生命周期

- Context: pipeline 用裸 dict 拥有 subscriber，main 内嵌 dispatcher 且不保存 root handle，queue 用裸 `create_task` 启 worker；shutdown 因而无法区分 seal admission、settle submit 边界和 Kernel 后 drain，也无法给 queued-before-submit 工作明确终态。
- Decision: 新增 concrete `BackgroundSubscriptionManager`，以显式 agent id 构造稳定 dedupe key，保留首次 replay anchor/route 并 ensure-once；manager `seal()` 不 cancel，Kernel 后 `aclose(deadline)` 并发收拢。新增 `InboundDispatcher` 同时追踪 loop task 与 thread-safe future。`SessionRunQueue` 增加 seal、typed `GatewayShutdownBeforeSubmit`、pending lifecycle callback、admission event、具名 worker与同 deadline settle/drain。pipeline 只通过 manager/queue 公开接口接线；删除旧 subscriber dict/method、main 私有 dispatcher class 以及对等 private subscriber 测试。
- Rationale: 每类 task 集合只存在于创建它的 owner；composition/shutdown 只调用 seal/settle/drain，不读取集合。queued item 的 failed lifecycle 仍复用 relay callback，未新增 wire 字段或用户文案；active head 保留给 Kernel close 产生终态。
- Evidence:
  - Tests: 新 owner 公共 lifecycle 门禁 → `6 passed`；subscriber/pipeline/queue/build-runtime 既有回归 → `38 passed`；相关 `ruff check` → passed。
  - Entry: public manager 测试证明同 session 两次 ensure 只打开一个 `after_sequence=7` stream，重复 `_id=42` 生成同一 `agent-a|tool_call:sess-bg:42` 并回原 `ReplyContext`；seal 后新订阅拒绝、当前 callback 不被提前 cancel。queue/dispatcher 公开测试证明 post-seal work 不执行、accepted root/worker drain 后无具名 task。真 Gateway/IM 入口统一在 R4。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `test_background_subscription_manager.py`、`test_inbound_dispatcher.py`、`test_run_queue.py`；`test_inbound_pipeline_sse.py` 删除对 pipeline subscriber 私有 dict/callback 的断言并降到 392 行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `31429404a` 恢复 pipeline/main/queue 旧 ownership；C1 可随同回退。
- Commits: C1=`943bb14d8`；C2=`31429404a`；C3=本次 docs commit。
- Next: R3 C1 锁定唯一 delivery task tracker 与 observer 无裸 detached coroutine。
