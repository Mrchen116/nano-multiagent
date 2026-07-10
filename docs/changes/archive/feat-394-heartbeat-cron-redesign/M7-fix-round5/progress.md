# M7-fix-round5: Progress

## 背景

Round 5 acceptance 暴露了 cron 执行层 5 处接缝断裂，orchestrator 亲自 trace 全链后
一次派发全量修复（不再逐轮）。另发现一隐藏 bug：local_store YAML 解析器未读取
cron.enabled 字段，导致 cron_enabled 永远 False。

---

### R1 — RunOrigin.CRON + submit_message 映射 + _UNATTENDED_ORIGINS

- Context: RunOrigin 无 CRON，submit_message 走 else → _RunOrigin.SYSTEM → AttributeError
- Decision: origin.py 加 CRON = "cron"；submit_message 映射 cron→CRON；auto_mode_gate
  _UNATTENDED_ORIGINS 加 RunOrigin.CRON.value 和 "cron" string form
- Rationale: 遵循 heartbeat 相同模式；cron 是无人值守 origin，tool ask 须走 unattended fallback
- Evidence:
  - Tests: 4 unit tests 全绿 (test_cron_run_origin.py)
  - 验证: submit_message(origin="cron") 不再 AttributeError，CRON enum 存在
- Commits: C1=80586c68, C2=e48d9908

### R2 — cron 可见投递链（播种 run_context_store + 消费 stream）

- Context: _submit_cron_job 是 fire-and-forget，结果从未进直聊
- Decision: _submit_cron_job 返回 (run_id, kernel_session_id) 元组；
  _cron_tick_for_agent 的 _submit_and_deliver_fn 播种
  run_context_store{to_user_id=owner_user_id, agent_id, kernel_session_id=""} +
  消费 kernel.stream 到终态，驱动 kernel_event_observer → node.streaming_delta →
  IM 直聊；stream 终态后调 _append_awareness 写 System(untrusted) 进直聊 JSONL
- Rationale: 复用 _consume_heartbeat_run 的接线模式（播种 + stream 消费 + observer）
- Evidence:
  - Tests: 3 delivery chain + 7 awareness tests 全绿
  - Live E2E (见 R6): cron 消息出现在 IM 直聊 ✓
- Commits: C1=40555ec3, C2=37b41f5d

### R3 — file 工具缺失（cron 追加不覆盖 DEFAULT_TOOL_IDS）

- Context: cron_enabled=True 时 agent 只有 cron 工具，无 file 工具（tool_allowlist=["cron"]）
- Decision: inbound_pipeline.create_session 时，若 agent.tool_allowlist 非空，
  合并 PERSONAL_ASSISTANT_PROFILE.default_tool_ids + extras；
  via `from agent.sdk import PERSONAL_ASSISTANT_PROFILE` 符合依赖边界规则
- Rationale: IM tool_allowlist 是"额外工具"，不应替换 DEFAULT_TOOL_IDS
- Evidence:
  - Tests: 3 unit tests 全绿 (test_cron_file_tools.py)
  - tool_allowlist=["cron"] → 合并后含 read/write/edit/bash/cron ✓
  - contract/boundary tests 通过（无 agent.products 跨包 import）
- Commits: C2=0f87a318

### R4 — activeHours UI 控件

- Context: 配置页无 activeHours 控件，用户无法通过 UI 设置活跃时段（spec S2.5）
- Decision: agent-detail-page.tsx HeartbeatCard 补 start/end time inputs（`<input type="time">`），
  testid: heartbeat-active-hours-start / heartbeat-active-hours-end；
  onActiveHoursChange 更新 draft.heartbeat.active_hours.{start,end}
- Rationale: spec "我在配置页给某 agent 的 heartbeat 设了活跃时段 09:00–22:00"
- Evidence:
  - tsc -b && vite build 通过（无 TS 错误）
  - vitest: 361/361 passed
  - UI 新增两个 time input，留空=关闭活跃时段限制
- Commits: C2=695c4b2e

### R5 — _AtSchedule 过期 at 不补跑

- Context: 停机期间错过 at 时间点的一次性任务，重启后 last_due_at=None 被错误触发
- Decision: 引入 _AT_SCHEDULE_EXPIRED_GRACE = 60s；
  若 last_due_at is None 且 (now - due_at) > 60s → 视为过期不触发；
  60s 内的 tick 延迟（正常调度）仍触发
- Rationale: openclaw computeNextRunAtMs 语义：at 已过点不排；60s grace period
  保证"首次到点"（3s 内）仍 fire，"停机 7h 重启"不补触发
- Evidence:
  - Tests: 5 unit tests 全绿 (test_cron_at_expiry.py):
    - 首次 at 到点 fire ✓; 3s 内 tick fire ✓; 7h 后重启 no fire ✓
    - 已执行过不 refire ✓; 未到点不 fire ✓
- Commits: C2=bdac274b

### R6 — local_store YAML cron 解析 + 端到端验证

- Context: local_store._parse_agents 从未解析 `cron:` 块，导致 cron_enabled 永远 False；
  gateway 启动时所有 agent 无法通过 YAML 启用 cron（只能依赖 IM config sync 热更）
- Decision: _parse_agents 补 cron 字段解析（仿 heartbeat 段）；
  cron_enabled 从 YAML `cron.enabled` 读取，并注入 AgentWorkspaceConfig
- Rationale: 这是隐藏在 round-1~5 间的根本 bug：无此修复 cron 从不在 gateway 启动时生效
- Evidence:
  - Live E2E 全链验证（IM :57261, Gateway node wt-feat394-m7, LLM proxy :4000）:
    - cron job "Time reporter" (every 30s) 注册 → 到点执行 → IM 直聊出现 agent 消息
    - IM conversation fa5e57a09f994b4c891b19982ad79ef2 (type=direct):
      message sender_type=agent, content="Current time: 02:51:16 UTC",
      created_at=2026-06-04T02:51:21.009346Z ✓
    - cron-state.json: {"jobs": {"4f8b3b3a...": {"last_due_at": "2026-06-04T02:51:00+00:00"}}}
    - gateway log: run_submitted=run_198c0fdf94bfa45e → run_started → POST /v1/messages 200 OK → run_completed ✓
    - kernel session sess_e04c49c0eca19fbe.jsonl: assistant="Current time: 02:51:16 UTC" ✓
    - heartbeat 静默（HEARTBEAT_OK）正确工作: sess_e2081d4c9f6d0f3f, sess_cef4c2637f6769bf ✓
  - 全套 pytest -m "not e2e": **2508 passed**, 3 failed (预存在 macOS/tmp)
  - tsc -b + vitest: 全绿
- Commits: C2=87a3a770
