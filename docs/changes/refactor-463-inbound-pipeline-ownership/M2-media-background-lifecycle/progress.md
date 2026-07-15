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
