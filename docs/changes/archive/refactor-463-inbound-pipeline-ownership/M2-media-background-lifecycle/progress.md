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

## R3 — 收回 observer detached delivery task 所有权

- Context: observer 的 delta、tool/permission terminal、external mirror、skill-created、reconcile 与 bubble finalize 全部以裸 `create_task` 脱离事件调用栈；Gateway 没有 handle，IM close 前也无法证明这些投递已经完成。
- Decision: 新增 concrete `RuntimeDeliveryTaskTracker`，由 composition root 构造单例并注入 observer；所有 detached awaitable 以 `runtime-delivery:<event>:<run>` 语义名进入 tracker。关闭先拒绝新 admission，再按同一 absolute deadline drain 到集合为空；到期统一 cancel/await leftovers 并在 `TimeoutError` 中列出 task name。ordering-critical 的 turn-start/roll callback 仍原样返回给 producer await，不进入 tracker。
- Rationale: observer 只翻译事件，不拥有 event-loop task 集合；tracker 是唯一 detached delivery owner，既保持投递异常不反向打断 Kernel stream，又给 Gateway shutdown 一个可证明、可诊断的收拢边界。直接构造 observer 的既有单测保留局部 tracker，生产路径显式注入唯一实例。
- Evidence:
  - Tests: tracker seal/drain/timeout/零残留与 observer 禁止裸 task → `3 passed`；relay lifecycle、heartbeat delivery、streaming、external visibility、permission 回归 → `87 passed`；相关 `ruff check` → passed。
  - Entry: public tracker 测试证明 close 已开始时旧 delivery 继续完成、late awaitable 被关闭并拒绝；deadline 到期同时取消 delta/tool terminal 两项并报告语义名，最终无 `runtime-delivery:*` task。source contract 证明 observer 内无 `.create_task(`。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `tests/unit/personal_assistant/test_runtime_delivery_task_tracker.py` 加既有 runtime-delivery 回归；tracker 最终 close 顺序与真进程零残留在 R4 统一验证。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `f9f4992a5` 恢复 observer 裸 task 调度；C1 可随同回退。
- Commits: C1=`c68f93a86`；C2=`f9f4992a5`；C3=本次 docs commit。
- Next: R4 C1 锁定单一 80% deadline、O(1) producer seal、Kernel-before-consumer-drain、timeout isolation 与全图零残留。

## R4 — 关闭完整 ingress resource graph 并证明真入口

- Context: refactor-461 的 runtime cleanup 仍按 owner 顺序各自等待，未追踪 inbound root、queue worker、subscriber 与 detached delivery；internal HTTP、heartbeat 和 cron 也没有“同步拒绝新 work / Kernel 后 drain current work”的两段式关闭。首轮真栈还暴露出 deadline 到期取消 active queue worker 时，`CancelledError` 越过 pipeline 的 `except Exception`，使 IM relay 永久停在 `sent`。
- Decision: `request_shutdown()` 首次调用记录 monotonic 起点，cleanup 第一条语句派生唯一 80% absolute deadline。dispatcher/internal handler/heartbeat/cron/queue/subscriber/channel 先 O(1) seal，settle admission 后先 `kernel.aclose()`；再以同一 deadline 并发 drain AppRunner、heartbeat current tick、cron current execution、accepted inbound roots、queue workers 与 subscriber，最后 repeat-drain delivery tracker、关闭 IM/resources。active worker 的 deadline cancellation 在重新抛出前发明确 failed lifecycle，作为 Kernel close 超时后的最后终态兜底。
- Rationale: producer 的 admission switch 不再被 handler/tick 网络等待阻塞；Kernel terminal consumer 与投递保持存活到正确阶段。单项 timeout/异常只记录本 owner，不跳过资源图其余节点。queued-before-submit 与 active-after-submit 分别由 queue failure 和 Kernel/consumer terminal 收口，IM transport 不会先被关闭。
- Evidence:
  - Tests: shutdown resource graph、active relay cancellation、owner lifecycle 与文件大小 contract → `33 passed`；`ruff check src tests` → passed；全量非 e2e → `3367 passed, 1 skipped, 22 warnings`（33.82s）。
  - Entry: 真 IM/Gateway 证据覆盖有效/坏图与恢复、后台哨兵回原 conversation 且 8 秒窗口内只出现一次、真前台 Bash `/stop`、SIGTERM 时 active relay `sent → failed`。真 GatewayRuntime/Kernel 的确定性 FIFO 场景得到 `second → failed(gateway_shutdown_before_submit)`、`first → failed(run was aborted)`；`im_service=None` 的 external channel 经真 LLM 返回 `OFFLINE651B70A9`。完整命令与输出见 `evidence/live-stack.md`。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: 临时真栈驱动执行后已删除；持久回归落在 concrete owner/shutdown 单测与既有 critical-path e2e。新增 `test_gateway_shutdown_resource_graph.py` 393 行，其他新增测试均低于 400 行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 shutdown C2 `3651bf8e1` 与 active-terminal fix `85e4bb651`，再回退对应 C1；若资源图任一节点回退，M2 整体回退，不能保留半套 seal/drain。
- Commits: resource graph C1=`f439a9f6b`、C2=`3651bf8e1`；active terminal C1=`8ee021809`、C2=`85e4bb651`；C3=本次 docs commit。
- Next: 将 milestone 合入 `unit/refactor-463`、推送并清理 milestone branch/worktree，M3 才开始迁移最终 `SessionRunCoordinator`，不在 M2 重写 queue 算法。

## 正式签收 closure — O(1) seal 与 IM shared-deadline 完整收口

- Context: 正式签收发现三处实现证据未完全匹配 D6：queue seal 仍做 O(n) pending walk 并同步派生 callback task；IM close / supervisor await 绕过 inner deadline；既有 isolation test 只覆盖普通 `RuntimeError`，没有证明真实 deadline overrun 后完整资源图继续收口。
- Decision: queue 的同步 seal 收缩为单一 `_sealed=True`，`settle_admission(deadline)` 在 Kernel close 前摘除非 active-head 项并 await admission/lifecycle settlement；GatewayRuntime 依次用同一 `_run_shutdown_operation` 和同一 `inner_deadline` 执行 IM transport close、IM supervisor task await。新增独立 shutdown timeout isolation 测试，以一个 owner 睡到 shared deadline 后抛 `TimeoutError`，同时启动真实 AppRunner，并验证后续 delivery、两个 IM 阶段和 resource closer。
- Rationale: admission switch 的复杂度不再随 backlog 增长；per-item failure 仍只由 queue owner 在 async settlement phase 产生，未形成第二 owner。IM 两步即使 deadline 已过也各自获得一次 bounded attempt；helper 隔离 timeout 后继续执行同步 closer，保留外层 20% 退出余量。
- Evidence:
  - Tests: closure 红测修前分别观察到 pending 在 seal 后已经 terminal，以及 IM close 超过 shared deadline 后未被取消；修后聚焦 shutdown/queue/tracker/contract → `26 passed`，`ruff check src tests` → passed；全量非 e2e → `3369 passed, 1 skipped, 22 warnings`（37.88s）。
  - Entry: 原 M2 真 IM/Gateway 图片、后台、`/stop`、active/queued shutdown 与 IM-offline 证据保持有效；本轮是 shutdown ownership 内部 closure，新增确定性真实 event-loop/AppRunner resource graph 证据见 `evidence/live-stack.md` 的“正式签收 closure”段。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `test_seal_defers_pending_settlement_to_async_phase` 锁定 seal/settle 两阶段；`test_timeout_does_not_skip_later_owners_or_reset_deadline` 锁定真实 timeout、同 deadline、完整后续 close 与端口释放。调试中确认 `ready_event` 先于 IM task create 可被观察，测试因而显式等待 manager `run_forever` 入口，避免把 readiness 误当 supervisor-start。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C2 `7677fc1d1` 恢复签收前实现；C1 可随后回退。
- Commits: C1=`c2bf0d4eb`；C2=`7677fc1d1`；C3=本次 docs commit。
- Next: 推送 `unit/refactor-463`，交回独立正式签收；M2 不再有已知 design mismatch。
