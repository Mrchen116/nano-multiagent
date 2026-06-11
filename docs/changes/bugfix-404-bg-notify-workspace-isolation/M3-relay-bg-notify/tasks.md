# M3-relay-bg-notify Tasks

## Testing Strategy

单元测试为主：
- C1 红测覆盖 BACKGROUND_TASK origin assistant_message 经 gateway 回流到 IM 的全路径
- self_evolution_review 既有语义回归测试确认不破坏
- `pytest tests/ -m "not e2e"` 全绿

live e2e：起 e2e-up.sh 栈，IM 直聊让 agent 后台跑 `sleep 30 && echo BG404DONE`，确认收到含结果的第二条回复后 e2e-down。

## Roadpoints

### R1 (C1 — 红测)

- [ ] 在 `tests/unit/personal_assistant/test_background_session_events.py` 补 2 个新测试：
  1. `test_bg_subscriber_routes_background_task_assistant_message_to_bg_run_output_callback`：BACKGROUND_TASK origin 的 assistant_message 经 `bg_run_output_callback` 路由，不走 `on_event`
  2. `test_bg_subscriber_ignores_user_origin_assistant_message_in_bg_run_output_callback`：非 BACKGROUND_TASK origin 的 assistant_message 不走 `bg_run_output_callback`

- [ ] 在 `tests/unit/personal_assistant/test_inbound_pipeline_sse.py` 补 1 个测试：
  `test_background_task_assistant_message_relayed_to_outbound_router`：pipeline 的 background subscriber 收到 BACKGROUND_TASK origin 的 assistant_message 后把文本推到 channel.sent

### R2 (C2 — 实现)

- [ ] `background_session_events.py`：新增 `bg_run_output_callback` 参数；`_run_loop` 检查 origin == "BACKGROUND_TASK" 时调用它
- [ ] `inbound_pipeline.py`：`_ensure_background_subscriber` 接受 `reply_context`，组装 `bg_run_output_callback` 调 `outbound_router.send_text`；pipeline 调用处传入 `reply_context=binding.reply_context` 和 `workspace_root=str(agent_workspace_root_path)`

### R3 (C3 — 文档)

- [ ] progress.md live e2e 验证证据
- [ ] `docs/specs/gateway/spec.md` 更新契约层（BACKGROUND_TASK run 输出回流）

## Status

R1 C1: pending
R2 C2: pending
R3 C3: pending
