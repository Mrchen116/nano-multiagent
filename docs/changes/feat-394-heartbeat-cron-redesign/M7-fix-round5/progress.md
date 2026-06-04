# M7-fix-round5: Progress

## 背景

Round 5 acceptance 暴露了 cron 执行层 5 处接缝断裂，orchestrator 亲自 trace 全链后
一次派发全量修复（不再逐轮）。

---

### R1 — RunOrigin.CRON + submit_message 映射 + _UNATTENDED_ORIGINS

- Context: RunOrigin 无 CRON，submit_message 走 else → _RunOrigin.SYSTEM → AttributeError
- Decision: origin.py 加 CRON = "cron"；submit_message 映射 cron→CRON；auto_mode_gate _UNATTENDED_ORIGINS 加 RunOrigin.CRON.value
- Rationale: 遵循 heartbeat 相同模式；cron 是无人值守 origin，tool ask 须走 unattended fallback
- Evidence: (待补)
- Rollback: R1 C2 commit hash

### R2 — cron 可见投递链（播种 run_context_store + 消费 stream）

- Context: _submit_cron_job 是 fire-and-forget，结果从未进直聊
- Decision: 在 _cron_tick_for_agent 中，对每个 due job submit 后播种 run_context_store
  并消费 kernel.stream 到终态，驱动 kernel_event_observer → node.streaming_delta → IM 直聊
- Rationale: 复用 _consume_heartbeat_run 的接线模式（播种 + stream 消费 + observer）
- Evidence: (待补)
- Rollback: R2 C2 commit hash

### R3 — file 工具缺失（cron 追加不覆盖 DEFAULT_TOOL_IDS）

- Context: cron_enabled=True 时 agent 只有 cron 工具，无 file 工具
- Decision: 查看 _load_agent_from_im_payload 与 sync_agent 组装 tool_allowlist 的逻辑
- Rationale: cron 应是 append 到现有 allowlist，而非替换；file 工具来自 DEFAULT_TOOL_IDS
- Evidence: (待补)
- Rollback: R3 C2 commit hash

### R4 — activeHours UI 控件

- Context: 配置页无 activeHours 控件，用户无法设置活跃时段
- Decision: agent-detail-page.tsx 和 agent-create-page.tsx 补 activeHours start/end 输入
- Rationale: spec 要求可配置活跃时段
- Evidence: (待补)
- Rollback: R4 C2 commit hash

### R5 — _AtSchedule 过期 at 不补跑

- Context: 过期 at + last_due_at=None → 触发；应按 openclaw 语义不触发
- Decision: _AtSchedule.due_times_up_to 中，若 last_due_at is None 且 due_at < now，视为过期不触发
- Rationale: openclaw computeNextRunAtMs 语义：at 时间已过（bootstrap 期）不补跑
- Evidence: (待补)
- Rollback: R5 C2 commit hash

### R6 — 端到端验证 + 文档收口

- Context: 所有 R1-R5 完成后做 live 端到端验证
- Decision: 按 design.md Runbook 起完整 e2e 环境，走 cron 投递全链
- Evidence: (待补)
